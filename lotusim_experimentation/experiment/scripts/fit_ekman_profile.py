#!/usr/bin/env python3
"""Fit the vehicle YAML's Ekman parameters to a measured deep-column profile.

This is the script that actually produced `scenarios/fitted_params_deep/`,
reconstructed on 2026-08-27 because the one that had been tracked here
(reading/writing the shallow `copernicus_profiles`/`fitted_params`
directories, SEABED_DEPTH_M=65.0, depth-weighted residuals) was not it --
running it would neither touch the deep study's inputs nor reproduce its
outputs. Verified against four already-published dates spanning both
regimes (2023-11-04, 2024-08-07, 2024-11-30, 2026-01-24): current velocity,
orientation, top-layer thickness, U10 and RMSE all reproduce to the
precision the JSON files were written at. `bottom_layer_thickness_m` does
not reproduce exactly on dates where the top layer already covers every
sampled depth (`2*top_layer_m` exceeds the deepest sample) -- there,
`ekman_xdyn_model`'s `np.select` never reaches the bottom branch, so the
parameter has no effect on the fit and different optimiser runs converge to
different, equally arbitrary values for it. This is not a bug to fix; it is
the same "collapsed/resolved" degeneracy this study's results report, now
visible in the fitting code itself rather than only in its output.

Two things distinguish the actual recipe from the tracked-but-wrong version
this replaces, found by matching known outputs bit for bit rather than by
inspection alone:

1. Residuals are UNWEIGHTED, not depth-weighted. depth_weights() looked like
   the right thing to carry over from the shallow-study script (it corrects
   for Copernicus's geometric depth spacing), but weighting shifts every
   fitted parameter measurably -- e.g. 2023-11-04's current_velocity_ms
   changes from 0.223 (matches) to 0.142 (does not) depending on whether
   residuals are weighted. The tracked results are unweighted.
2. Reported RMSE is `sqrt(mean(dn**2 + de**2))` over the two components
   combined per depth sample, NOT
   `sqrt(mean(concatenate([dn, de])**2))` (the latter is smaller by a
   factor of sqrt(2), since concatenating first and averaging over 2N
   flattens the two components before the mean instead of combining them
   per sample).

Everything else -- the EkmanUWCurrentModel.cpp port itself, the corrected
rho/rotation physics, the multi-start optimisation to avoid the local-minimum
degeneracy documented below -- carries over from `appendix/v1`'s version of
this script, which got the model right but was pointed at the wrong
directories and depth band for this study.

**This ports xdyn's compiled model exactly**, from
`LOTUSim-Xdyn/code/xdyn/environment_models/EkmanUWCurrentModel.cpp`
(`get_UWCurrent`, `getTopLayerCurrent`, `getMiddleLayerCurrent`,
`getBottomLayerCurrent`). The top-layer wind-driven speed
`V0 = sqrt(2)*pi*wind_stress/(top_layer_m*F_TIMES_RHO)` is inversely
proportional to `top_layer_m`, and the wind stress enters as a genuine
rotation of `(windTauX, windTauY)` (`docs/EKMAN_SCALING_BUG.md`,
`appendix/v1/docs/EKMAN_IMPLEMENTATION_DIVERGENCE.md`) -- both corrected
relative to the original C++'s `sqrt(rho)` scaling and non-rotating angle
term.

Fit band: 0-150 m, matching the depth a BlueROV2 actually flies in this
study; the profile's full 0.5-1000 m column has samples out to ~900 m, of
which only the shallowest ~24 carry information relevant to this vehicle.
SEABED_DEPTH_M is fixed at 196 m (not the true ~900 m seabed) so that the
top/bottom layer bound (`SEABED_DEPTH_M/2 = 98 m`) sits just past the fit
band -- the point at which a "layer" already covers everything the vehicle
samples and the three-layer structure stops being distinguishable from a
single resolved layer. This is the origin of the reported `2D_s` range
topping out at 196 m and the sign that a fit has railed there.

U10 is FITTED, not fixed -- see the module's own multi-start rationale
below and `appendix/v1/scripts/fit_ekman_profile.py`'s longer discussion of
why (Gauss-Markov's mean/std are fit freely; pinning U10 while Ekman's other
four parameters are free would be an unfair asymmetry between the two
models' fitting procedures).

Matches every other script here: intended to run from a
`LOTUSim-generic-scenario` checkout after `scenarios/` and `scripts/`
are copied in (see this directory's README), reading/writing under
`src/simulation_run/config/bluerov_current_experiment/`. To run directly
against this repository's own tracked copies instead, pass
`--config-dir lotusim_experimentation/experiment/scenarios` from the
repository root.

Run:

    python3 scripts/fit_ekman_profile.py [--dates 2025-05-20 ...]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os

import numpy as np
from scipy.optimize import least_squares

CONFIG_DIR = "src/simulation_run/config/bluerov_current_experiment"
PROFILE_SUBDIR = "copernicus_profiles_deep"
OUT_SUBDIR = "fitted_params_deep"

FIT_BAND_M = 150.0
SEABED_DEPTH_M = 196.0
LATITUDE_DEG = 47.0
WIND_ORIENTATION_DEG = 20.0

# Constants from EkmanUWCurrentModel.cpp's parse().
RHO_KG_M3 = 1026.0
OMEGA_RAD_S = 7.2921e-5
RHO_AIR_KG_M3 = 1.225
U10_SAFE_MAX_MS = 25.0


def _wind_stress_n_m2(u10_ms: float) -> float:
    """Port of EkmanUWCurrentModel.cpp parse(): drag-coefficient bulk formula."""
    drag_coefficient = 0.79e-3 + 0.08e-3 * u10_ms if u10_ms < 20.2 else 0.002423
    return drag_coefficient * RHO_AIR_KG_M3 * u10_ms**2


# rho, not sqrt(rho) -- see docs/EKMAN_SCALING_BUG.md.
F_TIMES_RHO = 2 * OMEGA_RAD_S * math.sin(math.radians(LATITUDE_DEG)) * RHO_KG_M3
WIND_ANGLE_RAD = math.radians(WIND_ORIENTATION_DEG)
SGN_F = 1.0 if F_TIMES_RHO >= 0 else -1.0

P0 = [0.35, 30.0, 10.0, 20.0, 1.0]

# Multi-start initial guesses (top_layer_m, bottom_layer_m, U10_ms), spanning
# the thin/thick-layer and weak/strong-wind corners of the box. A single
# start converges to different local minima on different dates.
P0_STARTS = [
    (10.0, 20.0, 1.0),
    (2.0, 5.0, 3.0),
    (30.0, 40.0, 8.0),
    (80.0, 60.0, 15.0),
    (150.0, 90.0, 12.0),
    (0.6, 0.6, 5.0),
]


def bounds() -> tuple[list[float], list[float]]:
    return (
        [0.0, -360.0, 0.5, 0.5, 0.0],
        [2.0, 360.0, SEABED_DEPTH_M / 2, SEABED_DEPTH_M / 2, U10_SAFE_MAX_MS],
    )


def ekman_xdyn_model(
    depths: np.ndarray,
    current_velocity: float,
    current_orientation_deg: float,
    top_layer_m: float,
    bottom_layer_m: float,
    u10_ms: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Predicted (north, east) m/s at each depth, from xdyn's compiled model."""
    depths = np.asarray(depths, dtype=float)
    seabed_height = SEABED_DEPTH_M
    wind_stress = _wind_stress_n_m2(u10_ms)

    theta_mid = math.radians(current_orientation_deg)
    mid_n = current_velocity * math.cos(theta_mid)
    mid_e = current_velocity * math.sin(theta_mid)

    V0 = math.sqrt(2) * math.pi * wind_stress / (top_layer_m * F_TIMES_RHO)
    decay = top_layer_m / math.pi
    phase = math.pi / 4 - depths / decay + SGN_F * WIND_ANGLE_RAD
    top_n = mid_n + SGN_F * V0 * np.exp(-depths / decay) * np.cos(phase)
    top_e = mid_e + V0 * np.exp(-depths / decay) * np.sin(phase)

    depth_factor = math.pi * (seabed_height - depths) / bottom_layer_m
    e = np.exp(-depth_factor)
    c = np.cos(depth_factor)
    s = np.sin(depth_factor)
    bot_n = mid_n * (1.0 - e * c) - mid_e * e * s
    bot_e = mid_n * e * s + mid_e * (1.0 - e * c)

    mid_n_arr = np.full_like(depths, mid_n)
    mid_e_arr = np.full_like(depths, mid_e)
    zero_arr = np.zeros_like(depths)

    top_cond = (depths > 0.0) & (depths < 2 * top_layer_m)
    mid_cond = (depths >= 2 * top_layer_m) & (depths <= seabed_height - 2 * bottom_layer_m)
    bottom_cond = (depths > seabed_height - 2 * bottom_layer_m) & (depths < seabed_height)

    north = np.select([top_cond, mid_cond, bottom_cond], [top_n, mid_n_arr, bot_n], default=zero_arr)
    east = np.select([top_cond, mid_cond, bottom_cond], [top_e, mid_e_arr, bot_e], default=zero_arr)
    return north, east


