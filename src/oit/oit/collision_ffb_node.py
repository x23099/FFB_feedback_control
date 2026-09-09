"""
ROS 2 adapter for collision-warning force-feedback commands.

Hardware mode remains doubly gated and has no launch file.  The default and
dry-run modes do not import evdev or open a force-feedback device.
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

import rclpy
from oit_interfaces.msg import CollisionFfbCommand, CollisionFfbStatus
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rclpy.signals import SignalHandlerOptions

from oit.collision_ffb_policy import (
    CollisionFfbDecision,
    CollisionFfbRequest,
    CollisionFfbSafetyPolicy,
    OutputAction,
)
from oit.collision_ffb_backend import EvdevCollisionFfbBackend


OUTPUT_MODES = frozenset({"disabled", "dry_run", "hardware"})
INITIAL_HARDWARE_MAX_MAGNITUDE = 0.03


def validate_output_mode(value: object, *, hardware_armed=False) -> str:
    """Return a normalized mode, requiring an independent hardware arm."""
    mode = str(value).strip().lower()
    if mode not in OUTPUT_MODES:
        expected = ", ".join(sorted(OUTPUT_MODES))
        raise ValueError(
            f"unknown output_mode={mode!r}; expected one of: {expected}"
        )
    if mode == "hardware" and hardware_armed is not True:
        raise ValueError(
            "output_mode=hardware requires hardware_armed=true"
        )
    return mode


def collision_command_qos() -> QoSProfile:
    """Return the low-latency, non-persistent command QoS profile."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )


