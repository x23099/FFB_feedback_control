"""Receiver-clock freshness proofs for the opt-in collision FFB dry run."""

from __future__ import annotations

import math
import secrets

from oit.collision_ffb_policy import UINT64_MAX


class ChallengeTracker:
    """Bound command transit time without comparing the two PCs' clocks."""

    def __init__(self, *, max_age_sec: float = 0.1, session_id: int | None = None):
        self.max_age_sec = float(max_age_sec)
        if not math.isfinite(self.max_age_sec) or self.max_age_sec <= 0.0:
            raise ValueError("max_age_sec must be finite and positive")
        self.session_id = (
            secrets.randbelow(UINT64_MAX) + 1 if session_id is None else int(session_id)
        )
        if not 1 <= self.session_id <= UINT64_MAX:
            raise ValueError("session_id must be a nonzero uint64")
        self._next_token = 1
        self._issued: dict[int, float] = {}
        self._last_now: float | None = None

    def _check_clock(self, now: float) -> float:
        now = float(now)
        if not math.isfinite(now) or now < 0.0:
            raise ValueError("invalid_receiver_monotonic_time")
        if self._last_now is not None and now < self._last_now:
            self._issued.clear()
            raise ValueError("receiver_monotonic_time_moved_backwards")
        self._last_now = now
        return now

    def _prune(self, now: float) -> None:
        self._issued = {
            token: issued for token, issued in self._issued.items()
            if now - issued <= self.max_age_sec
        }

    def issue(self, now_monotonic_sec: float) -> tuple[int, int]:
        now = self._check_clock(now_monotonic_sec)
        self._prune(now)
        if self._next_token > UINT64_MAX:
            raise ValueError("receiver_challenge_token_exhausted")
        token = self._next_token
        self._next_token += 1
        self._issued[token] = now
        return self.session_id, token

    def validate(
        self, *, session_id: int, token: int, now_monotonic_sec: float
    ) -> None:
        now = self._check_clock(now_monotonic_sec)
        if int(session_id) != self.session_id:
            raise ValueError("unknown_receiver_session")
        issued = self._issued.get(int(token))
        if issued is None:
            raise ValueError("unknown_receiver_token")
        if now - issued > self.max_age_sec:
            self._prune(now)
            raise ValueError("expired_receiver_token")
        self._prune(now)
