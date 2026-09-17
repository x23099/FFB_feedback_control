import pytest

from oit.collision_ffb_challenge import ChallengeTracker


def test_issued_token_is_valid_until_receiver_monotonic_deadline():
    tracker = ChallengeTracker(max_age_sec=0.1, session_id=17)
    session, token = tracker.issue(2.0)

    tracker.validate(session_id=session, token=token, now_monotonic_sec=2.099)
    with pytest.raises(ValueError, match="expired_receiver_token"):
        tracker.validate(session_id=session, token=token, now_monotonic_sec=2.101)


def test_unknown_or_prior_session_cannot_reuse_token():
    old = ChallengeTracker(session_id=17)
    _session, token = old.issue(2.0)
    current = ChallengeTracker(session_id=18)
    current.issue(2.0)

    with pytest.raises(ValueError, match="unknown_receiver_session"):
        current.validate(session_id=17, token=token, now_monotonic_sec=2.01)
    with pytest.raises(ValueError, match="unknown_receiver_token"):
        current.validate(session_id=18, token=99, now_monotonic_sec=2.01)


def test_receiver_clock_anomaly_invalidates_issued_tokens():
    tracker = ChallengeTracker(session_id=18)
    session, token = tracker.issue(2.0)

    with pytest.raises(ValueError, match="receiver_monotonic_time_moved_backwards"):
        tracker.validate(session_id=session, token=token, now_monotonic_sec=1.9)
    with pytest.raises(ValueError, match="unknown_receiver_token"):
        tracker.validate(session_id=session, token=token, now_monotonic_sec=2.1)
