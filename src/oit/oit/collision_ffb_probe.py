"""Bounded collision-FFB probe with automatic status recording.

The probe only publishes commands.  Physical output remains controlled by the
separately started adapter and requires an explicit hardware acknowledgement.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import rclpy
from oit_interfaces.msg import (
    CollisionFfbChallenge,
    CollisionFfbCommand,
    CollisionFfbStatus,
)
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)


PROBE_MAX_MAGNITUDE = 0.05
PROBE_MAX_DURATION_SEC = 0.5
PROBE_MIN_RATE_HZ = 10.0
PROBE_MAX_RATE_HZ = 60.0
CLEAR_COUNT = 3
CADENCES = ("continuous", "double", "triple")
PATTERNS = {
    "steady": (
        CollisionFfbCommand.WARNING,
        CollisionFfbCommand.STEADY,
    ),
    "steady_hold": (
        CollisionFfbCommand.WARNING_HOLD,
        CollisionFfbCommand.STEADY_HOLD,
    ),
    "pulse": (
        CollisionFfbCommand.UNKNOWN,
        CollisionFfbCommand.PULSE,
    ),
}


@dataclass(frozen=True)
class ProbeSettings:
    """Validated settings for one bounded probe."""

    pattern: str = "steady"
    cadence: str = "continuous"
    magnitude: float = PROBE_MAX_MAGNITUDE
    duration_sec: float = PROBE_MAX_DURATION_SEC
    rate_hz: float = 30.0
    source: str = "bird_eye"
    reason: str = "manual_collision_ffb_probe"
    expect_output_mode: str = "dry_run"
    acknowledge_physical_output: bool = False
    freshness_mode: str = "clock"


def validate_settings(settings: ProbeSettings) -> ProbeSettings:
    """Reject settings outside the remotely verified Phase 4 envelope."""
    if settings.freshness_mode not in {"clock", "challenge"}:
        raise ValueError("freshness_mode must be clock or challenge")
    if settings.freshness_mode == "challenge" and settings.expect_output_mode != "dry_run":
        raise ValueError("challenge probe is dry-run only")
    if settings.pattern not in PATTERNS:
        raise ValueError(f"unsupported pattern: {settings.pattern!r}")
    if settings.cadence not in CADENCES:
        raise ValueError(f"unsupported cadence: {settings.cadence!r}")
    magnitude = float(settings.magnitude)
    if (
        not math.isfinite(magnitude)
        or magnitude <= 0.0
        or magnitude > PROBE_MAX_MAGNITUDE
    ):
        raise ValueError(
            f"magnitude must be within (0, {PROBE_MAX_MAGNITUDE:.2f}]"
        )
    duration_sec = float(settings.duration_sec)
    if (
        not math.isfinite(duration_sec)
        or duration_sec <= 0.0
        or duration_sec > PROBE_MAX_DURATION_SEC
    ):
        raise ValueError(
            "duration must be within "
            f"(0, {PROBE_MAX_DURATION_SEC:.1f}] seconds"
        )
    rate_hz = float(settings.rate_hz)
    if (
        not math.isfinite(rate_hz)
        or rate_hz < PROBE_MIN_RATE_HZ
        or rate_hz > PROBE_MAX_RATE_HZ
    ):
        raise ValueError(
            f"rate must be within {PROBE_MIN_RATE_HZ:.0f}.."
            f"{PROBE_MAX_RATE_HZ:.0f} Hz"
        )
    if not settings.source.strip():
        raise ValueError("source must not be empty")
    if not settings.reason.strip():
        raise ValueError("reason must not be empty")
    if settings.expect_output_mode not in {"dry_run", "hardware"}:
        raise ValueError("expect_output_mode must be dry_run or hardware")
    if (
        settings.expect_output_mode == "hardware"
        and not settings.acknowledge_physical_output
    ):
        raise ValueError(
            "hardware probe requires --acknowledge-physical-output"
        )
    return settings


def build_active_schedule(
    cadence: str,
    duration_sec: float,
    rate_hz: float,
) -> list[bool]:
    """Return a deterministic active/inactive command schedule."""
    if cadence not in CADENCES:
        raise ValueError(f"unsupported cadence: {cadence!r}")
    sample_count = max(1, int(round(duration_sec * rate_hz)))
    if cadence == "continuous":
        return [True] * sample_count
    pulse_count = 2 if cadence == "double" else 3
    return [
        ((index * pulse_count * 2) // sample_count) % 2 == 0
        for index in range(sample_count)
    ]


def percentile(values: Iterable[float], fraction: float) -> Optional[float]:
    """Return a linearly interpolated percentile or None for no values."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, float(fraction))) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_trial(
    command_rows: list[dict],
    status_rows: list[dict],
    *,
    expected_mode: str,
    magnitude_limit: float,
    final_clear_sequence: int,
) -> dict:
    """Evaluate status coverage, clamping, faults, and final stop."""
    active_sequences = {
        int(row["sequence"])
        for row in command_rows
        if int(row["active"]) == 1
    }
    applied_sequences = {
        int(row["sequence"])
        for row in status_rows
        if row["action"] == "apply" and int(row["output_active"]) == 1
    }
    matched_active = active_sequences & applied_sequences
    active_coverage = (
        len(matched_active) / len(active_sequences)
        if active_sequences
        else 0.0
    )
    fault_rows = [row for row in status_rows if int(row["fault"]) == 1]
    modes = sorted({str(row["output_mode"]) for row in status_rows})
    applied_values = [
        float(row["applied_magnitude"])
        for row in status_rows
        if int(row["output_active"]) == 1
    ]
    max_applied = max(applied_values, default=0.0)
    final_stop_rows = [
        row
        for row in status_rows
        if int(row["sequence"]) >= int(final_clear_sequence)
        and int(row["output_active"]) == 0
        and row["action"] in {"stop", "none"}
    ]
    final_inactive = bool(status_rows) and (
        int(status_rows[-1]["output_active"]) == 0
    )

    command_send_by_sequence = {
        int(row["sequence"]): float(row["send_monotonic_sec"])
        for row in command_rows
    }
    response_latencies_ms = []
    for row in status_rows:
        sequence = int(row["sequence"])
        sent = command_send_by_sequence.get(sequence)
        if sent is not None:
            response_latencies_ms.append(
                (float(row["receive_monotonic_sec"]) - sent) * 1000.0
            )
    stop_latency_ms = None
    if final_stop_rows:
        sent = command_send_by_sequence.get(final_clear_sequence)
        if sent is not None:
            stop_latency_ms = (
                float(final_stop_rows[0]["receive_monotonic_sec"]) - sent
            ) * 1000.0

    checks = {
        "status_received": bool(status_rows),
        "expected_mode_only": modes == [expected_mode],
        "active_apply_coverage": active_coverage >= 0.80,
        "no_fault": not fault_rows,
        "magnitude_within_limit": max_applied <= magnitude_limit + 1e-6,
        "final_clear_observed": bool(final_stop_rows),
        "final_inactive": final_inactive,
    }
    return {
        "decision": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "expected_output_mode": expected_mode,
        "observed_output_modes": modes,
        "command_count": len(command_rows),
        "active_command_count": len(active_sequences),
        "status_count": len(status_rows),
        "matched_active_sequences": len(matched_active),
        "active_apply_coverage": active_coverage,
        "fault_count": len(fault_rows),
        "max_applied_magnitude": max_applied,
        "response_latency_mean_ms": (
            statistics.fmean(response_latencies_ms)
            if response_latencies_ms
            else None
        ),
        "response_latency_p95_ms": percentile(response_latencies_ms, 0.95),
        "final_clear_stop_latency_ms": stop_latency_ms,
        "final_clear_sequence": int(final_clear_sequence),
    }


