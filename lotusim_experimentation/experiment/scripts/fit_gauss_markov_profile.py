#!/usr/bin/env python3
"""Fit the scenario JSON's Gauss-Markov parameters to a measured deep-column
profile.

Companion to fit_ekman_profile.py, reconstructed on 2026-08-27 for the same
reason: the version previously tracked here (depth-weighted mean/std over
the 0-65 m band, writing `fitted_params/`) is not what produced
`scenarios/fitted_params_deep/`. Matched against four published dates
(2023-11-04, 2024-06-03, 2024-08-07, 2026-01-24) to the precision the JSON
files were written at. The difference from the tracked-but-wrong version:

  * `mean_x`, `mean_y`: the PLAIN (unweighted) arithmetic mean of the
    measured profile over the same 0-150 m band Ekman is fitted on -- not
    depth-weighted. Depth-weighting looked like the right correction for
    Copernicus's geometric spacing (as it is in the closed-loop energy
    study elsewhere in this repository), but it moves the fitted mean
    measurably; the tracked results are unweighted.
  * `std_dev`: `sqrt(mean(dx**2 + dy**2))` over the same unweighted 24
    samples -- i.e. exactly the RMSE of that mean against the profile, not
    a variance divided by 2 or weighted by depth span.

Both models are fit over the identical 0-150 m band and identical
(unweighted) sample set, so a difference between them is not an artefact of
one model seeing more of the water column than the other.

`tau` stays fixed at 60 s: it is a temporal decorrelation time, and a single
depth snapshot carries no information about it.

Run from a `LOTUSim-generic-scenario` checkout after `scenarios/` and
`scripts/` are copied in (see this directory's README), or directly against
this repository's own copies with `--config-dir
lotusim_experimentation/experiment/scenarios`:

    python3 scripts/fit_gauss_markov_profile.py [--dates 2025-05-20 ...]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os

CONFIG_DIR = "src/simulation_run/config/bluerov_current_experiment"
PROFILE_SUBDIR = "copernicus_profiles_deep"
OUT_SUBDIR = "fitted_params_deep"

FIT_BAND_M = 150.0
TAU_S = 60.0


def load_profile(path: str) -> list[tuple[float, float, float]]:
    """Loads the full profile and truncates to the fit band (0-150 m)."""
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append((float(row["depth_m"]), float(row["vx_north_ms"]), float(row["vy_east_ms"])))
    rows.sort()
    return [r for r in rows if r[0] <= FIT_BAND_M]


def fit(profile: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    vx = [x for _, x, _ in profile]
    vy = [y for _, _, y in profile]
    n = len(vx)
    mean_x = sum(vx) / n
    mean_y = sum(vy) / n
    var = sum((x - mean_x) ** 2 + (y - mean_y) ** 2 for x, y in zip(vx, vy)) / n
    std_dev = math.sqrt(var)
    return mean_x, mean_y, std_dev


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
        profile = load_profile(prof)
        mean_x, mean_y, std_dev = fit(profile)

        out = {
            "date": date,
            "source_profile": os.path.relpath(prof, args.config_dir),
            "fitted": {
                "mean_x": round(mean_x, 6),
                "mean_y": round(mean_y, 6),
                "std_dev": round(std_dev, 6),
                "tau": TAU_S,
            },
            "n_depth_samples": len(profile),
            "_comment": (
                "mean_x/mean_y: plain (unweighted) mean of the measured profile "
                "over 0-150 m, the same band and sample set Ekman is fitted on. "
                "std_dev: RMSE of that mean against the profile -- a SPATIAL "
                "variability proxy, not the OU process's temporal variance (see "
                "this script's module docstring). tau left at 60 s, unfit."
            ),
        }
        out_path = os.path.join(out_dir, f"gauss_{date}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        speed = math.hypot(mean_x, mean_y)
        bearing = math.degrees(math.atan2(mean_y, mean_x)) % 360.0
        print(
            f"{date}: mean=({mean_x:.4f}, {mean_y:.4f}) [{speed:.4f} m/s @ {bearing:.1f} deg]  "
            f"std_dev={std_dev:.4f} m/s  n={len(profile)}  -> {out_path}"
        )


if __name__ == "__main__":
    main()
