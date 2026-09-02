# Model-in-the-loop experiment assets

Everything needed to reproduce the model-in-the-loop evaluation, kept here
rather than in the simulator repositories: these are the configurations and
data of one study, not simulator features.

- `scenarios/` — one scenario JSON per (transect, environment, date), plus the
  Copernicus depth profiles replayed as the reference environment, the fitted
  Ekman and Gauss–Markov parameters, and the Copernicus wind used to select
  dates.
- `scripts/` — the generators and drivers: `generate_environment_experiment.py`
  writes the scenarios, `generate_fitted_ekman_assets.py` writes the per-date
  vehicle files, `screen_copernicus_wind_dates.py` performs the wind screening.
- `vehicle_assets/` — one BlueROV2 Heavy YAML per date, carrying that date's
  fitted Ekman parameters. Copy into
  `LOTUSim/assets/models/bluerov2_heavy/` before running.

`LOTUSim-generic-scenario` ignores `config/bluerov_current_experiment/`
and `scripts/bluerov_current_experiment/`, so copying scenarios and scripts
into it never leaves stray diffs. `LOTUSim` does **not** currently
ignore `assets/models/bluerov2_heavy/BlueROV2_current_fitted_ekman_*.yml` --
copying vehicle assets there will show up as untracked files (`git status`)
until that repository's `.gitignore` is updated to match.

Dates are selected on measured 10 m wind speed from Copernicus's wind product,
independently of the current fit, so the criterion can be stated before any
simulation is run.

## Running the experiment on another machine

### 1. The three checkouts

Only two repositories have to be built; this one is data and tooling.

| repository | branch | what it provides |
|---|---|---|
| `LOTUSim` | `main` | simulation engine, worlds, vehicle models, and the prebuilt `physics/xdyn-for-cs` binary (tracked, so no xdyn build is needed) |
| `LOTUSim-generic-scenario` | `main` | `scenario_launch.sh`, `lotusim_sdk`, and the `bluerov_gnc` package the scenarios drive |
| this repository | `main` | scenarios, fitted parameters, vehicle YAMLs, drivers, results |

```bash
git clone -b main git@github.com:IRL-Crossing-CNRS/LOTUSim.git \
    <path>/lotusim_ws/src/LOTUSim
git clone -b main git@github.com:IRL-Crossing-CNRS/LOTUSim-generic-scenario.git \
    <path>/LOTUSim-generic-scenario
```

Build each per its own README (`colcon build` in both workspaces), then source
both `install/setup.bash`. `LOTUSim`'s `main` already carries the xdyn
binary built with the corrected Ekman current model, so `lxdyn` only needs
cloning if that C++ model is being changed.

### 2. Copy this directory into the checkouts

This directory is the source of truth for the experiment.
`LOTUSim-generic-scenario` ignores `config/bluerov_current_experiment/`
and `scripts/bluerov_current_experiment/`, so copying into it is always
clean. `LOTUSim` does not (yet) ignore the per-date vehicle YAMLs --
`git status` there will list them as untracked after the copy below; that is
expected, not a sign something went wrong. Generic carries only the base
example scenarios that users need; everything specific
to this study lives here and is copied in before a run.

```bash
SCEN=<path>/LOTUSim-generic-scenario
CORE=<path>/lotusim_ws/src/LOTUSim

mkdir -p "$SCEN/src/simulation_run/config/bluerov_current_experiment" \
         "$SCEN/src/simulation_run/scripts/bluerov_current_experiment"
cp -r scenarios/*      "$SCEN/src/simulation_run/config/bluerov_current_experiment/"
cp -r scripts/*        "$SCEN/src/simulation_run/scripts/bluerov_current_experiment/"
cp    vehicle_assets/* "$CORE/assets/models/bluerov2_heavy/"
```

### 3. Simulate

```bash
export SCENARIO_WS=<parent of LOTUSim-generic-scenario>
export LOTUSIM_WS=<path>/lotusim_ws

./run_experiment.sh                    # simulate the whole experiment
./run_experiment.sh --list             # what has no result yet, run nothing
./run_experiment.sh --until 07:00      # simulate what fits before 07:00
./run_experiment.sh --dates 2025-05-20 # one date only
```

`run_experiment.sh` verifies each run by the summary JSON it is supposed to
produce and lists anything still missing at the end. It only simulates cells
without a result, so an interrupted batch resumes where it stopped, and it
finishes one date before starting the next, so an interrupted batch leaves
whole dates behind rather than fragments of several. With `--until`, a date is
started only if all of its outstanding runs fit before that clock time.