def command_qos() -> QoSProfile:
    """Return QoS matching the collision FFB adapter."""
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )


class CollisionFfbProbeNode(Node):
    """Publish one bounded probe and collect adapter statuses."""

    def __init__(
        self, command_topic: str, status_topic: str, *,
        freshness_mode: str = "clock",
        challenge_topic: str = "/collision/ffb_challenge",
    ):
        """Create publisher and subscriber without opening an input device."""
        super().__init__("collision_ffb_probe")
        qos = command_qos()
        self.publisher = self.create_publisher(
            CollisionFfbCommand,
            command_topic,
            qos,
        )
        self.status_rows: list[dict] = []
        self.started_monotonic_sec = time.monotonic()
        self.latest_challenge = None
        self.subscription = self.create_subscription(
            CollisionFfbStatus,
            status_topic,
            self._on_status,
            qos,
        )
        self.challenge_subscription = None
        if freshness_mode == "challenge":
            self.challenge_subscription = self.create_subscription(
                CollisionFfbChallenge,
                challenge_topic,
                self._on_challenge,
                qos,
            )

    def _on_challenge(self, message: CollisionFfbChallenge) -> None:
        if int(message.session_id) > 0 and int(message.token) > 0:
            self.latest_challenge = (
                int(message.session_id), int(message.token), time.monotonic()
            )

    def _on_status(self, message: CollisionFfbStatus) -> None:
        received = time.monotonic()
        self.status_rows.append({
            "receive_monotonic_sec": received,
            "elapsed_sec": received - self.started_monotonic_sec,
            "stamp_sec": (
                float(message.header.stamp.sec)
                + float(message.header.stamp.nanosec) / 1e9
            ),
            "has_sequence": 1 if message.has_sequence else 0,
            "sequence": int(message.sequence),
            "source": str(message.source),
            "output_mode": str(message.output_mode),
            "action": str(message.action),
            "command_active": 1 if message.command_active else 0,
            "output_active": 1 if message.output_active else 0,
            "requested_magnitude": float(message.requested_magnitude),
            "applied_magnitude": float(message.applied_magnitude),
            "pattern": int(message.pattern),
            "reason": str(message.reason),
            "fault": 1 if message.fault else 0,
        })


