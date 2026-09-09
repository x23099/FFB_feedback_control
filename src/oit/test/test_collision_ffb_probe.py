"""Tests for the bounded collision FFB probe and its result artifacts."""

import json

import pytest

from oit.collision_ffb_probe import (
    ProbeSettings,
    build_active_schedule,
    summarize_trial,
    validate_settings,
    write_results,
)


@pytest.mark.parametrize(
    "cadence,expected_transitions",
    [
        ("continuous", 0),
        ("double", 3),
        ("triple", 5),
    ],
)
def test_cadence_schedule_is_bounded_and_deterministic(
    cadence,
    expected_transitions,
):
    """Cadence schedules must remain finite and deterministic."""
    schedule = build_active_schedule(cadence, 0.5, 30.0)

    transitions = sum(
        left != right for left, right in zip(schedule, schedule[1:])
    )
    assert len(schedule) == 15
    assert schedule[0]
    assert transitions == expected_transitions


@pytest.mark.parametrize(
    "settings,expected",
    [
        (ProbeSettings(magnitude=0.051), "magnitude"),
        (ProbeSettings(duration_sec=0.501), "duration"),
        (ProbeSettings(rate_hz=9.0), "rate"),
        (ProbeSettings(cadence="other"), "cadence"),
        (ProbeSettings(pattern="other"), "pattern"),
        (
            ProbeSettings(expect_output_mode="hardware"),
            "acknowledge-physical-output",
        ),
    ],
)
def test_probe_settings_reject_unsafe_values(settings, expected):
    """Probe settings must reject values outside the safety envelope."""
    with pytest.raises(ValueError, match=expected):
        validate_settings(settings)


def test_hardware_probe_requires_and_accepts_explicit_acknowledgement():
    """Hardware probing must require a separate acknowledgement."""
    settings = ProbeSettings(
        expect_output_mode="hardware",
        acknowledge_physical_output=True,
    )

    assert validate_settings(settings) is settings


def command_row(sequence, *, active, sent):
    """Build one representative command log row."""
    return {
        "send_monotonic_sec": sent,
        "sequence": sequence,
        "active": 1 if active else 0,
    }


def status_row(
    sequence,
    *,
    active,
    received,
    action="apply",
    fault=False,
    magnitude=0.05,
    mode="dry_run",
):
    """Build one representative adapter status row."""
    return {
        "receive_monotonic_sec": received,
        "sequence": sequence,
        "output_mode": mode,
        "action": action,
        "output_active": 1 if active else 0,
        "applied_magnitude": magnitude if active else 0.0,
        "fault": 1 if fault else 0,
    }


def passing_rows():
    """Return command and status rows for one passing trial."""
    commands = [
        command_row(0, active=True, sent=10.000),
        command_row(1, active=True, sent=10.033),
        command_row(2, active=False, sent=10.066),
    ]
    statuses = [
        status_row(0, active=True, received=10.005),
        status_row(1, active=True, received=10.038),
        status_row(
            2,
            active=False,
            received=10.071,
            action="stop",
        ),
    ]
    return commands, statuses


def test_summary_passes_complete_dry_run_trial():
    """A complete, capped, fault-free dry-run trial must pass."""
    commands, statuses = passing_rows()

    summary = summarize_trial(
        commands,
        statuses,
        expected_mode="dry_run",
        magnitude_limit=0.05,
        final_clear_sequence=2,
    )

    assert summary["decision"] == "PASS"
    assert summary["active_apply_coverage"] == 1.0
    assert summary["fault_count"] == 0
    assert summary["response_latency_p95_ms"] == pytest.approx(5.0)
    assert summary["final_clear_stop_latency_ms"] == pytest.approx(5.0)


@pytest.mark.parametrize(
    "mutation,failed_check",
    [
        ("fault", "no_fault"),
        ("magnitude", "magnitude_within_limit"),
        ("mode", "expected_mode_only"),
        ("active", "active_apply_coverage"),
        ("final", "final_clear_observed"),
    ],
)
def test_summary_fails_unsafe_or_incomplete_status(mutation, failed_check):
    """Unsafe or incomplete adapter status must fail the trial."""
    commands, statuses = passing_rows()
    if mutation == "fault":
        statuses[0]["fault"] = 1
    elif mutation == "magnitude":
        statuses[0]["applied_magnitude"] = 0.051
    elif mutation == "mode":
        statuses[0]["output_mode"] = "hardware"
    elif mutation == "active":
        statuses = statuses[1:]
        commands.insert(1, command_row(9, active=True, sent=10.020))
    elif mutation == "final":
        statuses = statuses[:2]

    summary = summarize_trial(
        commands,
        statuses,
        expected_mode="dry_run",
        magnitude_limit=0.05,
        final_clear_sequence=2,
    )

    assert summary["decision"] == "FAIL"
    assert not summary["checks"][failed_check]


def test_write_results_creates_reproducible_artifacts(tmp_path):
    """Result writing must create reusable machine-readable artifacts."""
    commands, statuses = passing_rows()
    settings = ProbeSettings()
    summary = summarize_trial(
        commands,
        statuses,
        expected_mode="dry_run",
        magnitude_limit=0.05,
        final_clear_sequence=2,
    )

    write_results(tmp_path, settings, commands, statuses, summary)

    assert (tmp_path / "command_log.csv").is_file()
    assert (tmp_path / "status_log.csv").is_file()
    assert "自動判定: **PASS**" in (
        tmp_path / "trial_report.md"
    ).read_text(encoding="utf-8")
    payload = json.loads(
        (tmp_path / "trial_summary.json").read_text(encoding="utf-8")
    )
    assert payload["settings"]["magnitude"] == 0.05
    assert payload["summary"]["decision"] == "PASS"
