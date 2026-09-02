#!/usr/bin/env bash
# Simulate the model-in-the-loop experiment: every (transect, environment,
# date) cell the scenario files define.
#
# This is the entry point for reproducing the study. Run it with no arguments
# on a fresh checkout and it simulates the whole experiment; the full set is
# every date present in the config directory crossed with four transects and
# three environments.
#
# It is also safe to re-run at any point. Each cell is skipped if its summary
# JSON already exists, so an interrupted batch resumes where it stopped rather
# than starting over, and a completed experiment re-run is a no-op that simply
# reports nothing missing. Resuming is a property of the script, not a separate
# mode: there is one command whether you are starting from nothing, filling a
# gap, or adding a newly generated date.
#
# Portable across machines: everything is derived from the two paths below,
# which are the only things to set.
#
# Why this exists rather than the previous ad-hoc loop: that loop slept a
# fixed interval and echoed "done" without checking anything, so 67 runs that
# never simulated were logged as successes. Here every run is verified by the
# output file it is supposed to produce, and anything still missing at the end
# is listed as a failure.
#
# Usage:
#   ./run_experiment.sh                 # simulate the whole experiment
#                                       # (skipping cells already done)
#   ./run_experiment.sh --list          # report what is missing, run nothing
#   ./run_experiment.sh --no-unity      # simulate headless (see the warning below)
#   ./run_experiment.sh --control DATE  # re-simulate one finished date headless
#                                    # and diff it against its stored result
#   ./run_experiment.sh --until 07:00   # stop in time: no date is started unless
#                                    # all of its cells fit before that clock
#                                    # time, so the batch never leaves a date
#                                    # half-simulated
#   ./run_experiment.sh --dates a,b,c   # only these dates, in this order
#
# Dates come from the scenario files present in the config directory, so
# adding a date is generating its scenarios -- no edit here. They are
# simulated in PRIORITY order first (below), then chronologically, and one
# date is finished before the next is started: an interrupted batch then
# leaves whole dates behind rather than fragments of several.
#
# --no-unity rewrites renderer_unity to false in a temporary copy of each
# scenario. The dates already recorded were simulated WITH the Unity
# renderer attached. Rendering should not touch the physics -- xdyn and Gazebo
# integrate the dynamics, Unity only draws them -- but "should not" is not
# evidence. Run --control on a finished date first and confirm the metrics
# match before mixing headless runs into the published set.
set -uo pipefail

# ---- paths (edit these two on a new machine) --------------------------------
SCEN_WS="${SCENARIO_WS:-$HOME/Documents/workspace/draft_lotusim}/LOTUSim-generic-scenario"
LOTUSIM_WS="${LOTUSIM_WS:-$HOME/draft_lotusim_ws}"

CONFIG_SUBDIR="bluerov_current_experiment"
CONFIG_DIR="$SCEN_WS/src/simulation_run/config/$CONFIG_SUBDIR"
RESULTS_DIR="$SCEN_WS/results/bluerov_environment_experiment"
LAUNCH="$SCEN_WS/src/simulation_run/executable/scenario_launch.sh"

# Wall-clock budget per run. The mission is ~304 s of simulated time; the
# extra covers startup and shutdown.
RUN_SECONDS=320
SETTLE_SECONDS=45

BANDS=(flat shallow mid deep)
CONDS=(copernicus gauss ekman)

# Dates to reach for first when the batch cannot cover every remaining one.
# Chosen to spread the added dates across seasons rather than to cluster them
# in one month, so the extra dates widen the range of conditions sampled
# instead of repeating one of them.
PRIORITY=(
  2025-01-06 2025-05-20 2025-08-12 2025-11-04 2026-02-12 2026-04-14
  2025-06-17 2025-09-09 2025-02-24 2026-05-12 2025-11-25 2026-01-16
)

# ---- argument parsing -------------------------------------------------------
MODE=run; NO_UNITY=0; CONTROL_DATE=""; UNTIL=""; DATES_ARG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)     MODE=list; shift ;;
    --no-unity) NO_UNITY=1; shift ;;
    --control)  MODE=control; CONTROL_DATE="${2:-}"; shift 2 ;;
    --until)    UNTIL="${2:-}"; shift 2 ;;
    --dates)    DATES_ARG="${2:-}"; shift 2 ;;
    -h|--help)  sed -n '2,42p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die () { echo "ERROR: $*" >&2; exit 1; }
