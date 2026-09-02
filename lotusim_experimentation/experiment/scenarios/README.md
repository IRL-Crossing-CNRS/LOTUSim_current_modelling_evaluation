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

## Other files in this directory

Everything not matching `env_*.json` (`station_keeping_*`, `transect_*`,
`line_*`, `sinxy_*`, `sinxz_*` and their `_seedN` variants) is left over
from the two earlier study designs and does not belong to the current
results -- their own scenario/config/results copies already live under
the `appendix/superseded-experiments` branch. They
were never moved out of this directory when the repository was restructured
around the current study, so `ls` here is misleading about what's live;
don't take a file's presence here as evidence it's part of the current
experiment. Treat only `env_*.json` (and the three supporting directories
above) as current.
