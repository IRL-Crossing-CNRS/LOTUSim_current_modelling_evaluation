# Scenarios — model-as-environment comparison

> **Path note:** paths below are written as they are inside
> `LOTUSim-generic-scenario`, where these scenarios actually run — copy
> this directory there first (see [../README.md](../README.md)).

The current study's files are `env_<band>_<current>_<date>.json`, one per
(transect, environment, date) cell -- 12 per date (4 transects x 3
environments). Written by `../scripts/generate_environment_experiment.py`;
see that script and [../scripts/README.md](../scripts/README.md) for how
they're generated, and [../README.md](../README.md) for the per-date tables
and how to reproduce or extend the set.

| band | depth band | crosses |
|---|---|---|
| `flat` | constant 25 m | nothing (control) |
| `shallow` | 10-40 m sinusoid | Sweep A |
| `mid` | 45-75 m sinusoid | Sweep B |
| `deep` | 80-110 m sinusoid | Sweep C |

| current | applied field |
|---|---|
| `copernicus` | that date's reanalysis profile, replayed -- the reference |
| `gauss` | Gauss-Markov, mean/std fit to the same profile |
| `ekman` | the layered model, fitted to the same profile (parameters live in the vehicle YAML, not here -- see `../scripts/generate_fitted_ekman_assets.py`) |

The controller is plain PID with no feedforward in every condition, so a
difference between conditions comes from the simulated environment alone,
not from what the controller believes about the current.

Supporting data alongside the scenarios:

- `copernicus_profiles_deep/` -- each date's measured 0.5-1000 m profile.
- `fitted_params_deep/` -- each date's fitted Ekman/Gauss-Markov parameters.
- `copernicus_wind/` -- measured wind, used to classify dates by Beaufort
  and to screen new candidates (independent of the current fit).

## The shallow-column data alongside it

`copernicus_profiles/` and `fitted_params/` hold the 0-65 m profiles and the
fits made against them, from the earlier shallow-column design of this study.
Nothing in the current experiment reads them -- every `env_*.json` replays
`copernicus_profiles_deep/`, and every vehicle YAML comes from
`fitted_params_deep/`. They are kept because the fit scripts still accept
them (`fit_ekman_profile.py` documents that mode), not because a current
result depends on them: treat only `env_*.json` and the three `_deep`/wind
directories listed above as live.
