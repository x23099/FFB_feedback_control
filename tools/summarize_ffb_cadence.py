#!/usr/bin/env python3
"""Summarize collision FFB cadence probe result directories."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def collect_rows(root: Path) -> list[dict]:
    """Collect one flat summary row from each cadence directory."""
    rows = []
    for path in sorted(root.glob("*/trial_summary.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        settings = payload["settings"]
        summary = payload["summary"]
        rows.append({
            "cadence": settings["cadence"],
            "pattern": settings["pattern"],
            "magnitude": settings["magnitude"],
            "duration_sec": settings["duration_sec"],
            "rate_hz": settings["rate_hz"],
            "decision": summary["decision"],
            "command_count": summary["command_count"],
            "active_command_count": summary["active_command_count"],
            "status_count": summary["status_count"],
            "active_apply_coverage": summary["active_apply_coverage"],
            "fault_count": summary["fault_count"],
            "max_applied_magnitude": summary["max_applied_magnitude"],
            "response_latency_mean_ms": summary[
                "response_latency_mean_ms"
            ],
            "response_latency_p95_ms": summary["response_latency_p95_ms"],
            "final_clear_stop_latency_ms": summary[
                "final_clear_stop_latency_ms"
            ],
            "result_dir": str(path.parent),
        })
    return rows


def write_summary(root: Path, rows: list[dict]) -> None:
    """Write suite CSV and Markdown summaries."""
    if not rows:
        raise ValueError(f"no cadence trial summaries found under {root}")
    csv_path = root / "cadence_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Collision FFB cadence dry-run summary",
        "",
        "| cadence | active commands | coverage | p95 latency [ms] | "
        "stop latency [ms] | decision |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        p95 = row["response_latency_p95_ms"]
        stop = row["final_clear_stop_latency_ms"]
        lines.append(
            f"| {row['cadence']} | {row['active_command_count']} | "
            f"{float(row['active_apply_coverage']):.3f} | "
            f"{float(p95):.3f} | {float(stop):.3f} | "
            f"{row['decision']} |"
        )
    decisions = [row["decision"] for row in rows]
    overall = "PASS" if decisions and all(
        item == "PASS" for item in decisions
    ) else "FAIL"
    lines.extend([
        "",
        f"総合判定: **{overall}**",
        "",
        "この比較はROS dry-runの通信・停止特性を示す。",
        "G923上の体感差は実機試験で別途評価する。",
        "",
    ])
    (root / "cadence_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    """Read one result root and write its suite summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    rows = collect_rows(args.root)
    write_summary(args.root, rows)
    print(f"Summary: {(args.root / 'cadence_report.md').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