def make_command(
    node: Node,
    *,
    sequence: int,
    pattern_name: str,
    active: bool,
    magnitude: float,
    source: str,
    reason: str,
    receiver_session_id: int = 0,
    receiver_token: int = 0,
) -> CollisionFfbCommand:
    """Build one schema-consistent active or CLEAR command."""
    message = CollisionFfbCommand()
    message.header.stamp = node.get_clock().now().to_msg()
    message.sequence = int(sequence)
    message.source = source
    message.receiver_session_id = int(receiver_session_id)
    message.receiver_token = int(receiver_token)
    if active:
        risk_level, pattern = PATTERNS[pattern_name]
        message.risk_level = risk_level
        message.pattern = pattern
        message.active = True
        message.normalized_magnitude = float(magnitude)
        message.reason = reason
    else:
        message.risk_level = CollisionFfbCommand.CLEAR
        message.pattern = CollisionFfbCommand.OFF
        message.active = False
        message.normalized_magnitude = 0.0
        message.reason = "probe_clear"
    return message


def spin_until(node: Node, deadline: float) -> None:
    """Service subscriptions until one monotonic deadline."""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return
        rclpy.spin_once(node, timeout_sec=min(0.01, remaining))


def run_probe(
    settings: ProbeSettings,
    *,
    command_topic: str,
    status_topic: str,
    discovery_sec: float,
    settle_sec: float,
    challenge_topic: str = "/collision/ffb_challenge",
) -> tuple[list[dict], list[dict], int]:
    """Send one probe, always finish with CLEAR, and collect statuses."""
    validate_settings(settings)
    rclpy.init(args=None)
    node = CollisionFfbProbeNode(
        command_topic,
        status_topic,
        freshness_mode=settings.freshness_mode,
        challenge_topic=challenge_topic,
    )
    command_rows: list[dict] = []
    sequence = 0
    interval_sec = 1.0 / settings.rate_hz
    schedule = build_active_schedule(
        settings.cadence,
        settings.duration_sec,
        settings.rate_hz,
    )

    def publish(active: bool) -> None:
        nonlocal sequence
        latest = node.latest_challenge
        if (
            settings.freshness_mode == "challenge"
            and latest is not None
            and 0.0 <= time.monotonic() - latest[2] <= 0.1
        ):
            receiver_session_id, receiver_token = latest[:2]
        else:
            receiver_session_id, receiver_token = 0, 0
        message = make_command(
            node,
            sequence=sequence,
            pattern_name=settings.pattern,
            active=active,
            magnitude=settings.magnitude,
            source=settings.source,
            reason=f"{settings.reason}:{settings.cadence}",
            receiver_session_id=receiver_session_id,
            receiver_token=receiver_token,
        )
        sent = time.monotonic()
        node.publisher.publish(message)
        command_rows.append({
            "send_monotonic_sec": sent,
            "elapsed_sec": sent - node.started_monotonic_sec,
            "sequence": sequence,
            "source": settings.source,
            "risk_level": int(message.risk_level),
            "pattern": int(message.pattern),
            "active": 1 if active else 0,
            "requested_magnitude": float(message.normalized_magnitude),
            "reason": str(message.reason),
            "receiver_session_id": receiver_session_id,
            "receiver_token": receiver_token,
        })
        sequence += 1

    try:
        spin_until(node, time.monotonic() + discovery_sec)
        if node.count_subscribers(command_topic) < 1:
            raise RuntimeError(
                f"no adapter subscriber discovered on {command_topic}"
            )
        if node.count_publishers(status_topic) < 1:
            raise RuntimeError(
                f"no adapter status publisher discovered on {status_topic}"
            )
        for active in schedule:
            publish(active)
            spin_until(node, time.monotonic() + interval_sec)
    finally:
        final_clear_sequence = sequence
        for _index in range(CLEAR_COUNT):
            publish(False)
            spin_until(node, time.monotonic() + 0.02)
        spin_until(node, time.monotonic() + settle_sec)
        statuses = list(node.status_rows)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return command_rows, statuses, final_clear_sequence


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write dictionaries to CSV with a stable empty-file behavior."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_results(
    output_dir: Path,
    settings: ProbeSettings,
    command_rows: list[dict],
    status_rows: list[dict],
    summary: dict,
) -> None:
    """Persist reproducible CSV, JSON, and Markdown trial outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "command_log.csv", command_rows)
    write_csv(output_dir / "status_log.csv", status_rows)
    payload = {"settings": asdict(settings), "summary": summary}
    (output_dir / "trial_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    checks = "\n".join(
        f"- {'PASS' if passed else 'FAIL'}: `{name}`"
        for name, passed in summary["checks"].items()
    )
    response_p95 = format_optional(
        summary["response_latency_p95_ms"], " ms"
    )
    stop_latency = format_optional(
        summary["final_clear_stop_latency_ms"], " ms"
    )
    report = f"""# Collision FFB probe report

