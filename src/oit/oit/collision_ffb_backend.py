"""Hardware backend primitives for collision-warning force feedback.

The ROS adapter does not instantiate this module yet.  Tests inject fake evdev
objects, so importing and testing this module never opens an input device.
"""

from __future__ import annotations

import fcntl
import math
import os
import stat
from pathlib import Path
from typing import Optional

from oit.collision_ffb_policy import (
    ABSOLUTE_MAX_NORMALIZED_MAGNITUDE,
    FeedbackPattern,
)


DEFAULT_LOCK_PATH = Path("/tmp/oit-g923-ffb-writer.lock")
DEFAULT_EFFECT_DURATION_MS = 120
DEFAULT_PERIOD_MS = 35
MAX_EFFECT_DURATION_MS = 120
FF_MAGNITUDE_MAX = 0x7FFF


class CollisionFfbBackendError(RuntimeError):
    """Report a hardware preparation or lifecycle failure."""


class FfbWriterLock:
    """Hold a non-blocking process lock for one FFB writer."""

    def __init__(self, path=DEFAULT_LOCK_PATH):
        """Store the lock path without creating or locking it."""
        self.path = Path(path)
        self._fd: Optional[int] = None

    @property
    def acquired(self) -> bool:
        """Return whether this object currently owns the lock."""
        return self._fd is not None

    def acquire(self) -> None:
        """Acquire the writer lock or fail without waiting."""
        if self.acquired:
            return
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(self.path, flags, 0o600)
        except OSError as error:
            raise CollisionFfbBackendError(
                f"cannot open FFB writer lock {self.path}: {error}"
            ) from error
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise CollisionFfbBackendError(
                    f"FFB writer lock is not a regular file: {self.path}"
                )
            if metadata.st_uid != os.getuid():
                raise CollisionFfbBackendError(
                    f"FFB writer lock has unexpected owner: {self.path}"
                )
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, CollisionFfbBackendError) as error:
            os.close(fd)
            if isinstance(error, CollisionFfbBackendError):
                raise
            raise CollisionFfbBackendError(
                "another force-feedback writer already owns "
                f"{self.path}"
            ) from error
        self._fd = fd

    def release(self) -> None:
        """Release the writer lock if held."""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self):
        """Acquire and return this lock for a context manager."""
        self.acquire()
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        """Release this lock when leaving a context manager."""
        self.release()


def normalized_to_evdev_magnitude(value: float) -> int:
    """Convert a validated normalized magnitude to Linux FF amplitude."""
    normalized = float(value)
    if (
        not math.isfinite(normalized)
        or normalized <= 0.0
        or normalized > ABSOLUTE_MAX_NORMALIZED_MAGNITUDE
    ):
        raise ValueError(
            "normalized magnitude must be finite and within "
            f"(0, {ABSOLUTE_MAX_NORMALIZED_MAGNITUDE}]"
        )
    return max(1, min(FF_MAGNITUDE_MAX, round(normalized * FF_MAGNITUDE_MAX)))


def build_periodic_effect(
    ff_module,
    ecodes_module,
    *,
    effect_id: int,
    pattern: FeedbackPattern,
    normalized_magnitude: float,
    period_ms: int,
    duration_ms: int,
):
    """Build one finite periodic effect without touching a device."""
    try:
        pattern = FeedbackPattern(pattern)
    except (TypeError, ValueError) as error:
        raise ValueError(f"unsupported feedback pattern: {pattern}") from error
    if pattern not in {
        FeedbackPattern.STEADY,
        FeedbackPattern.STEADY_HOLD,
        FeedbackPattern.PULSE,
    }:
        raise ValueError(
            f"inactive feedback pattern cannot be played: {pattern}"
        )
    period_ms = int(period_ms)
    duration_ms = int(duration_ms)
    if period_ms <= 0:
        raise ValueError("period_ms must be positive")
    if not 1 <= duration_ms <= MAX_EFFECT_DURATION_MS:
        raise ValueError(
            f"duration_ms must be within 1..{MAX_EFFECT_DURATION_MS}"
        )
    magnitude = normalized_to_evdev_magnitude(normalized_magnitude)
    # G923 testing showed that a 0.05/35 ms sine was not perceptible while
    # the same bounded square waveform was.  Use the verified waveform for
    # every active pattern; warning cadence can be tuned separately.
    waveform = ecodes_module.FF_SQUARE
    envelope = ff_module.Envelope(0, 0, 0, 0)
    periodic = ff_module.Periodic(
        waveform,
        period_ms,
        magnitude,
        0,
        0,
        envelope,
        0,
        None,
    )
    return ff_module.Effect(
        ecodes_module.FF_PERIODIC,
        int(effect_id),
        0x4000,
        ff_module.Trigger(0, 0),
        ff_module.Replay(duration_ms, 0),
        ff_module.EffectType(ff_periodic_effect=periodic),
    )


