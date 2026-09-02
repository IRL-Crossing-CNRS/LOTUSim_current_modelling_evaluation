#!/bin/bash
#
# @file run_bandwidth_matched_experiment.sh
# @brief Launches the bandwidth-matched sinxz scenarios written by
#        generate_bandwidth_matched_sinxz.py (2 depths x 3 conditions x N
#        dates). Same launch/verify loop as run_energy_trajectory_experiment.sh
#        -- see that script's header for how each run is stopped and verified.
#
# Results land in results/bluerov_energy_experiment_bw, separate from the
# main grid (results/bluerov_energy_experiment), because this trajectory's
# geometry (u0=0.6, A=3, lambda=25.1) differs from the main grid's sinxz and
# the two should not be aggregated together.
#
# Must be run from the repository root, same as scenario_launch.sh itself:
#   src/simulation_run/scripts/bluerov_current_experiment/run_bandwidth_matched_experiment.sh
#
# Environment:
#   DATES="2023-11-04 2024-08-07"   restrict the batch (space-separated)
#   DEPTHS="deep"                   restrict the batch
#   CONDITIONS="ff_ekman"           restrict the batch
#   RERUN_MODE=all|missing          skip the interactive prompt

set -uo pipefail

YELLOW='\033[0;33m'; RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'

CONFIG_SUBDIR="bluerov_current_experiment"
RESULTS_SUBDIR="bluerov_energy_experiment_bw"
LAUNCH_SCRIPT="src/simulation_run/executable/scenario_launch.sh"
CONFIG_DIR="src/simulation_run/config/$CONFIG_SUBDIR"

DEPTHS="${DEPTHS:-shallow deep}"
DATES="${DATES:-$(ls "$CONFIG_DIR/fitted_params"/ekman_*.json 2>/dev/null \
    | sed -E 's#.*/ekman_(.*)\.json#\1#' | sort)}"
CONDITIONS="${CONDITIONS:-copernicus ff_gauss ff_ekman}"

SCENARIOS=()
for depth in $DEPTHS; do
    for date in $DATES; do
        for cond in $CONDITIONS; do
            SCENARIOS+=("sinxz_bw_${depth}_${cond}_${date}.json")
        done
    done
done

MAX_WAIT_S="${MAX_WAIT_S:-1800}"
POLL_S=5
LOG_DIR_TIMEOUT_S=120
CLEANUP_TIMEOUT_S=120
# Measured duration_s in the validated pilots was ~219s; margin to 260s.
RUN_DURATION_S="${RUN_DURATION_S:-260}"

die() { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }
info() { echo -e "${GREEN}[INFO] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }

[[ -f "$LAUNCH_SCRIPT" ]] || die "Run this from the repository root (couldn't find $LAUNCH_SCRIPT)."
command -v jq >/dev/null || die "jq is required."

RESULTS_DIR="results/$RESULTS_SUBDIR"
has_results() { compgen -G "$RESULTS_DIR/${1%.json}/*_summary.json" >/dev/null 2>&1; }

CURRENT_PID=""; CURRENT_CONFIG_FILE=""
stop_scenario() {
    local pid="$1" config_file="$2"
    local py_pid; py_pid=$(pgrep -f "simulation_run/lib/simulation_run/main .*${config_file}" 2>/dev/null | head -1)
    [[ -n "$py_pid" ]] && kill -INT "$py_pid" 2>/dev/null
    kill -INT "$pid" 2>/dev/null
}
abort() {
    echo ""; warn "Interrupted -- stopping the current scenario and exiting."
    if [[ -n "$CURRENT_PID" ]] && kill -0 "$CURRENT_PID" 2>/dev/null; then
        stop_scenario "$CURRENT_PID" "$CURRENT_CONFIG_FILE"; wait "$CURRENT_PID" 2>/dev/null
    fi
    exit 130
}
trap abort SIGINT SIGTERM

run_one() {
    local config_file="$1" config_path="$CONFIG_DIR/$1"
    [[ -f "$config_path" ]] || { warn "Skipping $config_file: not found."; return; }
    local n_agents; n_agents=$(jq -r '.agents | length' "$config_path") || { warn "Skipping $config_file: bad config."; return; }
    info "=== $config_file ($n_agents agent(s), ${RUN_DURATION_S}s) ==="
    local before_ts; before_ts=$(date +%s)
    PYTHONUNBUFFERED=1 "$LAUNCH_SCRIPT" --config "$CONFIG_SUBDIR/$config_file" &
    CURRENT_PID=$!; CURRENT_CONFIG_FILE="$config_file"

    local log_dir="" waited=0
    while (( waited < LOG_DIR_TIMEOUT_S )); do
        local candidate; candidate=$(ls -dt scenario_logs/*/ 2>/dev/null | head -1)
        if [[ -n "$candidate" ]]; then
            local mtime; mtime=$(stat -c %Y "$candidate" 2>/dev/null || echo 0)
            (( mtime >= before_ts )) && { log_dir="${candidate%/}"; break; }
        fi
        kill -0 "$CURRENT_PID" 2>/dev/null || { warn "$config_file exited before its log dir appeared."; CURRENT_PID=""; return; }
        sleep 2; (( waited += 2 ))
    done
    [[ -z "$log_dir" ]] && { warn "$config_file: no log dir after ${LOG_DIR_TIMEOUT_S}s."; kill -INT "$CURRENT_PID" 2>/dev/null; wait "$CURRENT_PID" 2>/dev/null; CURRENT_PID=""; return; }
    info "Logging to $log_dir"

    local wait_cap_s="$MAX_WAIT_S"; (( RUN_DURATION_S < wait_cap_s )) && wait_cap_s="$RUN_DURATION_S"
    waited=0
    while (( waited < wait_cap_s )); do
        kill -0 "$CURRENT_PID" 2>/dev/null || { warn "$config_file exited on its own after ~${waited}s."; CURRENT_PID=""; return; }
        sleep "$POLL_S"; (( waited += POLL_S ))
    done
    info "$config_file: ran for ~${waited}s."
    info "$config_file: stopping, teardown can take a minute or two (caps at ${CLEANUP_TIMEOUT_S}s)."
    stop_scenario "$CURRENT_PID" "$config_file"
    waited=0
    while kill -0 "$CURRENT_PID" 2>/dev/null && (( waited < CLEANUP_TIMEOUT_S )); do sleep 2; (( waited += 2 )); done
    kill -0 "$CURRENT_PID" 2>/dev/null && { warn "$config_file: force-killing."; kill -9 "$CURRENT_PID" 2>/dev/null; }
    wait "$CURRENT_PID" 2>/dev/null; CURRENT_PID=""
    has_results "$config_file" || die "$config_file stopped but no summary was written."
    sleep 15
}

ALREADY_DONE=(); for s in "${SCENARIOS[@]}"; do has_results "$s" && ALREADY_DONE+=("$s"); done
TO_RUN=("${SCENARIOS[@]}")
if (( ${#ALREADY_DONE[@]} > 0 )); then
    warn "${#ALREADY_DONE[@]} of ${#SCENARIOS[@]} already have results."
    if [[ -n "${RERUN_MODE:-}" ]]; then answer="$RERUN_MODE"; else
        read -rp "Re-run ALL, or only MISSING? [all/missing] (default missing): " answer
    fi
    if [[ "${answer:-missing}" == "all" ]]; then info "Re-running all."; else
        TO_RUN=(); for s in "${SCENARIOS[@]}"; do has_results "$s" || TO_RUN+=("$s"); done
        info "Skipping ${#ALREADY_DONE[@]}, running ${#TO_RUN[@]}."
    fi
fi

info "Running ${#TO_RUN[@]} scenario(s)."
for s in "${TO_RUN[@]}"; do run_one "$s"; done
info "Batch done."
