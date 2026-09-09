from types import SimpleNamespace

import pytest

from oit.collision_ffb_backend import (
    CollisionFfbBackendError,
    EvdevCollisionFfbBackend,
    FfbWriterLock,
    normalized_to_evdev_magnitude,
)
from oit.collision_ffb_policy import FeedbackPattern


class FakeStruct:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class FakeFf:
    Envelope = FakeStruct
    Periodic = FakeStruct
    Effect = FakeStruct
    Trigger = FakeStruct
    Replay = FakeStruct
    EffectType = FakeStruct


class FakeEcodes:
    EV_FF = 21
    FF_PERIODIC = 81
    FF_SINE = 90
    FF_SQUARE = 88


class FakeDevice:
    def __init__(
        self,
        path,
        *,
        effects=None,
        effect_count=16,
        fail_upload=False,
        fail_play=False,
        fail_stop=False,
        fail_erase=False,
        returned_effect_id=7,
    ):
        self.path = path
        self.effects = (
            [FakeEcodes.FF_PERIODIC, FakeEcodes.FF_SINE]
            if effects is None
            else effects
        )
        self.ff_effects_count = effect_count
        self.fail_upload = fail_upload
        self.fail_play = fail_play
        self.fail_stop = fail_stop
        self.fail_erase = fail_erase
        self.returned_effect_id = returned_effect_id
        self.uploaded = []
        self.writes = []
        self.erased = []
        self.closed = False

    def capabilities(self):
        return {FakeEcodes.EV_FF: self.effects}

    def upload_effect(self, effect):
        self.uploaded.append(effect)
        if self.fail_upload:
            raise OSError("upload failed")
        requested_id = effect.args[1]
        return requested_id if requested_id >= 0 else self.returned_effect_id

    def write(self, event_type, effect_id, value):
        self.writes.append((event_type, effect_id, value))
        if value == 1 and self.fail_play:
            raise OSError("play failed")
        if value == 0 and self.fail_stop:
            raise OSError("stop failed")

    def erase_effect(self, effect_id):
        self.erased.append(effect_id)
        if self.fail_erase:
            raise OSError("erase failed")

    def close(self):
        self.closed = True


def backend_for(device, lock_path, **kwargs):
    return EvdevCollisionFfbBackend(
        "/dev/input/fake-g923",
        lock_path=lock_path,
        input_device_factory=lambda _path: device,
        ecodes_module=FakeEcodes,
        ff_module=FakeFf,
        **kwargs,
    )


def test_construction_checks_capability_without_writing(tmp_path):
    device = FakeDevice("fake")

    backend = backend_for(device, tmp_path / "writer.lock")

    assert device.uploaded == []
    assert device.writes == []
    assert backend.effect_id is None
    backend.close()
    assert device.closed


@pytest.mark.parametrize(
    "effects,effect_count,expected",
    [
        ([FakeEcodes.FF_SINE], 16, "FF_PERIODIC"),
        ([FakeEcodes.FF_PERIODIC], 16, "FF_SINE"),
        ([FakeEcodes.FF_PERIODIC, FakeEcodes.FF_SINE], 0, "effect slots"),
    ],
)
def test_missing_capability_fails_before_upload(
    tmp_path,
    effects,
    effect_count,
    expected,
):
    device = FakeDevice("fake", effects=effects, effect_count=effect_count)

    with pytest.raises(CollisionFfbBackendError, match=expected):
        backend_for(device, tmp_path / "writer.lock")

    assert device.uploaded == []
    assert device.writes == []
    assert device.closed


def test_apply_refreshes_one_finite_effect_slot(tmp_path):
    device = FakeDevice("fake")
    backend = backend_for(device, tmp_path / "writer.lock")

    backend.apply(0.03, FeedbackPattern.STEADY)
    backend.apply(0.05, FeedbackPattern.STEADY_HOLD)

    assert backend.effect_id == 7
    assert [effect.args[1] for effect in device.uploaded] == [-1, 7]
    assert device.writes == [
        (FakeEcodes.EV_FF, 7, 1),
        (FakeEcodes.EV_FF, 7, 1),
    ]
    for effect in device.uploaded:
        replay = effect.args[4]
        assert replay.args[0] == 120
    periodic = device.uploaded[-1].args[5].kwargs["ff_periodic_effect"]
    assert periodic.args[2] == normalized_to_evdev_magnitude(0.05)
    backend.close()


def test_stop_erases_effect_and_is_idempotent(tmp_path):
    device = FakeDevice("fake")
    backend = backend_for(device, tmp_path / "writer.lock")
    backend.apply(0.03, FeedbackPattern.STEADY)

    backend.stop()
    backend.stop()

    assert device.writes[-1] == (FakeEcodes.EV_FF, 7, 0)
    assert device.erased == [7]
    assert backend.effect_id is None
    backend.close()


def test_play_failure_still_stops_and_erases(tmp_path):
    device = FakeDevice("fake", fail_play=True)
    backend = backend_for(device, tmp_path / "writer.lock")

    with pytest.raises(CollisionFfbBackendError, match="failed to apply"):
        backend.apply(0.03, FeedbackPattern.STEADY)

    assert device.writes[-1] == (FakeEcodes.EV_FF, 7, 0)
    assert device.erased == [7]
    assert backend.effect_id is None
    backend.close()


def test_close_attempts_erase_and_unlocks_after_stop_failure(tmp_path):
    lock_path = tmp_path / "writer.lock"
    device = FakeDevice("fake", fail_stop=True)
    backend = backend_for(device, lock_path)
    backend.apply(0.03, FeedbackPattern.STEADY)

    with pytest.raises(CollisionFfbBackendError, match="stop effect"):
        backend.close()

    assert device.erased == [7]
    assert device.closed
    replacement = FfbWriterLock(lock_path)
    replacement.acquire()
    replacement.release()


def test_writer_lock_rejects_a_second_owner(tmp_path):
    lock_path = tmp_path / "writer.lock"
    first = FfbWriterLock(lock_path)
    second = FfbWriterLock(lock_path)
    first.acquire()

    with pytest.raises(CollisionFfbBackendError, match="another"):
        second.acquire()

    first.release()
    second.acquire()
    second.release()


@pytest.mark.parametrize("value", [0.0, -0.1, 0.251, float("nan")])
def test_magnitude_conversion_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        normalized_to_evdev_magnitude(value)


def test_invalid_effect_lifetime_is_rejected_before_device_open(tmp_path):
    called = SimpleNamespace(value=False)

    def factory(_path):
        called.value = True
        return FakeDevice("fake")

    with pytest.raises(ValueError, match="effect_duration_ms"):
        EvdevCollisionFfbBackend(
            "/dev/input/fake-g923",
            lock_path=tmp_path / "writer.lock",
            effect_duration_ms=121,
            input_device_factory=factory,
            ecodes_module=FakeEcodes,
            ff_module=FakeFf,
        )

    assert not called.value
