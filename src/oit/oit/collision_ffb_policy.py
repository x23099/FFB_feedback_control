"""
Pure safety policy for collision-warning force-feedback requests.

This module deliberately has no ROS or evdev dependency.  It validates the
semantic command produced by perception and returns an abstract action for a
future hardware adapter.  Invalid, stale, or missing commands fail closed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional


ABSOLUTE_MAX_NORMALIZED_MAGNITUDE = 0.25
UINT64_MAX = (1 << 64) - 1


class RiskLevel(IntEnum):
    """Values mirrored by ``oit_interfaces/CollisionFfbCommand``."""

    CLEAR = 0
    PATH = 1
    WARNING = 2
    WARNING_HOLD = 3
    CRITICAL = 4
    UNKNOWN = 5


class FeedbackPattern(IntEnum):
    """Values mirrored by ``oit_interfaces/CollisionFfbCommand``."""

    OFF = 0
    STEADY = 1
    STEADY_HOLD = 2
    PULSE = 3


class OutputAction(str, Enum):
    """Action requested from the future device backend."""

    NONE = "none"
    APPLY = "apply"
    STOP = "stop"


@dataclass(frozen=True)
class CollisionFfbRequest:
    """Device-independent command received from perception."""

    sequence: int
    source: str
    generated_time_sec: float
    risk_level: int
    pattern: int
    active: bool
    normalized_magnitude: float
    reason: str = ""


@dataclass(frozen=True)
class CollisionFfbDecision:
    """Validated action emitted by :class:`CollisionFfbSafetyPolicy`."""

    action: OutputAction
    active: bool
    normalized_magnitude: float
    pattern: FeedbackPattern
    reason: str
    sequence: Optional[int]
    fault: bool = False


_EXPECTED_STATE = {
    RiskLevel.CLEAR: (False, FeedbackPattern.OFF),
    RiskLevel.PATH: (False, FeedbackPattern.OFF),
    RiskLevel.WARNING: (True, FeedbackPattern.STEADY),
    RiskLevel.WARNING_HOLD: (True, FeedbackPattern.STEADY_HOLD),
    RiskLevel.CRITICAL: (True, FeedbackPattern.STEADY),
    RiskLevel.UNKNOWN: (True, FeedbackPattern.PULSE),
}


class CollisionFfbSafetyPolicy:
    """Validate commands, clamp magnitude, and enforce a monotonic watchdog."""

    def __init__(
        self,
        *,
        expected_source: str = "bird_eye",
        configured_max_magnitude: float = 0.05,
        watchdog_timeout_sec: float = 0.1,
        maximum_message_age_sec: float = 0.1,
        future_tolerance_sec: float = 0.05,
        timestamp_age_check_enabled: bool = True,
    ):
        """Initialize safety limits and reset the command-stream state."""
        if not expected_source or not expected_source.strip():
            raise ValueError("expected_source must not be empty")
        self.expected_source = expected_source.strip()
        self.configured_max_magnitude = self._finite_nonnegative(
            configured_max_magnitude,
            "configured_max_magnitude",
        )
        if self.configured_max_magnitude > 1.0:
            raise ValueError("configured_max_magnitude must be <= 1")
        self.watchdog_timeout_sec = self._finite_positive(
            watchdog_timeout_sec,
            "watchdog_timeout_sec",
        )
        self.maximum_message_age_sec = self._finite_positive(
            maximum_message_age_sec,
            "maximum_message_age_sec",
        )
        self.future_tolerance_sec = self._finite_nonnegative(
            future_tolerance_sec,
            "future_tolerance_sec",
        )
        self.timestamp_age_check_enabled = bool(timestamp_age_check_enabled)

        self._active = False
        self._last_sequence: Optional[int] = None
        self._last_generated_time_sec: Optional[float] = None
        self._last_valid_received_monotonic_sec: Optional[float] = None

    @staticmethod
    def _finite_positive(value: float, name: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed) or parsed <= 0.0:
            raise ValueError(f"{name} must be finite and > 0")
        return parsed

    @staticmethod
    def _finite_nonnegative(value: float, name: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < 0.0:
            raise ValueError(f"{name} must be finite and >= 0")
        return parsed

    @property
    def active(self) -> bool:
        """Return whether the most recent valid request is active."""
        return self._active

    @property
    def last_sequence(self) -> Optional[int]:
        """Return the latest accepted sequence number, if any."""
        return self._last_sequence

    def process(
        self,
        request: CollisionFfbRequest,
        *,
        received_monotonic_sec: float,
        current_time_sec: float,
    ) -> CollisionFfbDecision:
        """Validate one request and return a device-independent action."""
        try:
            received_monotonic_sec = self._finite_nonnegative(
                received_monotonic_sec,
                "received_monotonic_sec",
            )
            current_time_sec = self._finite_nonnegative(
                current_time_sec,
                "current_time_sec",
            )
            risk_level, pattern = self._validate_request(
                request,
                received_monotonic_sec=received_monotonic_sec,
                current_time_sec=current_time_sec,
            )
        except (TypeError, ValueError) as error:
            return self._invalid_decision(str(error), request)

        was_active = self._active
        self._last_sequence = int(request.sequence)
        self._last_generated_time_sec = float(request.generated_time_sec)
        self._last_valid_received_monotonic_sec = received_monotonic_sec

        expected_active, _expected_pattern = _EXPECTED_STATE[risk_level]
        if not expected_active:
            self._active = False
            return CollisionFfbDecision(
                action=OutputAction.STOP if was_active else OutputAction.NONE,
                active=False,
                normalized_magnitude=0.0,
                pattern=FeedbackPattern.OFF,
                reason=f"inactive:{risk_level.name.lower()}",
                sequence=int(request.sequence),
            )

        magnitude = min(
            float(request.normalized_magnitude),
            self.configured_max_magnitude,
            ABSOLUTE_MAX_NORMALIZED_MAGNITUDE,
        )
        self._active = True
        return CollisionFfbDecision(
            action=OutputAction.APPLY,
            active=True,
            normalized_magnitude=magnitude,
            pattern=pattern,
            reason=str(request.reason or risk_level.name.lower()),
            sequence=int(request.sequence),
        )

    def poll_watchdog(self, now_monotonic_sec: float) -> CollisionFfbDecision:
        """Stop an active request once its monotonic age reaches timeout."""
        try:
            now = self._finite_nonnegative(
                now_monotonic_sec,
                "now_monotonic_sec",
            )
        except ValueError as error:
            return self._force_stop(
                f"invalid_watchdog_time:{error}",
                fault=True,
            )

        if not self._active or self._last_valid_received_monotonic_sec is None:
            return self._no_action("watchdog_inactive")

        age = now - self._last_valid_received_monotonic_sec
        if age < 0.0:
            return self._force_stop(
                "monotonic_time_moved_backwards",
                fault=True,
            )
        if age < self.watchdog_timeout_sec:
            return self._no_action("watchdog_fresh")
        return self._force_stop("watchdog_timeout", fault=True)

    def force_stop(
        self,
        reason: str,
        *,
        fault: bool = False,
    ) -> CollisionFfbDecision:
        """Clear the active state and return an explicit STOP decision."""
        return self._force_stop(str(reason), fault=fault)

    def reject_request(
        self, request: CollisionFfbRequest, reason: str
    ) -> CollisionFfbDecision:
        """Fail closed while retaining the rejected command's sequence in status."""
        return self._invalid_decision(str(reason), request)

    def _validate_request(
        self,
        request: CollisionFfbRequest,
        *,
        received_monotonic_sec: float,
        current_time_sec: float,
    ) -> tuple[RiskLevel, FeedbackPattern]:
        source = str(request.source or "").strip()
        if source != self.expected_source:
            raise ValueError(
                f"unexpected_source:{source or 'empty'}"
            )

        if isinstance(request.sequence, bool):
            raise ValueError("sequence_must_be_uint64")
        sequence = int(request.sequence)
        if sequence != request.sequence or not 0 <= sequence <= UINT64_MAX:
            raise ValueError("sequence_must_be_uint64")

        generated = float(request.generated_time_sec)
        if not math.isfinite(generated) or generated < 0.0:
            raise ValueError("generated_time_must_be_finite_and_nonnegative")
        if self.timestamp_age_check_enabled:
            age = current_time_sec - generated
            if age > self.maximum_message_age_sec:
                raise ValueError(f"stale_message:age={age:.6f}")
            if age < -self.future_tolerance_sec:
                raise ValueError(f"future_message:age={age:.6f}")

        if self._last_sequence is not None and sequence <= self._last_sequence:
            if not self._can_reset_sequence(
                sequence=sequence,
                generated_time_sec=generated,
                received_monotonic_sec=received_monotonic_sec,
            ):
                raise ValueError(
                    "non_increasing_sequence:"
                    f"{sequence}<={self._last_sequence}"
                )

        try:
            risk_level = RiskLevel(request.risk_level)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"unknown_risk_level:{request.risk_level}"
            ) from error
        try:
            pattern = FeedbackPattern(request.pattern)
        except (TypeError, ValueError) as error:
            raise ValueError(f"unknown_pattern:{request.pattern}") from error

        expected_active, expected_pattern = _EXPECTED_STATE[risk_level]
        if bool(request.active) is not expected_active:
            raise ValueError(
                f"active_mismatch:{risk_level.name.lower()}"
            )
        if pattern is not expected_pattern:
            raise ValueError(
                "pattern_mismatch:"
                f"{risk_level.name.lower()}:{pattern.name.lower()}"
            )

        magnitude = float(request.normalized_magnitude)
        if not math.isfinite(magnitude) or not 0.0 <= magnitude <= 1.0:
            raise ValueError("normalized_magnitude_must_be_between_0_and_1")
        if expected_active and magnitude <= 0.0:
            raise ValueError("active_request_requires_positive_magnitude")
        if not expected_active and magnitude != 0.0:
            raise ValueError("inactive_request_requires_zero_magnitude")
        return risk_level, pattern

    def _can_reset_sequence(
        self,
        *,
        sequence: int,
        generated_time_sec: float,
        received_monotonic_sec: float,
    ) -> bool:
        del sequence
        if self._last_valid_received_monotonic_sec is None:
            return False
        if self._last_generated_time_sec is None:
            return False
        gap = received_monotonic_sec - self._last_valid_received_monotonic_sec
        return (
            gap >= self.watchdog_timeout_sec
            and generated_time_sec > self._last_generated_time_sec
        )

    def _invalid_decision(
        self,
        reason: str,
        request: CollisionFfbRequest,
    ) -> CollisionFfbDecision:
        self._active = False
        sequence = getattr(request, "sequence", None)
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or not 0 <= sequence <= UINT64_MAX
        ):
            sequence = None
        return CollisionFfbDecision(
            action=OutputAction.STOP,
            active=False,
            normalized_magnitude=0.0,
            pattern=FeedbackPattern.OFF,
            reason=f"invalid_request:{reason}",
            sequence=sequence,
            fault=True,
        )

    def _force_stop(self, reason: str, *, fault: bool) -> CollisionFfbDecision:
        self._active = False
        return CollisionFfbDecision(
            action=OutputAction.STOP,
            active=False,
            normalized_magnitude=0.0,
            pattern=FeedbackPattern.OFF,
            reason=reason,
            sequence=self._last_sequence,
            fault=fault,
        )

    def _no_action(self, reason: str) -> CollisionFfbDecision:
        return CollisionFfbDecision(
            action=OutputAction.NONE,
            active=self._active,
            normalized_magnitude=0.0,
            pattern=FeedbackPattern.OFF,
            reason=reason,
            sequence=self._last_sequence,
        )
