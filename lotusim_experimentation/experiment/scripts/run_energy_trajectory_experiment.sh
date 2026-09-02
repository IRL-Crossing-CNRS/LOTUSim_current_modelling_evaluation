#!/bin/bash
#
# @file run_energy_trajectory_experiment.sh
# @brief Launches the energy-impact grid (3 trajectories x 2 depths x 5 dates
#        x 3 controller conditions = 90 runs) in sequence.
#
# Same launch/duration/verify loop as run_feedforward_experiment.sh -- see
# that script's header for how each run is stopped and verified. Two
# differences:
#
#   * the per-run duration is chosen per TRAJECTORY, not per mission, because
#     the horizontal sinusoid covers 264 m of path against 200-205 m for the
#     other two and needs proportionally longer at the same 0.5 m/s;
#   * results land in results/bluerov_energy_experiment, separate from the
#     transect/station-keeping experiment, while the CONFIGS stay in
#     config/bluerov_current_experiment because each scenario's Copernicus
#     profile path is resolved relative to its own config directory
#     (agents_manager.py:272) and those CSVs live there.
#
# Ordering is deliberate: `sinxz` (depth sinusoid) first, then `sinxy`, then
# `line`. sinxz is the only trajectory where a depth-resolved model has
# information a depth-uniform one lacks, so it carries the informative result;
# `line` is the negative control and is expected to come out null. Running
# them in that order means an interrupted batch still holds the answer.
#
# Prerequisite: generate_energy_trajectory_scenarios.py must have been run,
# and the workspace rebuilt so `bluerov_guidance_los_polyline` is registered.
#
# Must be run from the repository root, same as scenario_launch.sh itself:
#   src/simulation_run/scripts/bluerov_current_experiment/run_energy_trajectory_experiment.sh
#
# Environment:
#   TRAJECTORIES="sinxz"      restrict the batch (space-separated)
#   DATES="2023-11-04"        restrict the batch
#   DEPTHS="deep"             restrict the batch
#   CONDITIONS="ff_ekman"     restrict the batch
#   DURATION_SCALE=0.2        multiply every run duration (pilot runs)
#   RERUN_MODE=all|missing    skip the interactive prompt

set -uo pipefail

YELLOW='\033[0;33m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

CONFIG_SUBDIR="bluerov_current_experiment"
RESULTS_SUBDIR="bluerov_energy_experiment"
LAUNCH_SCRIPT="src/simulation_run/executable/scenario_launch.sh"
CONFIG_DIR="src/simulation_run/config/$CONFIG_SUBDIR"

TRAJECTORIES="${TRAJECTORIES:-sinxz sinxy line}"
DEPTHS="${DEPTHS:-shallow deep}"
# Auto-discovered from the fitted-params directory rather than hard-coded, so
# a new date only needs generate_energy_trajectory_scenarios.py re-run (which
# discovers the same way) before this picks it up too.
DATES="${DATES:-$(ls "$CONFIG_DIR/fitted_params"/ekman_*.json 2>/dev/null \
    | sed -E 's#.*/ekman_(.*)\.json#\1#' | sort)}"
CONDITIONS="${CONDITIONS:-copernicus ff_gauss ff_ekman}"
DURATION_SCALE="${DURATION_SCALE:-1.0}"

SCENARIOS=()
for traj in $TRAJECTORIES; do
    for depth in $DEPTHS; do
        for date in $DATES; do
            for cond in $CONDITIONS; do
                SCENARIOS+=("${traj}_${depth}_${cond}_${date}.json")
            done
        done
    done
done

MAX_WAIT_S="${MAX_WAIT_S:-1800}"
POLL_S=5
LOG_DIR_TIMEOUT_S=120
CLEANUP_TIMEOUT_S=120

# Commanded path length at the MEASURED along-track speed (0.478 m/s, not the
# 0.5 m/s setpoint -- the vehicle loses a little to the current), plus the 30 s
# settle window and ~20% margin. The recorder never self-stops (see
# run_feedforward_experiment.sh), so these fixed durations are what bounds
# each run.
duration_for() {
    local base
    case "$1" in
        sinxy_*) base=380 ;;    # 132 m of path -> 276 s + settle + margin
        sinxz_*) base=300 ;;    # 102 m of path -> 214 s + settle + margin
        *)       base=295 ;;    # 100 m of path -> 209 s + settle + margin
    esac
    awk -v b="$base" -v s="$DURATION_SCALE" 'BEGIN{printf "%d", (b*s < 30 ? 30 : b*s)}'
}

die() { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }
info() { echo -e "${GREEN}[INFO] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }

[[ -f "$LAUNCH_SCRIPT" ]] || die "Run this from the repository root (couldn't find $LAUNCH_SCRIPT)."
command -v jq >/dev/null || die "jq is required (same dependency as scenario_launch.sh)."

RESULTS_DIR="results/$RESULTS_SUBDIR"
has_results() {
    compgen -G "$RESULTS_DIR/${1%.json}/*_summary.json" >/dev/null 2>&1
}

CURRENT_PID=""
CURRENT_CONFIG_FILE=""

stop_scenario() {
    local pid="$1" config_file="$2"
    local py_pid
    py_pid=$(pgrep -f "simulation_run/lib/simulation_run/main .*${config_file}" 2>/dev/null | head -1)
    [[ -n "$py_pid" ]] && kill -INT "$py_pid" 2>/dev/null
    kill -INT "$pid" 2>/dev/null
}

abort() {
    echo ""
    warn "Interrupted -- stopping the current scenario and exiting the batch."
    if [[ -n "$CURRENT_PID" ]] && kill -0 "$CURRENT_PID" 2>/dev/null; then
        stop_scenario "$CURRENT_PID" "$CURRENT_CONFIG_FILE"
        wait "$CURRENT_PID" 2>/dev/null
    fi
    exit 130
}
trap abort SIGINT SIGTERM

run_one() {
    local config_file="$1"
    local config_path="$CONFIG_DIR/$config_file"
    [[ -f "$config_path" ]] || { warn "Skipping $config_file: not found at $config_path"; return; }

    local n_agents
    n_agents=$(jq -r '.agents | length' "$config_path") || { warn "Skipping $config_file: couldn't parse agent count"; return; }

    local target_duration_s
    target_duration_s=$(duration_for "$config_file")
    info "=== $config_file ($n_agents agent(s), ${target_duration_s}s) ==="
    local before_ts
    before_ts=$(date +%s)

    PYTHONUNBUFFERED=1 "$LAUNCH_SCRIPT" --config "$CONFIG_SUBDIR/$config_file" &
    CURRENT_PID=$!
    CURRENT_CONFIG_FILE="$config_file"

    local log_dir=""
    local waited=0
    while (( waited < LOG_DIR_TIMEOUT_S )); do
        local candidate
        candidate=$(ls -dt scenario_logs/*/ 2>/dev/null | head -1)
        if [[ -n "$candidate" ]]; then
            local mtime
            mtime=$(stat -c %Y "$candidate" 2>/dev/null || echo 0)
            if (( mtime >= before_ts )); then
                log_dir="${candidate%/}"
                break
            fi
        fi
        if ! kill -0 "$CURRENT_PID" 2>/dev/null; then
            warn "$config_file exited before its log directory appeared -- check the terminal output above."
            CURRENT_PID=""
            return
        fi
        sleep 2
        (( waited += 2 ))
    done
    if [[ -z "$log_dir" ]]; then
        warn "$config_file: no log directory after ${LOG_DIR_TIMEOUT_S}s, giving up on this scenario."
        kill -INT "$CURRENT_PID" 2>/dev/null
        wait "$CURRENT_PID" 2>/dev/null
        CURRENT_PID=""
        return
    fi
    info "Logging to $log_dir"

    local wait_cap_s="$MAX_WAIT_S"
    (( target_duration_s < wait_cap_s )) && wait_cap_s="$target_duration_s"

    waited=0
    while (( waited < wait_cap_s )); do
        if ! kill -0 "$CURRENT_PID" 2>/dev/null; then
            warn "$config_file exited on its own after ~${waited}s (target was ${target_duration_s}s)."
            CURRENT_PID=""
            return
        fi
        sleep "$POLL_S"
        (( waited += POLL_S ))
    done
    info "$config_file: ran for ~${waited}s (fixed duration, no self-stop signal available)."

    info "$config_file: stopping and waiting for Gazebo/Unity/ROS2/xdyn teardown -- this routinely takes a minute or two, this is not stuck, just wait (caps at ${CLEANUP_TIMEOUT_S}s)."
    stop_scenario "$CURRENT_PID" "$config_file"
    waited=0
    while kill -0 "$CURRENT_PID" 2>/dev/null && (( waited < CLEANUP_TIMEOUT_S )); do
        sleep 2
        (( waited += 2 ))
    done
    if kill -0 "$CURRENT_PID" 2>/dev/null; then
        warn "$config_file: cleanup did not finish within ${CLEANUP_TIMEOUT_S}s, force-killing."
        kill -9 "$CURRENT_PID" 2>/dev/null
    fi
    wait "$CURRENT_PID" 2>/dev/null
    CURRENT_PID=""

    if ! has_results "$config_file"; then
        die "$config_file stopped but no *_summary.json was written -- the graceful shutdown did not complete. Fix that before trusting any more runs; this scenario's CSV data is incomplete."
    fi

    # 15s between runs: a 5s gap once let a previous run's ROS graph survive
    # into the next one and break its recorder's topic wiring entirely (see
    # run_feedforward_experiment.sh).
    sleep 15
}

ALREADY_DONE=()
for scenario in "${SCENARIOS[@]}"; do
    has_results "$scenario" && ALREADY_DONE+=("$scenario")
done

TO_RUN=("${SCENARIOS[@]}")
if (( ${#ALREADY_DONE[@]} > 0 )); then
    warn "${#ALREADY_DONE[@]} of ${#SCENARIOS[@]} scenario(s) already have results."
    if [[ -n "${RERUN_MODE:-}" ]]; then
        answer="$RERUN_MODE"
        info "RERUN_MODE=$answer set in the environment, skipping the prompt."
    else
        read -rp "Re-run ALL scenarios, or only the ones MISSING results? [all/missing] (default: missing): " answer
    fi
    if [[ "${answer:-missing}" == "all" ]]; then
        info "Re-running all ${#SCENARIOS[@]} scenario(s)."
    else
        TO_RUN=()
        for scenario in "${SCENARIOS[@]}"; do
            has_results "$scenario" || TO_RUN+=("$scenario")
        done
        info "Skipping ${#ALREADY_DONE[@]} scenario(s) with existing results; running ${#TO_RUN[@]}."
    fi
fi

TOTAL_S=0
for scenario in "${TO_RUN[@]}"; do
    TOTAL_S=$(( TOTAL_S + $(duration_for "$scenario") + 90 ))
done
info "Running ${#TO_RUN[@]} scenario(s), ~$(( TOTAL_S / 3600 ))h$(( (TOTAL_S % 3600) / 60 ))m of wall clock including teardown. Ctrl+C stops the current one and exits the batch cleanly."
for scenario in "${TO_RUN[@]}"; do
    run_one "$scenario"
done

info "Batch done. All conditions are deterministic -- no seed aggregation needed."