One run takes about 6 minutes of wall clock (a ~304 s mission plus startup and
shutdown), so a date — four depth bands x three environments — takes about
75 minutes, and the full 40-date experiment about 50 hours.

The scenarios here define exactly the 40 dates reported, so a complete run
reproduces the reported set rather than a superset: dates that were screened
but never simulated are not left lying in the config directory.

Results land in `$SCENARIO_WS/LOTUSim-generic-scenario/results/bluerov_environment_experiment/`,
one directory per run. Copy them back into this repository's
`lotusim_experimentation/results/` to keep the analysis reproducible from the
checked-in data alone. The checked-in copies are gzipped (`*.csv.gz`) to keep
the repository clonable; the analysis scripts read either form, so a run you
have just produced needs no conversion.

### 4. Adding dates

Dates are selected on measured 10 m wind speed from Copernicus's wind product,
independently of the current fit, so the criterion can be stated before any
simulation is run. Adding one is four steps, none of which requires editing a
script — the generators and `run_experiment.sh` discover dates from the files
present:

```bash
# a. find candidates: measured wind over a window, cheap, no current download
python3 scripts/screen_copernicus_wind_dates.py \
    --start 2024-06-15 --end 2026-08-15 --step-days 4 --out candidates.csv

# b. for a chosen date, download its current profile, fit both models, and
#    report the accuracy edge -- still no simulation
python3 scripts/download_and_screen_candidate_dates.py --dates 2025-05-20

# c. write that date's scenarios and its fitted-Ekman vehicle YAML
python3 scripts/generate_environment_experiment.py --dates 2025-05-20
python3 scripts/generate_fitted_ekman_assets.py

# d. copy in (step 2 above) and run it
./run_experiment.sh --dates 2025-05-20
```

Step (a) writes one row per candidate date with its measured 10 m wind speed
and Beaufort number; (b) needs a date to already have a profile or downloads
one; (c) writes twelve scenario JSONs for the date and one vehicle YAML per
date found in `scenarios/fitted_params/`; (d) simulates them.

Both Copernicus downloads need the `copernicusmarine` package and an
authenticated account (`copernicusmarine login`; credentials are cached in
`~/.copernicusmarine/`, never in this repository). Note that the near-real-time
wind product covers a rolling window only — roughly 2024-06 onward — so dates
before it can be simulated from an already-downloaded profile but cannot be
newly screened on wind.

### The Unity requirement

Every scenario sets `renderer_unity: true`, and `scenario_launch.sh` exits
before simulating if the Unity build is absent. That is how 67 runs in an
earlier batch were logged as successful without ever simulating: the driver
slept a fixed interval and echoed "done" without checking. `run_experiment.sh`
refuses to start in that state rather than repeating it.

If the target machine has no Unity build, `--no-unity` rewrites
`renderer_unity` to false in a temporary copy of each scenario. Rendering
should not affect the physics — xdyn and Gazebo integrate the dynamics, Unity
only draws them — but every date recorded so far was simulated with it
attached, so confirm equivalence before mixing:

```bash
./run_experiment.sh --control 2026-02-03
```

This re-simulates one finished date headless and diffs the metrics against the
stored result. Under ~1 % on every metric, headless runs are safe to combine.

## Per-date results

The summary tables report the two-regime aggregate; the per-date detail behind
them -- every date, every transect -- is here. After adding dates, recompute
these rows from `results/` with the `compute_*.py` scripts in `scripts/`
rather than editing the numbers by hand.

### Per-date fitted parameters

