#!/bin/bash
#
# @file run_bluerov_current_experiment.sh
# @brief Launches every bluerov_current_experiment scenario in sequence,
#        stopping each one automatically once its metrics recorder has
#        collected enough post-settle data, then moving to the next.
#
# @details
# Each scenario has no scripted end condition (see PROTOCOL.md) -- it holds
# or transects forever until stopped. This script watches each run's own
# log for the recorder's ">>> ... ENOUGH DATA ... <<<" line (one per agent),
# and once every agent in the scenario has printed it, sends the same
# Ctrl+C signal scenario_launch.sh expects, waits for its cleanup to finish,
# then starts the next scenario. A per-scenario timeout guards against a
# run that never gets there (stuck guidance, crashed xdyn, etc.) -- it stops
# and moves on rather than hanging the whole batch.
#
# If any scenario already has a result from a previous run, it asks whether
# to re-run everything or skip those (interactively, or non-interactively
# via RERUN_MODE=all|missing set in the environment).
#
# Must be run from the repository root, same as scenario_launch.sh itself:
#   src/simulation_run/scripts/bluerov_current_experiment/run_bluerov_current_experiment.sh
#
# Edit the SCENARIOS array below to run a subset instead of everything.
# See README.md in this directory for what each script here does.

set -uo pipefail

YELLOW='\033[0;33m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

CONFIG_SUBDIR="bluerov_current_experiment"
LAUNCH_SCRIPT="src/simulation_run/executable/scenario_launch.sh"
CONFIG_DIR="src/simulation_run/config/$CONFIG_SUBDIR"
SELF_DIR="src/simulation_run/scripts/$CONFIG_SUBDIR"

# Every scenario, in order. Comment lines out to permanently drop one; for a
# one-off skip of scenarios that already have results, see the prompt below
# instead -- no need to edit this array for that.
SCENARIOS=(
    station_keeping_none.json
    station_keeping_ekman.json
    station_keeping_gauss.json
    station_keeping_gauss_seed2.json
    station_keeping_gauss_seed3.json
    station_keeping_gauss_seed4.json
    station_keeping_gauss_seed5.json
    transect_none.json
    transect_ekman.json
    transect_ekman_pure_pursuit.json
    transect_gauss.json
    transect_gauss_seed2.json
    transect_gauss_seed3.json
    transect_gauss_seed4.json
    transect_gauss_seed5.json
    transect_gauss_seed6.json
    transect_gauss_seed7.json
    transect_gauss_seed8.json
    transect_gauss_seed9.json
    transect_gauss_seed10.json
    transect_gauss_seed11.json
    transect_gauss_seed12.json
    transect_gauss_seed13.json
    transect_gauss_seed14.json
    transect_gauss_seed15.json
    transect_gauss_seed16.json
    transect_gauss_seed17.json
    transect_gauss_seed18.json
    transect_gauss_seed19.json
    transect_gauss_seed20.json
    # Measured-current condition: one scenario per Copernicus date, treated as
    # an ensemble the way the Gauss-Markov seeds are (see
    # generate_copernicus_scenarios.py). Deterministic, so one run per date.
    station_keeping_copernicus_2023-11-04.json
    station_keeping_copernicus_2024-06-03.json
    station_keeping_copernicus_2024-07-31.json
    station_keeping_copernicus_2024-08-07.json
    station_keeping_copernicus_2024-10-03.json
    transect_copernicus_2023-11-04.json
    transect_copernicus_2024-06-03.json
    transect_copernicus_2024-07-31.json
    transect_copernicus_2024-08-07.json
    transect_copernicus_2024-10-03.json
)

# Safety ceiling per scenario: stop and move on if "ENOUGH DATA" never
# appears from every agent within this many seconds. Generous margin over
# the ~360 s (settle_s + min_duration_s) the recorder needs, to absorb
# Gazebo/Unity startup time.
MAX_WAIT_S="${MAX_WAIT_S:-1800}"
# How often to check the log while waiting.
POLL_S=5
# How long to wait for the scenario's own log directory to appear after
# launch, before giving up on this scenario entirely.
LOG_DIR_TIMEOUT_S=120
# How long to wait for scenario_launch.sh to finish its own cleanup after
# being signalled, before this script force-kills it as a last resort.
CLEANUP_TIMEOUT_S=120

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