def load_profile(path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Loads the full profile and truncates to the fit band (0-150 m)."""
    depths, vx, vy = [], [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            depths.append(float(row["depth_m"]))
            vx.append(float(row["vx_north_ms"]))
            vy.append(float(row["vy_east_ms"]))
    order = np.argsort(depths)
    d, x, y = np.array(depths)[order], np.array(vx)[order], np.array(vy)[order]
    mask = d <= FIT_BAND_M
    return d[mask], x[mask], y[mask]


def fit(depths: np.ndarray, vx: np.ndarray, vy: np.ndarray) -> tuple[list[float], float, list[str]]:
    def residuals(p):
        n, e = ekman_xdyn_model(depths, *p)
        return np.concatenate([n - vx, e - vy])

    lo, hi = bounds()
    result = None
    for top0, bot0, u0 in P0_STARTS:
        start = [P0[0], P0[1], top0, bot0, u0]
        start = [min(max(v, l), h) for v, l, h in zip(start, lo, hi)]
        try:
            cand = least_squares(residuals, start, bounds=(lo, hi))
        except Exception:
            continue
        if result is None or cand.cost < result.cost:
            result = cand
    if result is None:
        raise RuntimeError("every multi-start fit failed")

    n, e = ekman_xdyn_model(depths, *result.x)
    rn, re = n - vx, e - vy
    rmse = float(np.sqrt(np.mean(rn**2 + re**2)))

    names = ("current_velocity_ms", "current_orientation_deg",
             "top_layer_thickness_m", "bottom_layer_thickness_m", "U10_ms")
    railed = []
    for name, v, l, h in zip(names, result.x, lo, hi):
        span = h - l
        if span > 0 and (v - l < 0.01 * span or h - v < 0.01 * span):
            railed.append(name)
    return [float(v) for v in result.x], rmse, railed


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config-dir", default=CONFIG_DIR)
    ap.add_argument("--dates", nargs="+", default=None,
                     help="fit only these dates; default: every profile present")
    args = ap.parse_args()

    profile_dir = os.path.join(args.config_dir, PROFILE_SUBDIR)
    out_dir = os.path.join(args.config_dir, OUT_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)

    if args.dates:
        profiles = [os.path.join(profile_dir, f"brest_{d}.csv") for d in args.dates]
        missing = [p for p in profiles if not os.path.exists(p)]
        if missing:
            raise SystemExit(f"no profile for: {', '.join(missing)}")
    else:
        profiles = sorted(glob.glob(os.path.join(profile_dir, "*.csv")))
        if not profiles:
            raise SystemExit(f"no profiles in {profile_dir}")

    for prof in profiles:
        date = os.path.splitext(os.path.basename(prof))[0].split("_", 1)[-1]
        depths, vx, vy = load_profile(prof)
        params, rmse, railed = fit(depths, vx, vy)
        current_velocity, current_orientation, top_layer, bottom_layer, u10 = params

        out = {
            "date": date,
            "source_profile": os.path.relpath(prof, args.config_dir),
            "fitted": {
                "current_velocity_ms": round(current_velocity, 4),
                "current_orientation_deg": round(current_orientation % 360.0, 2),
                "top_layer_thickness_m": round(top_layer, 3),
                "bottom_layer_thickness_m": round(bottom_layer, 3),
                "U10_ms": round(u10, 4),
            },
            "held_fixed": {
                "seabed_depth_m": SEABED_DEPTH_M,
                "latitude_deg": LATITUDE_DEG,
                "wind_orientation_deg": WIND_ORIENTATION_DEG,
            },
            "fit_rmse_ms": round(rmse, 5),
            "railed_parameters": railed,
            "n_depth_samples": int(len(depths)),
            "_comment": (
                "Fit of xdyn's compiled `ekman current` model (ported exactly "
                "from EkmanUWCurrentModel.cpp) to the measured profile above, "
                "truncated to 0-150 m and fit unweighted. U10 is fitted, not "
                "pinned -- see this script's module docstring."
            ),
        }
        out_path = os.path.join(out_dir, f"ekman_{date}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        two_ds = 2 * top_layer
        print(
            f"{date}: v={current_velocity:.4f} m/s  orient={current_orientation % 360.0:.1f} deg  "
            f"2Ds={two_ds:.1f} m ({'resolved' if two_ds >= 10.0 else 'collapsed'})  "
            f"U10={u10:.3f} m/s  rmse={rmse:.5f} m/s  n={len(depths)}"
            + (f"  [railed: {', '.join(railed)}]" if railed else "")
            + f"  -> {out_path}"
        )


if __name__ == "__main__":
    main()