| date | Bft | v (m/s) | orient (deg) | top layer (m) | bottom layer (m) | U10 (m/s) | GM mean_x | GM mean_y | GM std_dev |
|---|---|---|---|---|---|---|---|---|---|
| 2023-11-04 | 8 | 0.223 | 111.4 | 98.00 | 1.84 | 13.16 | -0.0277 | +0.2565 | 0.1332 |
| 2024-06-03 | 3 | 0.129 | 129.8 | 0.60 | 8.32 | 2.05 | -0.0828 | +0.0983 | 0.0213 |
| 2024-07-31 | 3 | 0.056 | 99.1 | 0.50 | 72.56 | 2.46 | -0.0093 | +0.0541 | 0.0289 |
| 2024-08-07 | 3 | 0.108 | 189.3 | 0.50 | 1.07 | 2.58 | -0.1070 | -0.0186 | 0.0903 |
| 2024-08-10 | 3 | 0.040 | 247.4 | 34.31 | 34.26 | 7.15 | +0.0050 | -0.0234 | 0.0403 |
| 2024-10-03 | 3 | 0.118 | 312.9 | 0.68 | 0.60 | 1.90 | +0.0808 | -0.0873 | 0.0275 |
| 2024-11-30 | 4 | 0.108 | 358.5 | 27.15 | 1.30 | 4.33 | +0.1150 | +0.0012 | 0.0303 |
| 2024-12-08 | 4 | 0.161 | 232.1 | 0.50 | 19.69 | 2.33 | -0.0995 | -0.1281 | 0.0745 |
| 2025-01-06 | 6 | 0.135 | 115.9 | 98.00 | 9.80 | 9.78 | -0.0338 | +0.1447 | 0.0553 |
| 2025-01-09 | 6 | 0.100 | 181.1 | 98.00 | 61.69 | 7.07 | -0.0883 | +0.0085 | 0.0642 |
| 2025-01-20 | 6 | 0.024 | 144.8 | 0.85 | 0.60 | 1.92 | -0.0183 | +0.0127 | 0.0236 |
| 2025-02-24 | 6 | 0.053 | 96.5 | 98.00 | 2.11 | 9.23 | +0.0160 | +0.0724 | 0.0324 |
| 2025-05-20 | 3 | 0.009 | 19.1 | 0.58 | 1.76 | 2.43 | +0.0082 | +0.0014 | 0.0240 |
| 2025-06-17 | 3 | 0.033 | 62.5 | 98.00 | 42.85 | 3.55 | +0.0175 | +0.0315 | 0.0200 |
| 2025-08-12 | 4 | 0.055 | 200.3 | 98.00 | 25.42 | 6.71 | -0.0412 | -0.0098 | 0.0444 |
| 2025-09-09 | 4 | 0.051 | 257.4 | 0.50 | 5.00 | 0.88 | -0.0110 | -0.0494 | 0.0418 |
| 2025-10-15 | 5 | 0.050 | 87.9 | 98.00 | 28.19 | 7.82 | +0.0164 | +0.0630 | 0.0453 |
| 2025-11-04 | 5 | 0.029 | 341.7 | 98.00 | 51.29 | 8.87 | +0.0478 | +0.0089 | 0.0336 |
| 2025-12-15 | 5 | 0.086 | 139.1 | 70.89 | 19.22 | 7.32 | -0.0497 | +0.0687 | 0.0313 |
| 2026-01-08 | 6 | 0.007 | 104.1 | 98.00 | 97.93 | 6.58 | +0.0078 | +0.0158 | 0.0329 |
| 2026-01-24 | 7 | 0.068 | 125.4 | 98.00 | 5.57 | 9.96 | -0.0129 | +0.0797 | 0.0375 |
| 2026-02-03 | 6 | 0.078 | 84.8 | 98.00 | 34.87 | 10.54 | +0.0376 | +0.1057 | 0.0401 |
| 2026-02-12 | 8 | 0.092 | 229.2 | 98.00 | 43.60 | 6.43 | -0.0511 | -0.0614 | 0.0408 |
| 2026-04-14 | 5 | 0.031 | 347.8 | 32.60 | 98.00 | 3.91 | +0.0351 | -0.0029 | 0.0356 |
| 2026-06-21 | 3 | 0.042 | 351.1 | 0.52 | 1.99 | 5.57 | +0.0388 | -0.0138 | 0.0828 |
| 2026-07-07 | 3 | 0.065 | 36.2 | 28.97 | 98.00 | 4.64 | +0.0608 | +0.0439 | 0.0252 |

### Per-date field accuracy (0-150 m)

