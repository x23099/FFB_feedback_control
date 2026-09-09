import ast
import inspect

import pytest
import rclpy
from builtin_interfaces.msg import Time
from oit_interfaces.msg import CollisionFfbCommand
from rclpy.context import Context
from rclpy.parameter import Parameter

import oit.collision_ffb_node as collision_ffb_node_module
from oit.collision_ffb_node import (
    CollisionFfbNode,
    validate_output_mode,
)


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class FakeHardwareBackend:
    def __init__(self, device_path, **kwargs):
        self.device_path = device_path
        self.kwargs = kwargs
        self.applied = []
        self.stop_calls = 0
        self.close_calls = 0
        self.fail_apply = False

    def apply(self, magnitude, pattern):
        if self.fail_apply:
            raise OSError("synthetic hardware failure")
        self.applied.append((magnitude, pattern))

    def stop(self):
        self.stop_calls += 1

    def close(self):
        self.close_calls += 1


@pytest.fixture
def node_factory():
    resources = []

    def create(
        mode="dry_run",
        *,
        hardware_armed=False,
        initial_test_passed=False,
        max_magnitude=0.05,
    ):
        context = Context()
        rclpy.init(args=[], context=context)
        clocks = {"monotonic": 2.0, "current": 10.0}
        try:
            node = CollisionFfbNode(
                context=context,
                parameter_overrides=[
                    Parameter("output_mode", value=mode),
                    Parameter("hardware_armed", value=hardware_armed),
                    Parameter(
                        "hardware_initial_test_passed",
                        value=initial_test_passed,
                    ),
                    Parameter("max_magnitude", value=max_magnitude),
                    Parameter(
                        "device_path",
                        value=(
                            "/dev/input/by-id/"
                            "usb-Logitech_G923-event-joystick"
                        ),
                    ),
                ],
                monotonic_clock=lambda: clocks["monotonic"],
                current_time_clock=lambda: clocks["current"],
                hardware_backend_factory=FakeHardwareBackend,
            )
        except Exception:
            if context.ok():
                rclpy.shutdown(context=context)
            raise
        publisher = FakePublisher()
        node.status_publisher = publisher
        resources.append((node, context))
        return node, publisher, clocks

    yield create

    for node, context in reversed(resources):
        node.destroy_node()
        if context.ok():
            rclpy.shutdown(context=context)


def command(
    sequence,
    *,
    risk=CollisionFfbCommand.WARNING,
    pattern=CollisionFfbCommand.STEADY,
    active=True,
    magnitude=0.25,
    source="bird_eye",
):
    message = CollisionFfbCommand()
    message.header.stamp = Time(sec=10, nanosec=0)
    message.sequence = sequence
    message.source = source
    message.risk_level = risk
    message.pattern = pattern
    message.active = active
    message.normalized_magnitude = magnitude
    message.reason = "test"
    return message


def test_modes_require_independent_hardware_arm():
    assert validate_output_mode("disabled") == "disabled"
    assert validate_output_mode(" DRY_RUN ") == "dry_run"
    with pytest.raises(ValueError, match="hardware_armed"):
        validate_output_mode("hardware")
    assert validate_output_mode("hardware", hardware_armed=True) == "hardware"
    with pytest.raises(ValueError, match="unknown"):
        validate_output_mode("unexpected")


def test_phase2_module_has_no_evdev_or_device_write_symbols():
    source = inspect.getsource(collision_ffb_node_module)
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for item in ast.walk(tree)
        if isinstance(item, (ast.Import, ast.ImportFrom))
        for alias in item.names
    }

    assert "evdev" not in imported_roots
    assert "InputDevice" not in source
    assert "upload_effect" not in source


def test_dry_run_replays_clear_warning_hold_clear(node_factory):
    node, publisher, _clocks = node_factory()

    node._on_command(command(
        1,
        risk=CollisionFfbCommand.CLEAR,
        pattern=CollisionFfbCommand.OFF,
        active=False,
        magnitude=0.0,
    ))
    node._on_command(command(2))
    node._on_command(command(
        3,
        risk=CollisionFfbCommand.WARNING_HOLD,
        pattern=CollisionFfbCommand.STEADY_HOLD,
    ))
    node._on_command(command(
        4,
        risk=CollisionFfbCommand.CLEAR,
        pattern=CollisionFfbCommand.OFF,
        active=False,
        magnitude=0.0,
    ))

    statuses = publisher.messages
    assert [item.action for item in statuses] == [
        "none",
        "apply",
        "apply",
        "stop",
    ]
    assert [item.output_active for item in statuses] == [
        False,
        True,
        True,
        False,
    ]
    assert statuses[1].requested_magnitude == pytest.approx(0.25)
    assert statuses[1].applied_magnitude == pytest.approx(0.05)
    assert statuses[2].pattern == CollisionFfbCommand.STEADY_HOLD
    assert statuses[3].reason == "inactive:clear"