- 自動判定: **{summary['decision']}**
- pattern: `{settings.pattern}`
- cadence: `{settings.cadence}`
- magnitude: `{settings.magnitude:.3f}`
- duration: `{settings.duration_sec:.3f} s`
- rate: `{settings.rate_hz:.1f} Hz`
- expected output mode: `{settings.expect_output_mode}`

## 集計

| 項目 | 値 |
|---|---:|
| command数 | {summary['command_count']} |
| active command数 | {summary['active_command_count']} |
| status数 | {summary['status_count']} |
| active apply coverage | {summary['active_apply_coverage']:.3f} |
| fault数 | {summary['fault_count']} |
| 最大適用強度 | {summary['max_applied_magnitude']:.3f} |
| 応答時間p95 | {response_p95} |
| 最終CLEAR停止時間 | {stop_latency} |

## チェック

{checks}

この判定はROS adapterの状態に対する判定であり、G923の体感強度を自動判定するものではない。
"""
    (output_dir / "trial_report.md").write_text(report, encoding="utf-8")


def format_optional(value: Optional[float], suffix: str = "") -> str:
    """Format an optional measured value for a report table."""
    return "N/A" if value is None else f"{value:.3f}{suffix}"


def default_output_dir() -> Path:
    """Return a timestamped result directory under the current repository."""
    now = datetime.now()
    return Path("Experimental_results") / now.strftime("%Y-%m-%d") / (
        "ffb_probe_" + now.strftime("%H%M%S")
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Send one bounded collision-FFB probe and record adapter status"
        )
    )
    parser.add_argument(
        "--pattern",
        choices=sorted(PATTERNS),
        default="steady",
    )
    parser.add_argument("--cadence", choices=CADENCES, default="continuous")
    parser.add_argument("--magnitude", type=float, default=0.05)
    parser.add_argument("--duration", type=float, default=0.5)
    parser.add_argument("--rate", type=float, default=30.0)
    parser.add_argument("--source", default="bird_eye")
    parser.add_argument("--reason", default="manual_collision_ffb_probe")
    parser.add_argument(
        "--expect-output-mode",
        choices=("dry_run", "hardware"),
        default="dry_run",
    )
    parser.add_argument(
        "--freshness-mode", choices=("clock", "challenge"), default="clock"
    )
    parser.add_argument("--challenge-topic", default="/collision/ffb_challenge")
    parser.add_argument("--acknowledge-physical-output", action="store_true")
    parser.add_argument("--command-topic", default="/collision/ffb_command")
    parser.add_argument("--status-topic", default="/collision/ffb_status")
    parser.add_argument("--discovery-sec", type=float, default=1.0)
    parser.add_argument("--settle-sec", type=float, default=0.2)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(args=None) -> int:
    """Run one probe and return 0 only for an automatic PASS."""
    parsed = build_parser().parse_args(args)
    settings = ProbeSettings(
        pattern=parsed.pattern,
        cadence=parsed.cadence,
        magnitude=parsed.magnitude,
        duration_sec=parsed.duration,
        rate_hz=parsed.rate,
        source=parsed.source,
        reason=parsed.reason,
        expect_output_mode=parsed.expect_output_mode,
        acknowledge_physical_output=parsed.acknowledge_physical_output,
        freshness_mode=parsed.freshness_mode,
    )
    output_dir = parsed.output_dir or default_output_dir()
    try:
        validate_settings(settings)
        command_rows, status_rows, final_clear_sequence = run_probe(
            settings,
            command_topic=parsed.command_topic,
            status_topic=parsed.status_topic,
            discovery_sec=parsed.discovery_sec,
            settle_sec=parsed.settle_sec,
            challenge_topic=parsed.challenge_topic,
        )
        summary = summarize_trial(
            command_rows,
            status_rows,
            expected_mode=settings.expect_output_mode,
            magnitude_limit=settings.magnitude,
            final_clear_sequence=final_clear_sequence,
        )
        write_results(
            output_dir,
            settings,
            command_rows,
            status_rows,
            summary,
        )
    except (RuntimeError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(f"Decision: {summary['decision']}")
    print(f"Report: {(output_dir / 'trial_report.md').resolve()}")
    return 0 if summary["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