class CollisionFfbNode(Node):
    """Validate commands and expose the selected adapter status."""

    def __init__(
        self,
        *,
        monotonic_clock: Callable[[], float] = time.monotonic,
        current_time_clock: Optional[Callable[[], float]] = None,
        hardware_backend_factory=EvdevCollisionFfbBackend,
        **node_kwargs,
    ):
        """Create the adapter; default and dry-run never open a device."""
        super().__init__("collision_ffb_node", **node_kwargs)

        self.declare_parameter("command_topic", "/collision/ffb_command")
        self.declare_parameter("status_topic", "/collision/ffb_status")
        self.declare_parameter("output_mode", "disabled")
        self.declare_parameter("hardware_armed", False)
        self.declare_parameter("expected_source", "bird_eye")
        self.declare_parameter("max_magnitude", 0.05)
        self.declare_parameter("watchdog_timeout_sec", 0.1)
        self.declare_parameter("maximum_message_age_sec", 0.1)
        self.declare_parameter("future_tolerance_sec", 0.05)
        self.declare_parameter("watchdog_check_rate_hz", 100.0)
        self.declare_parameter("device_path", "")
        self.declare_parameter(
            "writer_lock_path", "/tmp/oit-g923-ffb-writer.lock"
        )
        self.declare_parameter("effect_duration_ms", 120)
        self.declare_parameter("effect_period_ms", 35)

        self.command_topic = str(
            self.get_parameter("command_topic").value
        )
        self.status_topic = str(self.get_parameter("status_topic").value)
        self.output_mode = validate_output_mode(
            self.get_parameter("output_mode").value,
            hardware_armed=self.get_parameter("hardware_armed").value,
        )
        configured_max_magnitude = float(
            self.get_parameter("max_magnitude").value
        )
        if (
            self.output_mode == "hardware"
            and configured_max_magnitude > INITIAL_HARDWARE_MAX_MAGNITUDE
        ):
            raise ValueError(
                "initial hardware mode requires max_magnitude <= "
                f"{INITIAL_HARDWARE_MAX_MAGNITUDE:.2f}"
            )
        watchdog_timeout = float(
            self.get_parameter("watchdog_timeout_sec").value
        )
        check_rate = float(
            self.get_parameter("watchdog_check_rate_hz").value
        )
        if not math.isfinite(check_rate) or check_rate <= 0.0:
            raise ValueError("watchdog_check_rate_hz must be finite and > 0")

        self.policy = CollisionFfbSafetyPolicy(
            expected_source=str(
                self.get_parameter("expected_source").value
            ),
            configured_max_magnitude=float(
                configured_max_magnitude
            ),
            watchdog_timeout_sec=watchdog_timeout,
            maximum_message_age_sec=float(
                self.get_parameter("maximum_message_age_sec").value
            ),
            future_tolerance_sec=float(
                self.get_parameter("future_tolerance_sec").value
            ),
        )

        self._monotonic_clock = monotonic_clock
        self._current_time_clock = current_time_clock
        self._last_source = ""
        self._last_requested_magnitude = 0.0
        self._last_log_signature = None
        self._shutdown_published = False
        self.hardware_backend = None

        if self.output_mode == "hardware":
            device_path = str(self.get_parameter("device_path").value)
            if not (
                device_path.startswith("/dev/input/by-id/")
                and device_path.endswith("-event-joystick")
            ):
                raise ValueError(
                    "hardware device_path must be a stable "
                    "/dev/input/by-id/*-event-joystick path"
                )
            self.hardware_backend = hardware_backend_factory(
                device_path,
                lock_path=str(self.get_parameter("writer_lock_path").value),
                effect_duration_ms=int(
                    self.get_parameter("effect_duration_ms").value
                ),
                period_ms=int(self.get_parameter("effect_period_ms").value),
            )

        qos = collision_command_qos()
        self.status_publisher = self.create_publisher(
            CollisionFfbStatus,
            self.status_topic,
            qos,
        )
        self.command_subscription = self.create_subscription(
            CollisionFfbCommand,
            self.command_topic,
            self._on_command,
            qos,
        )
        self.watchdog_timer = self.create_timer(
            1.0 / check_rate,
            self._check_watchdog,
        )

        self.get_logger().info(
            "Collision FFB adapter started: "
            f"mode={self.output_mode}, command={self.command_topic}, "
            f"status={self.status_topic}, watchdog={watchdog_timeout:.3f}s; "
            + (
                "hardware backend armed"
                if self.output_mode == "hardware"
                else "hardware access disabled"
            )
        )

    def _current_time_sec(self) -> float:
        if self._current_time_clock is not None:
            return float(self._current_time_clock())
        return self.get_clock().now().nanoseconds / 1e9

    @staticmethod
    def _message_time_sec(message: CollisionFfbCommand) -> float:
        return (
            float(message.header.stamp.sec)
            + float(message.header.stamp.nanosec) / 1e9
        )

    def _on_command(self, message: CollisionFfbCommand) -> None:
        requested_magnitude = float(message.normalized_magnitude)
        self._last_source = str(message.source)
        self._last_requested_magnitude = requested_magnitude

        try:
            request = CollisionFfbRequest(
                sequence=int(message.sequence),
                source=message.source,
                generated_time_sec=self._message_time_sec(message),
                risk_level=int(message.risk_level),
                pattern=int(message.pattern),
                active=bool(message.active),
                normalized_magnitude=requested_magnitude,
                reason=message.reason,
            )
            decision = self.policy.process(
                request,
                received_monotonic_sec=float(self._monotonic_clock()),
                current_time_sec=self._current_time_sec(),
            )
        except Exception as error:
            decision = self.policy.force_stop(
                f"callback_exception:{type(error).__name__}:{error}",
                fault=True,
            )

        decision = self._execute_output(decision)
        self._publish_status(
            decision,
            requested_magnitude=requested_magnitude,
            source=self._last_source,
        )

    def _check_watchdog(self) -> None:
        decision = self.policy.poll_watchdog(
            float(self._monotonic_clock())
        )
        if decision.action is OutputAction.NONE:
            return
        decision = self._execute_output(decision)
        self._publish_status(
            decision,
            requested_magnitude=self._last_requested_magnitude,
            source=self._last_source,
        )

    def _execute_output(
        self,
        decision: CollisionFfbDecision,
    ) -> CollisionFfbDecision:
        if self.output_mode != "hardware":
            return decision
        try:
            if decision.action is OutputAction.APPLY:
                self.hardware_backend.apply(
                    decision.normalized_magnitude,
                    decision.pattern,
                )
            elif decision.action is OutputAction.STOP:
                self.hardware_backend.stop()
            return decision
        except Exception as error:
            try:
                self.hardware_backend.stop()
            except Exception:
                pass
            return self.policy.force_stop(
                f"hardware_error:{type(error).__name__}:{error}",
                fault=True,
            )

    def _publish_status(
        self,
        decision: CollisionFfbDecision,
        *,
        requested_magnitude: float,
        source: str,
    ) -> None:
        status = CollisionFfbStatus()
        status.header.stamp = self.get_clock().now().to_msg()
        status.has_sequence = decision.sequence is not None
        status.sequence = (
            int(decision.sequence)
            if decision.sequence is not None
            else 0
        )
        status.source = source
        status.output_mode = self.output_mode
        status.action = decision.action.value
        status.command_active = decision.active
        status.output_active = (
            self.output_mode in {"dry_run", "hardware"}
            and decision.active
        )
        status.requested_magnitude = float(requested_magnitude)
        status.applied_magnitude = (
            float(decision.normalized_magnitude)
            if status.output_active
            else 0.0
        )
        status.pattern = int(decision.pattern)
        status.reason = decision.reason
        status.fault = decision.fault
        self.status_publisher.publish(status)
        self._log_status(status)

    def _log_status(self, status: CollisionFfbStatus) -> None:
        sequence = str(status.sequence) if status.has_sequence else "none"
        detail = (
            f"mode={status.output_mode} sequence={sequence} "
            f"action={status.action} command_active={status.command_active} "
            f"output_active={status.output_active} "
            f"requested={status.requested_magnitude:.3f} "
            f"applied={status.applied_magnitude:.3f} "
            f"pattern={status.pattern} reason={status.reason} "
            f"fault={status.fault}"
        )
        signature = (
            status.action,
            status.command_active,
            status.output_active,
            status.pattern,
            status.reason,
            status.fault,
        )
        if status.fault:
            self.get_logger().warning(detail)
        elif signature != self._last_log_signature:
            self.get_logger().info(detail)
        else:
            self.get_logger().debug(detail)
        self._last_log_signature = signature

    def destroy_node(self):
        """Publish a final inactive status before destroying ROS entities."""
        if not self._shutdown_published:
            self._shutdown_published = True
            try:
                decision = self._execute_output(
                    self.policy.force_stop("shutdown")
                )
                self._publish_status(
                    decision,
                    requested_magnitude=self._last_requested_magnitude,
                    source=self._last_source,
                )
            except Exception as error:
                self.get_logger().error(
                    "Failed to publish final inactive status: "
                    f"{type(error).__name__}: {error}"
                )
        try:
            if self.hardware_backend is not None:
                self.hardware_backend.close()
                self.hardware_backend = None
        except Exception as error:
            self.get_logger().error(
                "Failed to close hardware backend: "
                f"{type(error).__name__}: {error}"
            )
        return super().destroy_node()


def main(args=None):
    """Run the collision FFB ROS adapter."""
    rclpy.init(
        args=args,
        signal_handler_options=SignalHandlerOptions.NO,
    )
    node = None
    try:
        node = CollisionFfbNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
