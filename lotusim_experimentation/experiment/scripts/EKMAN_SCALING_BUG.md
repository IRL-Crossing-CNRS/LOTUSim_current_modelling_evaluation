# Scaling error in LOTUSim-Xdyn's Ekman top-layer velocity

**Status: diagnosed, fixed in this working tree, and confirmed empirically.**
Not yet reviewed by the model's authors. Everything below is reproducible
from the source files cited.

## The discrepancy

The reference Python implementation
(`benchmark/reference_implementations/python_ekman/classes/underwater/CurrentModels.py`,
`Vc_topLayer`) computes the wind-driven surface velocity as

    sqrt(2) / (RhoWater * f * dTop)   applied to the wind stress components

The C++ port used by the simulator
(`LOTUSim-Xdyn/code/xdyn/environment_models/EkmanUWCurrentModel.cpp`,
`getTopLayerCurrent`) computes

    V0 = sqrt(2) * M_PI * wind_stress / ( top_ekman_depth * f_and_sqrt_rho )

with, from `parse()`:

    f_and_sqrt_rho = 2 * omega * sin(latitude) * sqrt(rho)

The C++ uses **sqrt(rho)** where the reference uses **rho**. Classical Ekman
theory settles which is right:

    V0 = tau / (rho * sqrt(Az*f))    with    D = pi*sqrt(2*Az/f)
    =>  sqrt(Az*f) = D*f / (pi*sqrt(2))
    =>  V0 = sqrt(2)*pi*tau / (rho * f * D)

so the **pi in the C++ is correct** and the reference Python is missing it;
the density term is what is wrong. The C++ therefore overestimates V0 by

    sqrt(rho) = sqrt(1026) = 32.0x

(The 100x figure obtained by comparing the two implementations directly
conflates this 32x with the reference's missing pi -- 32x against theory is
the correct statement.)

Dimensional check on the C++ form: `[N/m^2] / ([m][1/s][kg^0.5/m^1.5])`
resolves to `kg^0.5 m^0.5 / s`, which is not a velocity -- consistent with a
mis-ported density term rather than a deliberate reparameterisation.

## Why it went unnoticed: the fit absorbs it

`fit_ekman_profile.py` fits `U10` to the measured current profile rather than
taking it from the wind product. Since wind stress goes as `U10^2`, a 100x
overscaled `V0` is compensated by a roughly 10x too-small fitted `U10` -- and
that is exactly what the fitted values show against the independently
measured wind (`configs/copernicus_wind/measured_wind.csv`):

| date | measured U10 | fitted U10 | ratio |
|---|---|---|---|
| 2023-11-04 | 17.45 m/s | 1.19 m/s | 14.7x |
| 2024-06-03 | 4.91 m/s | 0.43 m/s | 11.4x |
| 2024-07-31 | 5.29 m/s | 0.44 m/s | 12.0x |
| 2024-08-07 | 4.61 m/s | 0.78 m/s | 5.9x |
| 2024-10-03 | 4.82 m/s | 0.79 m/s | 6.1x |

The fitted layer thicknesses hitting their bounds on 3 of 5 dates is
plausibly part of the same compensation (`V0` also scales as `1/dTop`).

## Why it matters for the closed-loop evaluation

Feeding the model its *true* measured wind produces physically impossible
currents: at `U10 = 17.45 m/s` with `dTop = 32.5 m`, `V0 = 32.6 m/s`. The
model is therefore only usable with the compensating fitted wind, which means
every closed-loop Ekman condition run so far used a model whose wind-driven
term is internally inconsistent with the wind that actually blew.

This does not by itself invalidate the *fitted* Ekman condition (the fit makes
the profile match the data, which is what the feedforward consumes), but it
does mean:

1. the fitted `U10` must not be reported or interpreted as a wind speed;
2. the "true forcing" variant of the experiment cannot be run until this is
   resolved -- it is what exposed the discrepancy in the first place;
3. any conclusion about the Ekman model's *wind-driven regime* is untested,
   because no run so far has used a physically correct wind stress.

## Reproducing

```bash
python3 - <<'PY'
import math
rho, rho_air, omega, lat = 1026.0, 1.225, 7.2921e-5, 47.0
f = 2*omega*math.sin(math.radians(lat))
U10, D = 17.45, 32.5
Cd = 0.79e-3 + 0.08e-3*U10
tau = Cd*rho_air*U10**2
print("xdyn  V0 =", math.sqrt(2)*math.pi*tau/(D*f*math.sqrt(rho)), "m/s")
print("python V0 =", math.sqrt(2)*tau/(rho*f*D), "m/s")
PY
```

## Confirmation

The fix (`sqrt(rho)` -> `rho`) was applied to all three copies of the formula
-- `EkmanUWCurrentModel.cpp` (branch `fix/ekman-surface-velocity-scaling`),
`fit_ekman_profile.py`, and `lotusim_sdk/control/current_feedforward.py` --
and `U10_SAFE_MAX_MS` in the fit was raised from 6 to 25 m/s, since the
~6.7 m/s divergence that motivated the old bound is itself a symptom of the
32x overscaling.

Re-fitting then moves the fitted `U10` much closer to the independently
measured wind, which is the diagnostic this predicted:

| date | measured | fitted before | fitted after | ratio before | ratio after |
|---|---|---|---|---|---|
| 2023-11-04 | 17.45 | 1.19 | 5.66 | 14.7x | 3.1x |
| 2024-06-03 | 4.91 | 0.43 | 2.25 | 11.4x | 2.2x |
| 2024-07-31 | 5.29 | 0.44 | 2.31 | 12.0x | 2.3x |
| 2024-08-07 | 4.61 | 0.77 | 3.86 | 5.9x | **1.2x** |
| 2024-10-03 | 4.82 | 0.79 | 3.95 | 6.1x | **1.2x** |

## What it does *not* change

The fit RMSE is essentially unchanged, and so is the predicted profile: the
model is over-parameterised, so the fit reaches the same `V0` either way by
scaling `U10` by about `sqrt(32) = 5.7x` (observed: 1.19 -> 5.66, i.e. 4.8x).
Evaluating the SDK's own `EkmanCurrentModel` with the before/after parameters
at the two depths flown gives **bit-identical output on 10 of 16
date-depth cells**; only 2023-11-04 (0.027 m/s at 8 m), 2024-10-03
(0.017 / 0.006 m/s) and 2025-01-09 (0.006 / 0.038 m/s) differ.

So the fix makes the model's parameters physically interpretable and makes a
true-forcing experiment possible for the first time, but it is **not**
expected to overturn the closed-loop null result: for 10 of 16 cells the
controller sees exactly the same current as before. Only those six cells'
`ff_ekman` runs were repeated.