def test_disabled_mode_never_marks_physical_output_active(node_factory):
    node, publisher, _clocks = node_factory(mode="disabled")

    node._on_command(command(1))

    status = publisher.messages[-1]
    assert status.command_active
    assert not status.output_active
    assert status.applied_magnitude == 0.0
    assert status.output_mode == "disabled"


def test_hardware_mode_uses_fake_backend_with_initial_cap(node_factory):
    node, publisher, _clocks = node_factory(
        mode="hardware",
        hardware_armed=True,
        max_magnitude=0.03,
    )

    node._on_command(command(1, magnitude=0.25))
    node._on_command(command(
        2,
        risk=CollisionFfbCommand.CLEAR,
        pattern=CollisionFfbCommand.OFF,
        active=False,
        magnitude=0.0,
    ))

    backend = node.hardware_backend
    assert len(backend.applied) == 1
    assert backend.applied[0][0] == pytest.approx(0.03)
    assert backend.stop_calls == 1
    assert publisher.messages[0].output_active
    assert publisher.messages[0].applied_magnitude == pytest.approx(0.03)
    assert not publisher.messages[1].output_active


def test_hardware_backend_failure_is_reported_and_stopped(node_factory):
    node, publisher, _clocks = node_factory(
        mode="hardware",
        hardware_armed=True,
        max_magnitude=0.03,
    )
    node.hardware_backend.fail_apply = True

    node._on_command(command(1))

    status = publisher.messages[-1]
    assert status.fault
    assert not status.output_active
    assert status.applied_magnitude == 0.0
    assert "hardware_error:OSError" in status.reason
    assert node.hardware_backend.stop_calls == 1


def test_initial_hardware_mode_rejects_cap_above_limit(node_factory):
    with pytest.raises(ValueError, match="initial_test_passed"):
        node_factory(
            mode="hardware",
            hardware_armed=True,
            max_magnitude=0.05,
        )


def test_verified_hardware_mode_allows_point_zero_five(node_factory):
    node, publisher, _clocks = node_factory(
        mode="hardware",
        hardware_armed=True,
        initial_test_passed=True,
        max_magnitude=0.05,
    )

    node._on_command(command(1, magnitude=0.25))

    assert node.hardware_backend.applied[0][0] == pytest.approx(0.05)
    assert publisher.messages[-1].applied_magnitude == pytest.approx(0.05)


def test_verified_hardware_mode_rejects_cap_above_point_zero_five(
    node_factory,
):
    with pytest.raises(ValueError, match="max_magnitude <= 0.05"):
        node_factory(
            mode="hardware",
            hardware_armed=True,
            initial_test_passed=True,
            max_magnitude=0.051,
        )


def test_watchdog_publishes_exactly_one_stop(node_factory):
    node, publisher, clocks = node_factory()
    node._on_command(command(1))

    clocks["monotonic"] = 2.1
    node._check_watchdog()
    clocks["monotonic"] = 2.2
    node._check_watchdog()

    assert len(publisher.messages) == 2
    status = publisher.messages[-1]
    assert status.action == "stop"
    assert not status.output_active
    assert status.reason == "watchdog_timeout"
    assert status.fault


def test_invalid_message_fails_closed(node_factory):
    node, publisher, _clocks = node_factory()

    node._on_command(command(1, source="unexpected"))

    status = publisher.messages[-1]
    assert status.action == "stop"
    assert not status.command_active
    assert not status.output_active
    assert status.fault
    assert "unexpected_source" in status.reason


def test_callback_exception_fails_closed(node_factory):
    node, publisher, _clocks = node_factory()

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    node.policy.process = raise_error
    node._on_command(command(1))

    status = publisher.messages[-1]
    assert status.action == "stop"
    assert not status.output_active
    assert status.fault
    assert "callback_exception:RuntimeError" in status.reason


def test_destroy_publishes_final_inactive_status_once(node_factory):
    node, publisher, _clocks = node_factory()
    node._on_command(command(1))

    node.destroy_node()
    node.destroy_node()

    shutdown_statuses = [
        item for item in publisher.messages
        if item.reason == "shutdown"
    ]
    assert len(shutdown_statuses) == 1
    assert shutdown_statuses[0].action == "stop"
    assert not shutdown_statuses[0].output_active