[[ -x "$LAUNCH" ]] || die "launcher not found or not executable: $LAUNCH
Set SCENARIO_WS to the directory containing LOTUSim-generic-scenario."
[[ -d "$CONFIG_DIR" ]] || die "scenario configs not found: $CONFIG_DIR
Copy experiment/scenarios/ there first (see this directory's README)."
command -v jq >/dev/null || die "jq is required"

# Each scenario's output_dir ("results/bluerov_environment_experiment") and the
# launcher's LOG_DIR are both relative to the working directory, so the runs
# only land where RESULTS_DIR expects them if that directory is the scenario
# workspace. Enforce it here rather than requiring the caller to cd first: run
# from anywhere else and every run is written somewhere else, then reported as
# having produced no output.
cd "$SCEN_WS" || die "cannot enter $SCEN_WS"

# ---- which dates ------------------------------------------------------------
# Every date that has a full set of scenarios, priority ones first.
mapfile -t AVAILABLE < <(
  ls "$CONFIG_DIR"/env_*.json 2>/dev/null |
    sed 's/.*env_[a-z]*_[a-z]*_//; s/\.json$//' | sort | uniq -c |
    awk -v n=$(( ${#BANDS[@]} * ${#CONDS[@]} )) '$1 == n { print $2 }'
)
[[ ${#AVAILABLE[@]} -gt 0 ]] || die "no date has a complete set of scenarios in $CONFIG_DIR"

if [[ -n "$DATES_ARG" ]]; then
  IFS=',' read -r -a DATES <<< "$DATES_ARG"
  for d in "${DATES[@]}"; do
    [[ " ${AVAILABLE[*]} " == *" $d "* ]] || die "$d has no complete set of scenarios"
  done
else
  DATES=()
  for d in "${PRIORITY[@]}"; do
    [[ " ${AVAILABLE[*]} " == *" $d "* ]] && DATES+=("$d")
  done
  for d in "${AVAILABLE[@]}"; do
    [[ " ${DATES[*]} " == *" $d "* ]] || DATES+=("$d")
  done
fi

# ---- deadline ---------------------------------------------------------------
# A date is started only if all of its outstanding cells fit before this.
DEADLINE=0
if [[ -n "$UNTIL" ]]; then
  DEADLINE=$(date -d "$UNTIL" +%s 2>/dev/null) || die "cannot read --until $UNTIL"
  # A time already past today means the same time tomorrow.
  [[ $DEADLINE -le $(date +%s) ]] && DEADLINE=$(date -d "tomorrow $UNTIL" +%s)
fi
PER_RUN=$(( RUN_SECONDS + SETTLE_SECONDS + 5 ))

# ---- helpers ----------------------------------------------------------------
result_dir () { echo "$RESULTS_DIR/env_${1}_${2}_${3}"; }
is_done () { compgen -G "$(result_dir "$1" "$2" "$3")/*_summary.json" >/dev/null 2>&1; }

# Build the scenario to launch. With --no-unity, write a headless copy into the
# same config directory (the launcher resolves --config relative to it) and
# echo the name to use; otherwise echo the original.
TMP_SCENARIOS=()
scenario_for () {
  local name="$1"
  if [[ $NO_UNITY -eq 0 ]]; then echo "$name"; return; fi
  local headless="nounity_$name"
  jq '.renderer_unity = false' "$CONFIG_DIR/$name" > "$CONFIG_DIR/$headless" || return 1
  TMP_SCENARIOS+=("$CONFIG_DIR/$headless")
  echo "$headless"
}
cleanup () { [[ ${#TMP_SCENARIOS[@]} -gt 0 ]] && rm -f "${TMP_SCENARIOS[@]}"; }
trap cleanup EXIT

run_one () {
  local band="$1" cond="$2" date="$3"
  local name="env_${band}_${cond}_${date}.json"
  [[ -f "$CONFIG_DIR/$name" ]] || { echo "  MISSING SCENARIO $name"; return 1; }
  local launch_name; launch_name="$(scenario_for "$name")" || return 1

  echo "  $(date +%H:%M) $name"
  "$LAUNCH" --config "$CONFIG_SUBDIR/$launch_name" >/dev/null 2>&1 &
  local lpid=$!
  sleep "$RUN_SECONDS"
  local py; py=$(pgrep -f "simulation_run/lib/simulation_run/main .*$launch_name" | head -1)
  [[ -n "$py" ]] && kill -INT "$py"
  kill -INT "$lpid" 2>/dev/null
  sleep "$SETTLE_SECONDS"
  pkill -9 -f "xdyn-for-cs|gz sim" 2>/dev/null
  sleep 5

  # The point of this script: confirm the run produced what it claims to.
  if is_done "$band" "$cond" "$date"; then
    echo "    ok"
    return 0
  fi
  echo "    NO OUTPUT"
  return 1
}

# ---- control mode -----------------------------------------------------------
if [[ "$MODE" == control ]]; then
  [[ -n "$CONTROL_DATE" ]] || die "--control needs a date, e.g. --control 2026-02-03"
  band=flat; cond=copernicus
  before="$(result_dir "$band" "$cond" "$CONTROL_DATE")"
  compgen -G "$before/*_summary.json" >/dev/null || die "$CONTROL_DATE has no stored result to compare against"
  saved=$(mktemp); cat "$before"/*_summary.json > "$saved"
  echo "Re-simulating $CONTROL_DATE ($band/$cond) with the current settings."
  mv "$before" "${before}.control_backup.$$"
  NO_UNITY=1
  if run_one "$band" "$cond" "$CONTROL_DATE"; then
    echo; echo "stored vs re-simulated:"
    python3 - "$saved" "$before" <<'PY'
import glob, json, sys
a = json.load(open(sys.argv[1]))
b = json.load(open(glob.glob(sys.argv[2] + "/*_summary.json")[0]))
keys = ["energy_wh", "rms_cross_track_m", "rms_control_effort_N", "duration_s"]
worst = 0.0
for k in keys:
    if k not in a or k not in b:
        continue
    d = abs(b[k] - a[k]) / a[k] * 100 if a[k] else 0.0
    worst = max(worst, d)
    print(f"  {k:24s} {a[k]:12.5f} -> {b[k]:12.5f}   {d:+.3f}%")
print()
print(f"  worst deviation: {worst:.3f}%")
print("  VERDICT: headless runs are comparable" if worst < 1.0
      else "  VERDICT: NOT comparable -- do not mix headless runs into the set")
PY
  else
    echo "control run produced no output"
  fi
  rm -rf "$before"; mv "${before}.control_backup.$$" "$before"; rm -f "$saved"
  exit 0
fi

# ---- enumerate what is missing ---------------------------------------------
missing=()
for d in "${DATES[@]}"; do
  for b in "${BANDS[@]}"; do
    for c in "${CONDS[@]}"; do
      is_done "$b" "$c" "$d" || missing+=("$b|$c|$d")
    done
  done
done

complete_dates=$(
  for d in "${AVAILABLE[@]}"; do
    n=0
    for b in "${BANDS[@]}"; do for c in "${CONDS[@]}"; do
      is_done "$b" "$c" "$d" && n=$((n + 1))
    done; done
    [[ $n -eq $(( ${#BANDS[@]} * ${#CONDS[@]} )) ]] && echo "$d"
  done | wc -l
)
echo "dates already complete: $complete_dates of ${#AVAILABLE[@]} available"
echo "missing runs: ${#missing[@]}"
if [[ "$MODE" == list || ${#missing[@]} -eq 0 ]]; then
  printf '  %s\n' "${missing[@]//|/ }"
  exit 0
fi

# ---- preflight: is the Unity build present? ---------------------------------
UNITY_DIR="$SCEN_WS/lotusim_unity_executables"
if [[ $NO_UNITY -eq 0 ]]; then
  if ! compgen -G "$UNITY_DIR/*/*.x86_64" >/dev/null 2>&1; then
    cat >&2 <<MSG
ERROR: no Unity executable under $UNITY_DIR

Every scenario in this experiment sets renderer_unity: true, and the launcher
exits before simulating when the build is absent. This is exactly what silently
voided 67 runs in the previous batch.

Either restore the Unity build on this machine, or re-run with --no-unity after
validating it with --control (see the header of this script).
MSG
    exit 1
  fi
fi


secs=$(( PER_RUN * ${#missing[@]} ))
echo "estimated wall clock: $((secs / 3600))h $(((secs % 3600) / 60))m"
[[ $NO_UNITY -eq 1 ]] && echo "MODE: headless (renderer_unity forced false)"
[[ $DEADLINE -gt 0 ]] && echo "deadline: $(date -d "@$DEADLINE" '+%F %H:%M') ($(( (DEADLINE - $(date +%s)) / 60 )) min from now)"
echo

failed=(); ran=0; skipped_dates=()
for d in "${DATES[@]}"; do
  cells=()
  for cell in "${missing[@]}"; do [[ "$cell" == *"|$d" ]] && cells+=("$cell"); done
  [[ ${#cells[@]} -eq 0 ]] && continue

  # Start a date only if it can be finished. A date left half-simulated is
  # not usable for a per-date comparison, and re-running it later costs the
  # cells already spent on it.
  if [[ $DEADLINE -gt 0 ]]; then
    need=$(( PER_RUN * ${#cells[@]} ))
    if [[ $(( $(date +%s) + need )) -gt $DEADLINE ]]; then
      skipped_dates+=("$d")
      continue
    fi
  fi

  echo "$(date +%H:%M) === $d (${#cells[@]} runs) ==="
  for cell in "${cells[@]}"; do
    IFS='|' read -r b c _ <<< "$cell"
    run_one "$b" "$c" "$d" || failed+=("$cell")
    ran=$((ran + 1))
  done
done

echo
echo "=== finished: $(( ran - ${#failed[@]} ))/$ran produced output ==="
if [[ ${#skipped_dates[@]} -gt 0 ]]; then
  echo "not started, would not fit before the deadline:"
  printf '  %s\n' "${skipped_dates[@]}"
fi
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "failed:"; printf '  %s\n' "${failed[@]//|/ }"
  exit 1
fi