# scenario_launch.sh's own cleanup() assumes its "ros2 run simulation_run
# main" child already received SIGINT via the *process group* -- true for a
# real terminal Ctrl+C (broadcast to the whole foreground group), NOT true
# for `kill -INT` sent to one specific PID by this script. Without it,
# cleanup() waits its scripted 10s grace period for nothing, then escalates
# to an uncaught SIGTERM (main.py only registers a SIGINT handler -- see
# main.py's signal.signal call), which kills the process immediately,
# skipping the `finally:` block that writes each agent's summary.json.
# Signal the python process directly too, so it always gets a real chance
# to shut down gracefully, regardless of process-group membership.
stop_scenario() {
    local pid="$1" config_file="$2"
    local py_pid
    py_pid=$(pgrep -f "simulation_run/lib/simulation_run/main .*${config_file}" 2>/dev/null | head -1)
    [[ -n "$py_pid" ]] && kill -INT "$py_pid" 2>/dev/null
    kill -INT "$pid" 2>/dev/null
}

# Forward Ctrl+C on this script to whatever scenario is currently running,
# instead of leaving it orphaned, then stop the batch.
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

    # PYTHONUNBUFFERED: scenario_launch.sh pipes everything through `tee`, so
    # python's stdout is a pipe, not a tty, and defaults to block buffering --
    # the ENOUGH DATA line can then sit in a 4-8 KB buffer for a minute or
    # more before reaching the log this loop greps, delaying every stop.
    PYTHONUNBUFFERED=1 "$LAUNCH_SCRIPT" --config "$CONFIG_SUBDIR/$config_file" &
    CURRENT_PID=$!
    CURRENT_CONFIG_FILE="$config_file"

    # Find the log directory this run just created.
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

    # Wait until every agent has printed ENOUGH DATA, or the timeout hits.
    waited=0
    while (( waited < MAX_WAIT_S )); do
        if ! kill -0 "$CURRENT_PID" 2>/dev/null; then
            warn "$config_file exited on its own before reaching ENOUGH DATA on all agents."
            CURRENT_PID=""
            return
        fi
        local ready_count
        ready_count=$(grep -c "ENOUGH DATA" "$log_dir/main_simulation.log" 2>/dev/null)
        ready_count="${ready_count:-0}"
        if (( ready_count >= n_agents )); then
            info "$config_file: all $n_agents agent(s) reported ENOUGH DATA after ~${waited}s."
            break
        fi
        sleep "$POLL_S"
        (( waited += POLL_S ))
    done
    if (( waited >= MAX_WAIT_S )); then
        warn "$config_file: MAX_WAIT_S=${MAX_WAIT_S}s reached without every agent reporting ENOUGH DATA -- stopping anyway and moving on. Check $log_dir/main_simulation.log."
    fi

    # Stop this scenario the same way a user would (Ctrl+C), then wait for
    # its own cleanup trap to actually finish before starting the next one.
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

    # Verify the stop actually produced a summary for every agent, rather
    # than silently trusting the shutdown went cleanly -- if it didn't,
    # stop the whole batch here so an incomplete run never goes unnoticed.
    if ! has_results "$config_file"; then
        die "$config_file stopped but no *_summary.json was written -- the graceful shutdown did not complete (see run_bluerov_current_experiment.sh/scenario_launch.sh's cleanup()). Fix that before trusting any more runs; this scenario's CSV data is incomplete."
    fi

    # Small margin so ports/processes are fully released before the next launch.
    sleep 5
}

# Ask whether to re-run scenarios that already have a completed result
# (a *_summary.json under results/bluerov_current_experiment/<scenario>/),
# instead of silently redoing or silently skipping them.
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

info "Batch done. Aggregating the ensemble conditions (if all their runs succeeded)..."
# Gauss-Markov: ensemble members are seeds, and the current is depth-uniform,
# so the cross-agent pooled figure is the one to quote.
python3 "$SELF_DIR/aggregate_seeds.py" station_keeping_gauss || warn "station_keeping_gauss aggregation skipped/failed -- see above."
python3 "$SELF_DIR/aggregate_seeds.py" transect_gauss || warn "transect_gauss aggregation skipped/failed -- see above."
# Measured current: ensemble members are dates, and the current varies with
# depth, so pooling across agents is suppressed (--depth-resolved).
python3 "$SELF_DIR/aggregate_seeds.py" station_keeping_copernicus \
    --run-glob 'station_keeping_copernicus_*' --depth-resolved \
    || warn "station_keeping_copernicus aggregation skipped/failed -- see above."
python3 "$SELF_DIR/aggregate_seeds.py" transect_copernicus \
    --run-glob 'transect_copernicus_*' --depth-resolved \
    || warn "transect_copernicus aggregation skipped/failed -- see above."

info "All done."