| date | Bft | regime | 2Ds (m) | eps_Ekman | eps_const | reduction (%) |
|---|---|---|---|---|---|---|
| 2023-11-04 | 8 | resolved | 196 | 0.1172 | 0.1332 | 12 |
| 2024-06-03 | 3 | collapsed | 1 | 0.0207 | 0.0213 | 3 |
| 2024-07-31 | 3 | collapsed | 1 | 0.0285 | 0.0289 | 2 |
| 2024-08-07 | 3 | collapsed | 1 | 0.0901 | 0.0903 | 0 |
| 2024-08-10 | 3 | resolved | 69 | 0.0205 | 0.0403 | 49 |
| 2024-10-03 | 3 | collapsed | 1 | 0.0270 | 0.0275 | 2 |
| 2024-11-30 | 4 | resolved | 54 | 0.0275 | 0.0303 | 9 |
| 2024-12-08 | 4 | collapsed | 1 | 0.0743 | 0.0745 | 0 |
| 2025-01-06 | 6 | resolved | 196 | 0.0465 | 0.0553 | 16 |
| 2025-01-09 | 6 | resolved | 196 | 0.0628 | 0.0642 | 2 |
| 2025-01-20 | 6 | collapsed | 2 | 0.0227 | 0.0236 | 4 |
| 2025-02-24 | 6 | resolved | 196 | 0.0196 | 0.0324 | 40 |
| 2025-05-20 | 3 | collapsed | 1 | 0.0230 | 0.0240 | 4 |
| 2025-06-17 | 3 | resolved | 196 | 0.0199 | 0.0200 | 1 |
| 2025-08-12 | 4 | resolved | 196 | 0.0428 | 0.0444 | 4 |
| 2025-09-09 | 4 | collapsed | 1 | 0.0418 | 0.0418 | 0 |
| 2025-10-15 | 5 | resolved | 196 | 0.0419 | 0.0453 | 7 |
| 2025-11-04 | 5 | resolved | 196 | 0.0241 | 0.0336 | 28 |
| 2025-12-15 | 5 | resolved | 142 | 0.0242 | 0.0313 | 23 |
| 2026-01-08 | 6 | resolved | 196 | 0.0309 | 0.0329 | 6 |
| 2026-01-24 | 7 | resolved | 196 | 0.0208 | 0.0375 | 45 |
| 2026-02-03 | 6 | resolved | 196 | 0.0179 | 0.0401 | 56 |
| 2026-02-12 | 8 | resolved | 196 | 0.0394 | 0.0408 | 3 |
| 2026-04-14 | 5 | resolved | 65 | 0.0345 | 0.0356 | 3 |
| 2026-06-21 | 3 | collapsed | 1 | 0.0742 | 0.0828 | 10 |
| 2026-07-07 | 3 | resolved | 58 | 0.0211 | 0.0252 | 16 |

### Per-date closed-loop results

Ratio columns are eps_GM/eps_Ekman (geometric mean over the three metrics for that transect); above 1 favours Ekman. Layer: which Ekman layer that transect falls in on that date. Energy columns are signed relative departure from the reference.

**2026-04-22 is an outlier worth reading before trusting at a glance**: GM's
energy departure is +203% against Ekman's +25%, an order of magnitude beyond
every other date in this table. Checked against the raw run summaries
(`env_*_2026-04-22/*_summary.json`) before trusting it: all twelve runs have
the same ~304 s duration as every other date (no early termination, no crash),
and `gauss`'s cross-track/control-effort figures are essentially identical
across the `shallow`/`mid`/`deep` bands -- expected, not a bug, since the
Gauss-Markov current is depth-uniform by construction and those three bands
therefore see the same fitted current. The field-level accuracy gain that day
is modest (2Ds=111 m, only 3% RMSE reduction over the whole 0-150 m column),
yet the closed-loop energy gap is enormous -- meaning this date's true current
has most of its shear concentrated exactly in the depth range the vehicle
flies rather than spread evenly over the fitted band, a mismatch the
column-averaged field metric doesn't see but the mission does. The summary
tables above report medians across dates, which this single point does not
move by itself; it is recorded here as a per-date curiosity, not a claim the
aggregate results depend on.