class EvdevCollisionFfbBackend:
    """Own one finite periodic effect and its exclusive writer lock."""

    def __init__(
        self,
        device_path: str,
        *,
        lock_path=DEFAULT_LOCK_PATH,
        effect_duration_ms=DEFAULT_EFFECT_DURATION_MS,
        period_ms=DEFAULT_PERIOD_MS,
        input_device_factory=None,
        ecodes_module=None,
        ff_module=None,
    ):
        """Open and validate without uploading or playing an effect."""
        self.device_path = str(device_path).strip()
        if not self.device_path:
            raise ValueError("device_path must not be empty")
        self.effect_duration_ms = int(effect_duration_ms)
        self.period_ms = int(period_ms)
        if not 1 <= self.effect_duration_ms <= MAX_EFFECT_DURATION_MS:
            raise ValueError(
                "effect_duration_ms must be within "
                f"1..{MAX_EFFECT_DURATION_MS}"
            )
        if self.period_ms <= 0:
            raise ValueError("period_ms must be positive")

        if (
            input_device_factory is None
            or ecodes_module is None
            or ff_module is None
        ):
            try:
                from evdev import InputDevice, ecodes, ff
            except ImportError as error:
                raise CollisionFfbBackendError(
                    "python3-evdev is required for the hardware backend"
                ) from error
            input_device_factory = input_device_factory or InputDevice
            ecodes_module = ecodes_module or ecodes
            ff_module = ff_module or ff

        self._ecodes = ecodes_module
        self._ff = ff_module
        self._lock = FfbWriterLock(lock_path)
        self._device = None
        self._effect_id: Optional[int] = None
        self._closed = False
        self._lock.acquire()
        try:
            self._device = input_device_factory(self.device_path)
            self._validate_capabilities()
        except Exception:
            if self._device is not None:
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None
            self._lock.release()
            raise

    @property
    def effect_id(self) -> Optional[int]:
        """Return the currently owned effect slot, if any."""
        return self._effect_id

    def _validate_capabilities(self) -> None:
        effects = self._device.capabilities().get(self._ecodes.EV_FF, [])
        if self._ecodes.FF_PERIODIC not in effects:
            raise CollisionFfbBackendError(
                "device does not support FF_PERIODIC"
            )
        if self._ecodes.FF_SQUARE not in effects:
            raise CollisionFfbBackendError("device does not support FF_SQUARE")
        if int(self._device.ff_effects_count) < 1:
            raise CollisionFfbBackendError(
                "device reports no effect slots"
            )

    def apply(
        self,
        normalized_magnitude: float,
        pattern: FeedbackPattern,
    ) -> None:
        """Upload or refresh one finite effect, then play it once."""
        if self._closed or self._device is None:
            raise CollisionFfbBackendError("hardware backend is closed")
        requested_id = self._effect_id if self._effect_id is not None else -1
        effect = build_periodic_effect(
            self._ff,
            self._ecodes,
            effect_id=requested_id,
            pattern=pattern,
            normalized_magnitude=normalized_magnitude,
            period_ms=self.period_ms,
            duration_ms=self.effect_duration_ms,
        )
        try:
            updated_id = self._device.upload_effect(effect)
            if not isinstance(updated_id, int) or updated_id < 0:
                raise CollisionFfbBackendError(
                    f"device returned invalid effect id: {updated_id!r}"
                )
            if self._effect_id is not None and updated_id != self._effect_id:
                self._best_effort_stop_and_erase(extra_effect_id=updated_id)
                raise CollisionFfbBackendError(
                    "effect update unexpectedly allocated a different slot"
                )
            self._effect_id = updated_id
            self._device.write(self._ecodes.EV_FF, self._effect_id, 1)
        except Exception as error:
            self._best_effort_stop_and_erase()
            if isinstance(error, CollisionFfbBackendError):
                raise
            raise CollisionFfbBackendError(
                f"failed to apply collision FFB effect: {error}"
            ) from error

    def _best_effort_stop_and_erase(self, extra_effect_id=None) -> list[str]:
        errors = []
        effect_ids = []
        if self._effect_id is not None:
            effect_ids.append(self._effect_id)
        if extra_effect_id is not None and extra_effect_id not in effect_ids:
            effect_ids.append(extra_effect_id)
        self._effect_id = None
        for effect_id in effect_ids:
            try:
                self._device.write(self._ecodes.EV_FF, effect_id, 0)
            except Exception as error:
                errors.append(f"stop effect {effect_id}: {error}")
            try:
                self._device.erase_effect(effect_id)
            except Exception as error:
                errors.append(f"erase effect {effect_id}: {error}")
        return errors

    def stop(self) -> None:
        """Stop and erase the owned effect; repeated calls are safe."""
        if self._device is None or self._effect_id is None:
            return
        errors = self._best_effort_stop_and_erase()
        if errors:
            raise CollisionFfbBackendError("; ".join(errors))

    def close(self) -> None:
        """Attempt stop, erase, close, and unlock even after failures."""
        if self._closed:
            return
        self._closed = True
        errors = []
        if self._device is not None:
            errors.extend(self._best_effort_stop_and_erase())
            try:
                self._device.close()
            except Exception as error:
                errors.append(f"close device: {error}")
            self._device = None
        self._lock.release()
        if errors:
            raise CollisionFfbBackendError("; ".join(errors))
