import math

import pytest

from oit.collision_ffb_policy import (
    ABSOLUTE_MAX_NORMALIZED_MAGNITUDE,
    CollisionFfbRequest,
    CollisionFfbSafetyPolicy,
    FeedbackPattern,
    OutputAction,
    RiskLevel,
)


def request(
    sequence=1,
    *,
    generated=10.0,
    risk=RiskLevel.WARNING,
    pattern=FeedbackPattern.STEADY,
    active=True,
    magnitude=0.25,
    source="bird_eye",
):
    return CollisionFfbRequest(
        sequence=sequence,
        source=source,
        generated_time_sec=generated,
        risk_level=risk,
        pattern=pattern,
        active=active,
        normalized_magnitude=magnitude,
        reason="test",
    )


def process(policy, item, *, monotonic=2.0, now=10.01):
    return policy.process(
        item,
        received_monotonic_sec=monotonic,
        current_time_sec=now,
    )


def test_warning_is_clamped_to_configured_limit():
    policy = CollisionFfbSafetyPolicy(configured_max_magnitude=0.05)
    decision = process(policy, request())

    assert decision.action is OutputAction.APPLY
    assert decision.active
    assert decision.normalized_magnitude == pytest.approx(0.05)
    assert decision.pattern is FeedbackPattern.STEADY
    assert not decision.fault


def test_absolute_limit_cannot_be_bypassed_by_configuration():
    policy = CollisionFfbSafetyPolicy(configured_max_magnitude=1.0)
    decision = process(policy, request(magnitude=1.0))

    assert decision.normalized_magnitude == ABSOLUTE_MAX_NORMALIZED_MAGNITUDE


@pytest.mark.parametrize(
    "risk,pattern",
    [
        (RiskLevel.WARNING_HOLD, FeedbackPattern.STEADY_HOLD),
        (RiskLevel.CRITICAL, FeedbackPattern.STEADY),
        (RiskLevel.UNKNOWN, FeedbackPattern.PULSE),
    ],
)
def test_active_state_patterns_are_accepted(risk, pattern):
    policy = CollisionFfbSafetyPolicy()
    decision = process(policy, request(risk=risk, pattern=pattern))

    assert decision.action is OutputAction.APPLY
    assert decision.pattern is pattern


@pytest.mark.parametrize("risk", [RiskLevel.CLEAR, RiskLevel.PATH])
def test_inactive_state_stops_only_on_transition(risk):
    policy = CollisionFfbSafetyPolicy()
    process(policy, request(sequence=1))

    first = process(
        policy,
        request(
            sequence=2,
            risk=risk,
            pattern=FeedbackPattern.OFF,
            active=False,
            magnitude=0.0,
        ),
        monotonic=2.02,
    )
    second = process(
        policy,
        request(
            sequence=3,
            risk=risk,
            pattern=FeedbackPattern.OFF,
            active=False,
            magnitude=0.0,
        ),
        monotonic=2.04,
    )

    assert first.action is OutputAction.STOP
    assert second.action is OutputAction.NONE


@pytest.mark.parametrize("magnitude", [math.nan, math.inf, -0.1, 1.1])
def test_invalid_magnitude_fails_closed(magnitude):
    policy = CollisionFfbSafetyPolicy()
    decision = process(policy, request(magnitude=magnitude))

    assert decision.action is OutputAction.STOP
    assert decision.fault
    assert not decision.active


@pytest.mark.parametrize(
    "changes",
    [
        {"risk": 99},
        {"pattern": 99},
        {"active": False},
        {"pattern": FeedbackPattern.PULSE},
        {"source": "unexpected"},
    ],
)
def test_semantically_invalid_request_fails_closed(changes):
    policy = CollisionFfbSafetyPolicy()
    decision = process(policy, request(**changes))

    assert decision.action is OutputAction.STOP
    assert decision.fault


def test_inactive_request_requires_zero_magnitude():
    policy = CollisionFfbSafetyPolicy()
    decision = process(
        policy,
        request(
            risk=RiskLevel.CLEAR,
            pattern=FeedbackPattern.OFF,
            active=False,
            magnitude=0.01,
        ),
    )

    assert decision.action is OutputAction.STOP
    assert decision.fault


@pytest.mark.parametrize("sequence", [-1, 1 << 64, True, 1.5])
def test_sequence_must_be_uint64(sequence):
    policy = CollisionFfbSafetyPolicy()
    decision = process(policy, request(sequence=sequence))

    assert decision.action is OutputAction.STOP
    assert decision.fault


def test_duplicate_and_out_of_order_sequences_fail_closed():
    policy = CollisionFfbSafetyPolicy()
    process(policy, request(sequence=4))

    duplicate = process(policy, request(sequence=4), monotonic=2.01)
    out_of_order = process(policy, request(sequence=3), monotonic=2.02)

    assert duplicate.fault
    assert "non_increasing_sequence" in duplicate.reason
    assert out_of_order.fault


def test_sequence_can_reset_after_watchdog_sized_publisher_gap():
    policy = CollisionFfbSafetyPolicy(watchdog_timeout_sec=0.1)
    process(
        policy,
        request(sequence=10, generated=10.0),
        monotonic=2.0,
        now=10.0,
    )

    restarted = process(
        policy,
        request(sequence=0, generated=10.2),
        monotonic=2.2,
        now=10.2,
    )

    assert restarted.action is OutputAction.APPLY
    assert not restarted.fault
    assert policy.last_sequence == 0


def test_stale_and_future_timestamps_fail_closed():
    policy = CollisionFfbSafetyPolicy(
        maximum_message_age_sec=0.1,
        future_tolerance_sec=0.05,
    )

    stale = process(policy, request(generated=9.0), now=10.0)
    future = process(policy, request(sequence=2, generated=10.2), now=10.0)

    assert stale.fault and "stale_message" in stale.reason
    assert future.fault and "future_message" in future.reason


def test_watchdog_stops_once_at_timeout():
    policy = CollisionFfbSafetyPolicy(watchdog_timeout_sec=0.1)
    process(policy, request(), monotonic=2.0)

    fresh = policy.poll_watchdog(2.099)
    expired = policy.poll_watchdog(2.1)
    repeated = policy.poll_watchdog(2.2)

    assert fresh.action is OutputAction.NONE
    assert expired.action is OutputAction.STOP
    assert expired.reason == "watchdog_timeout"
    assert expired.fault
    assert repeated.action is OutputAction.NONE


def test_monotonic_time_moving_backwards_fails_closed():
    policy = CollisionFfbSafetyPolicy()
    process(policy, request(), monotonic=2.0)

    decision = policy.poll_watchdog(1.9)

    assert decision.action is OutputAction.STOP
    assert decision.fault
    assert decision.reason == "monotonic_time_moved_backwards"


def test_explicit_stop_clears_active_state():
    policy = CollisionFfbSafetyPolicy()
    process(policy, request())

    decision = policy.force_stop("shutdown")

    assert decision.action is OutputAction.STOP
    assert not decision.active
    assert not policy.active
    assert decision.reason == "shutdown"


@pytest.mark.parametrize("sequence", [-1, 1 << 64])
def test_invalid_uint64_is_not_copied_to_stop_decision(sequence):
    policy = CollisionFfbSafetyPolicy()

    decision = process(policy, request(sequence=sequence))

    assert decision.sequence is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_source": ""},
        {"configured_max_magnitude": -0.1},
        {"configured_max_magnitude": 1.1},
        {"watchdog_timeout_sec": 0.0},
        {"maximum_message_age_sec": math.nan},
        {"future_tolerance_sec": -0.1},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        CollisionFfbSafetyPolicy(**kwargs)