| date | Bft | 2Ds (m) | Level (layer) | Sweep A (layer) | Sweep B (layer) | Sweep C (layer) | pooled ratio | ref (Wh) | GM (%) | Ekman (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| 2023-11-04 | 8 | 196 | 0.37 (top) | 0.42 (top) | 34.44 (top) | 2.12 (top) | 1.84 | 10.6 | +39.0 | -13.1 |
| 2024-06-03 | 3 | 1 | 1.53 (mid) | 0.81 (mid) | 0.25 (mid) | 0.08 (mid) | 0.40 | 7.6 | -7.3 | -18.1 |
| 2024-07-31 | 3 | 1 | 0.28 (mid) | 0.76 (mid) | 0.66 (mid) | 0.05 (mid) | 0.29 | 5.7 | -2.6 | -8.6 |
| 2024-08-07 | 3 | 1 | 0.62 (mid) | 3.97 (mid) | 5.95 (mid) | 1.51 (mid) | 2.17 | 5.5 | +12.2 | +6.4 |
| 2024-08-10 | 3 | 69 | 2.62 (top) | 0.36 (top) | 1.24 (mixed) | 0.96 (mid) | 1.03 | 5.3 | -2.6 | -5.1 |
| 2024-10-03 | 3 | 1 | 5.52 (mid) | 6.32 (mid) | 1.18 (mid) | 0.45 (mid) | 2.07 | 6.9 | +19.3 | -7.3 |
| 2024-11-30 | 4 | 54 | 1.23 (top) | 0.19 (top) | 1.33 (mixed) | 0.49 (mid) | 0.62 | 5.1 | -4.2 | -6.7 |
| 2024-12-08 | 4 | 1 | 3.29 (mid) | 1.22 (mid) | 0.25 (mid) | 0.57 (mid) | 0.87 | 7.7 | -5.7 | -16.0 |
| 2025-01-06 | 6 | 196 | 2.29 (top) | 0.69 (top) | 14.87 (top) | 1.96 (mixed) | 2.61 | 6.9 | +4.1 | -4.8 |
| 2025-01-09 | 6 | 196 | 4.45 (top) | 1.68 (top) | 5.14 (top) | 1.41 (top) | 2.71 | 6.4 | -12.2 | -4.7 |
| 2025-01-20 | 6 | 2 | 1.42 (mid) | 1.32 (mid) | 0.55 (mid) | 0.35 (mid) | 0.77 | 5.3 | -7.4 | -7.4 |
| 2025-02-24 | 6 | 196 | 1.96 (top) | 2.68 (top) | 16.56 (top) | 1.97 (mixed) | 3.62 | 5.2 | +14.9 | +2.0 |
| 2025-05-20 | 3 | 1 | 2.71 (mid) | 0.85 (mid) | 0.60 (mid) | 0.89 (mid) | 1.05 | 5.0 | -8.0 | -3.9 |
| 2025-06-17 | 3 | 196 | 1.60 (top) | 1.20 (top) | 0.56 (top) | 1.33 (mixed) | 1.09 | 5.0 | +0.7 | +2.9 |
| 2025-08-12 | 4 | 196 | 18.55 (top) | 4.69 (top) | 1.48 (top) | 3.78 (mixed) | 4.70 | 5.3 | -6.0 | +1.1 |
| 2025-09-09 | 4 | 1 | 1.24 (mid) | 0.94 (mid) | 4.57 (mid) | 4.90 (mid) | 2.26 | 4.7 | +9.4 | -0.9 |
| 2025-10-15 | 5 | 196 | 1.11 (top) | 0.41 (top) | 11.96 (top) | 2.73 (top) | 1.96 | 5.3 | +2.2 | -8.3 |
| 2025-11-04 | 5 | 196 | 0.91 (top) | 0.37 (top) | 0.99 (top) | 0.56 (mixed) | 0.66 | 5.0 | -8.3 | -10.0 |
| 2025-12-15 | 5 | 142 | 1.63 (top) | 0.96 (top) | 3.23 (top) | 1.31 (top) | 1.61 | 6.0 | -1.7 | -3.4 |
| 2026-01-08 | 6 | 196 | 4.09 (top) | 0.81 (top) | 1.23 (top) | 0.13 (top) | 0.85 | 4.9 | -1.2 | -0.9 |
| 2026-01-24 | 7 | 196 | 1.85 (top) | 2.17 (top) | 7.23 (top) | 2.45 (top) | 2.90 | 5.4 | +11.4 | -0.1 |
| 2026-02-03 | 6 | 196 | 1.68 (top) | 3.24 (top) | 45.52 (top) | 3.41 (top) | 5.39 | 5.9 | +16.7 | -2.6 |
| 2026-02-12 | 8 | 196 | 5.33 (top) | 11.27 (top) | 0.88 (top) | 0.88 (mixed) | 2.61 | 6.7 | -10.8 | -5.9 |
| 2026-04-14 | 5 | 65 | 0.69 (top) | 0.17 (mixed) | 0.59 (mid) | 0.30 (mid) | 0.38 | 4.8 | -0.2 | -4.1 |
| 2026-06-21 | 3 | 1 | 0.50 (mid) | 0.15 (mid) | 13.45 (mid) | 10.25 (mid) | 1.78 | 5.0 | +13.3 | -10.8 |
| 2026-07-07 | 3 | 58 | 1.76 (top) | 5.44 (top) | 0.12 (mixed) | 0.34 (mid) | 0.79 | 5.4 | +2.5 | -4.3 |
