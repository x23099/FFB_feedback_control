#!/usr/bin/env bash

set -o pipefail

usage() {
    cat <<'EOF'
Usage:
  ./start_collision_ffb_dry_run_suite.sh [OUTPUT_DIR]

Runs continuous, double, and triple 0.05 cadence probes against an explicitly
dry-run collision FFB adapter. No input device is opened.

Environment:
  FFB_INSTALL_SETUP  setup.bash to source instead of ./install/setup.bash
  ROS_DOMAIN_ID      optional ROS 2 domain override
EOF
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -gt 1 ]]; then
    usage >&2
    exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir" || exit 2

output_dir="${1:-Experimental_results/$(date +%F)/ffb_cadence_$(date +%H%M%S)}"
install_setup="${FFB_INSTALL_SETUP:-$script_dir/install/setup.bash}"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
    echo "[ERROR] ROS 2 Humble setup not found" >&2
    exit 2
fi
if [[ ! -f "$install_setup" ]]; then
    echo "[ERROR] FFB workspace setup not found: $install_setup" >&2
    echo "Build oit_interfaces and oit before running this suite." >&2
    exit 2
fi

source /opt/ros/humble/setup.bash
source "$install_setup"
set -u

mkdir -p "$output_dir/ros_logs"
export ROS_LOG_DIR="$(cd "$output_dir/ros_logs" && pwd)"
adapter_log="$output_dir/adapter.log"

adapter_pid=""
stop_adapter() {
    if [[ -n "$adapter_pid" ]] && kill -0 "$adapter_pid" 2>/dev/null; then
        kill -INT "$adapter_pid" 2>/dev/null || true
        for _index in {1..20}; do
            kill -0 "$adapter_pid" 2>/dev/null || break
            sleep 0.05
        done
        if kill -0 "$adapter_pid" 2>/dev/null; then
            kill -TERM "$adapter_pid" 2>/dev/null || true
        fi
        wait "$adapter_pid" 2>/dev/null || true
    fi
    adapter_pid=""
}
trap stop_adapter EXIT INT TERM

echo "[INFO] Output: $output_dir"
echo "[INFO] Starting collision FFB adapter in dry_run mode"
bash -c 'trap - INT; exec ros2 run oit collision_ffb_node --ros-args \
    -p output_mode:=dry_run -p max_magnitude:=0.05' \
    >"$adapter_log" 2>&1 &
adapter_pid=$!

sleep 1
if ! kill -0 "$adapter_pid" 2>/dev/null; then
    echo "[ERROR] dry-run adapter exited during startup" >&2
    sed -n '1,160p' "$adapter_log" >&2
    exit 2
fi

suite_status=0
for cadence in continuous double triple; do
    echo "[INFO] Running cadence: $cadence"
    if ! ros2 run oit collision_ffb_probe \
        --pattern steady \
        --cadence "$cadence" \
        --magnitude 0.05 \
        --duration 0.5 \
        --rate 30 \
        --expect-output-mode dry_run \
        --output-dir "$output_dir/$cadence"; then
        suite_status=1
    fi
done

stop_adapter
trap - EXIT INT TERM

python3 "$script_dir/tools/summarize_ffb_cadence.py" "$output_dir"
echo "[INFO] Adapter log: $adapter_log"
echo "[INFO] Dry-run cadence suite finished"
exit "$suite_status"
