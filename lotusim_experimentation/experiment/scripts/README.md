# Tooling — model-as-environment comparison

Scripts for the current study only. Run every command below from a
`LOTUSim-generic-scenario` checkout after copying `scenarios/` and
`scripts/` in per the top-level [experiment README](../README.md), or
directly against this repository's own copies with `--config-dir
lotusim_experimentation/experiment/scenarios` (from the repository root).

Every script here was re-verified on 2026-08-27 by reproducing an already-
published date byte-for-byte from its raw inputs, not by reading the code:
several were previously drifted from the pipeline that actually produced
the tracked results (wrong directories, wrong fit weighting, wrong scenario
geometry) despite looking plausible. Don't trust a script here because it
reads correctly -- if you change one, re-run it against a published date
and diff the output before trusting it for a new one.

## Pipeline order

```
screen_copernicus_wind_dates.py   -- cheap: find candidate dates by wind alone
        |
download_deep_profiles.py        -- download the chosen dates' current profile
        |
fit_ekman_profile.py              -- fit both current models to each profile
fit_gauss_markov_profile.py
        |
generate_environment_experiment.py -- write that date's 12 scenario JSONs
generate_fitted_ekman_assets.py    -- write that date's vehicle YAML
        |
(copy into LOTUSim-generic-scenario / LOTUSim, see ../README.md)
        |
../run_experiment.sh                  -- simulate
```

## `screen_copernicus_wind_dates.py`

Downloads only the cheap wind product (~15-25 KB/date) for each candidate in
a date range and reports measured U10/Beaufort, so new dates are chosen for
genuine wind diversity rather than picked blind, and before paying for the
expensive current download below. Requires `copernicusmarine` (`pip install
copernicusmarine`, then `copernicusmarine login`) and `h5py`.

```bash
python3 scripts/screen_copernicus_wind_dates.py --start 2024-09-01 --end 2025-03-31 --step-days 4 --out candidates.csv
```

Imports `beaufort`/`mean_wind_speed` from `extract_copernicus_wind.py`
(kept alongside it for that reason, not run directly in this pipeline).

## `download_deep_profiles.py`

Downloads the full 0.5-1000 m current profile for a chosen date and writes
`scenarios/copernicus_profiles_deep/brest_<date>.csv`. Needs the full column,
not a shallow truncation -- see the script's own docstring for why.

```bash
python3 scripts/download_deep_profiles.py 2025-05-20 --out-dir scenarios
```

## `fit_ekman_profile.py` / `fit_gauss_markov_profile.py`

Fit both current models to the 0-150 m band of each profile (the depth a
BlueROV2 actually flies), writing
`scenarios/fitted_params_deep/{ekman,gauss}_<date>.json`. Unweighted
least-squares; see each script's own docstring for the exact recipe and how
it was verified against the published dates.

```bash
python3 scripts/fit_ekman_profile.py --dates 2025-05-20
python3 scripts/fit_gauss_markov_profile.py --dates 2025-05-20
```

Omit `--dates` to (re-)fit every profile present.

## `generate_environment_experiment.py`

Writes the 12 scenario JSONs (4 transects x 3 environments) for each date
from its fitted Gauss-Markov parameters.

```bash
python3 scripts/generate_environment_experiment.py --config-dir scenarios --dates 2025-05-20
```

`--bands` overrides the default transect geometry (Level/Sweep A/B/C, the
this study's transect design) if a different one is ever needed.

## `generate_fitted_ekman_assets.py`

Writes `BlueROV2_current_fitted_ekman_<date>.yml` into a `LOTUSim`
checkout's `assets/models/bluerov2_heavy/`, substituting the fitted Ekman
parameters into a copy of the base vehicle YAML (xdyn's `ekman current`
model reads its parameters from the vehicle YAML, not the scenario JSON).

```bash
python3 scripts/generate_fitted_ekman_assets.py \
    --fitted-params-dir scenarios/fitted_params_deep \
    --lotusim-path <path to a LOTUSim checkout>
```

Processes every `ekman_*.json` present each time (idempotent) rather than
taking a `--dates` filter.

## Superseded

The `appendix/superseded-experiments` branch holds the scripts for the two
earlier study designs (shallow-column feedforward benefit; energy-trajectory
feedforward pilot) -- not part of reproducing the current results, kept for
the record. Do not copy scripts
from there into this directory; if a script here needs equivalent
functionality (e.g. the wind cross-check, seed ensembles for a stochastic
condition), port it deliberately and re-verify it the same way this
directory's scripts were, rather than restoring the old file wholesale.
