#!/bin/bash
#
# @file run_feedforward_experiment.sh
# @brief Launches the model-in-the-loop (feedforward) scenarios in sequence,
#        mirroring run_fitted_current_experiment.sh exactly (same launch/
#        duration/verify loop, same timeouts) -- see that script's header for
#        how each run is stopped and verified.
#
# These runs hold the APPLIED current fixed at the measured Copernicus
# profile and vary only the current model the CONTROLLER uses for
# feedforward, so a difference between them is attributable to the model
# rather than to a different disturbance. The no-feedforward baseline is the
# already-generated *_copernicus_<date>.json runs, which this does NOT re-run.
#
# No seed variants: every condition here is deterministic (the applied
# current is the measured replay, and a feedforward can only use the
# Gauss-Markov mean, not its zero-mean stochastic part).
#
# Prerequisite: fit_ekman_profile.py, fit_gauss_markov_profile.py,
# generate_copernicus_scenarios.py and generate_feedforward_scenarios.py must
# already have been run -- see this directory's README.
#
# Must be run from the repository root, same as scenario_launch.sh itself:
#   src/simulation_run/scripts/bluerov_current_experiment/run_feedforward_experiment.sh

set -uo pipefail

YELLOW='\033[0;33m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

CONFIG_SUBDIR="bluerov_current_experiment"
LAUNCH_SCRIPT="src/simulation_run/executable/scenario_launch.sh"
CONFIG_DIR="src/simulation_run/config/$CONFIG_SUBDIR"
SELF_DIR="src/simulation_run/scripts/$CONFIG_SUBDIR"

DATES=(2023-11-04 2024-06-03 2024-07-31 2024-08-07 2024-10-03)

# Transect FIRST, deliberately. Holding station at a fixed depth in a
# temporally-constant current is the one case where feedforward cannot help
# at steady state: the PID's integral term absorbs a constant disturbance
# completely, so the total force is set by the current drag whatever the
# controller believes (measured: control effort within 0.005% across all
# three conditions on 2023-11-04). The transect descends 3 -> 55 m
# continuously, so the current changes throughout and the integrator always
# lags -- that is where a depth-resolved model can beat a depth-uniform one,
# and therefore where the informative result is. Run it first so a null
# result there is known early rather than after the station-keeping half.
SCENARIOS=()
for mission in transect station_keeping; do
    for date in "${DATES[@]}"; do
        SCENARIOS+=("${mission}_ff_ekman_${date}.json")
        SCENARIOS+=("${mission}_ff_gauss_${date}.json")
    done
done
# 2 missions x 5 dates x 2 controller models = 20 runs, no seed variants.

MAX_WAIT_S="${MAX_WAIT_S:-1800}"
POLL_S=5
LOG_DIR_TIMEOUT_S=120
CLEANUP_TIMEOUT_S=120

# The per-agent metrics recorder (bluerov_gnc / csv_recorder.py) does not
# implement an "ENOUGH DATA" self-stop signal in the current codebase; it
# runs PERPETUALLY and never self-reports completion. This script therefore
# does not poll for that line: it runs each scenario for a fixed,
# mission-appropriate duration instead, with margin above the durations
# these scenarios need to complete (~380s station-keeping, ~530s transect).
# This keeps the batch's timing independent of bluerov_gnc/csv_recorder.py
# behaviour. MAX_WAIT_S is kept as an outer safety cap in case a scenario
# hangs outright.
STATION_KEEPING_DURATION_S="${STATION_KEEPING_DURATION_S:-450}"
TRANSECT_DURATION_S="${TRANSECT_DURATION_S:-600}"

die() { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }
info() { echo -e "${GREEN}[INFO] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }

[[ -f "$LAUNCH_SCRIPT" ]] || die "Run this from the repository root (couldn't find $LAUNCH_SCRIPT)."
command -v jq >/dev/null || die "jq is required (same dependency as scenario_launch.sh)."

RESULTS_DIR="results/$CONFIG_SUBDIR"
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

    info "=== $config_file ($n_agents agent(s)) ==="
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

    local target_duration_s="$STATION_KEEPING_DURATION_S"
    [[ "$config_file" == transect_* ]] && target_duration_s="$TRANSECT_DURATION_S"
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
    info "$config_file: ran for ~${waited}s (fixed duration, no self-stop signal available -- see script header)."

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

    # 15s, not the base script's 5s: one run in this batch (30/60) hit a ROS2
    # node-name collision ("adopting it for all topics") that broke its
    # recorder's topic wiring entirely and let it time out at 1800s with zero
    # CSV output -- the prior scenario's ROS graph had not finished tearing
    # down in 5s. Bigger margin to make that race much less likely to recur.
    sleep 15
}

ALREADY_DONE=()
for scenario in "${SCENARIOS[@]}"; do
    has_results "$scenario" && ALREADY_DONE+=("$scenario")
done

TO_RUN=("${SCENARIOS[@]}")
if (( ${#ALREADY_DONE[@]} > 0 )); then
    warn "${#ALREADY_DONE[@]} of ${#SCENARIOS[@]} scenario(s) already have results:"
    printf '    %s\n' "${ALREADY_DONE[@]}"
    if [[ -n "${RERUN_MODE:-}" ]]; then
        answer="$RERUN_MODE"
        info "RERUN_MODE=$answer set in the environment, skipping the prompt."
    else
        read -rp "Re-run ALL scenarios, or only the ones MISSING results? [all/missing] (default: missing): " answer
    fi
    if [[ "${answer:-missing}" == "all" ]]; then
        info "Re-running all ${#SCENARIOS[@]} scenario(s), including the ones with existing results."
    else
        TO_RUN=()
        for scenario in "${SCENARIOS[@]}"; do
            has_results "$scenario" || TO_RUN+=("$scenario")
        done
        info "Skipping ${#ALREADY_DONE[@]} scenario(s) with existing results; running ${#TO_RUN[@]}."
    fi
fi

info "Running ${#TO_RUN[@]} scenario(s). Ctrl+C at any point stops the current one and exits the batch cleanly."
for scenario in "${TO_RUN[@]}"; do
    run_one "$scenario"
done

info "Batch done. All feedforward conditions are deterministic -- no seed aggregation needed."
