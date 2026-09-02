#!/usr/bin/env python3
"""Screen candidate dates for wind strength BEFORE committing to the full,
expensive current+bathymetry download and fit pipeline.

Why this exists. extract_copernicus_wind.py's cross-check (see
summarise_measured_wind.py) found that fit_ekman_profile.py's fitted U10
badly underestimates the true wind on all five of the original study's
dates, most severely on 2023-11-04 (a Storm Ciarán day, fitted Beaufort 1
vs. measured Beaufort 8). Extending the closed-loop energy-impact evaluation
(generate_energy_trajectory_scenarios.py) to a wider, independently verified
wind range needs MORE dates to have real wind diversity -- but a full
current+bathymetry download and Ekman/Gauss-Markov fit is expensive per
date. Wind alone is cheap (~15-25 KB, a few seconds) and is the thing being
selected for, so this screens on wind FIRST and only the current profile for
whichever dates pass gets downloaded (extract_copernicus_profile.py,
separately, still manual/deliberate -- this script never downloads current
data itself).

Requires `copernicusmarine` (pip) and prior authentication
(`copernicusmarine login`, credentials cached to
~/.copernicusmarine/.copernicusmarine-credentials, never stored in this
repo). Also requires `h5py` (see extract_copernicus_wind.py).

Data availability: the near-real-time wind product used here
(cmems_obs-wind_glo_phy_nrt_l4_0.125deg_PT1H) only covers a rolling window
(~2024-06 onward at the time this was written) -- confirm the candidate
range against the dataset's own reported time bounds if a request is
rejected as out of range. The five original dates predate this
window and were pulled from a different (reanalysis) product at download
time; this script does not attempt to reproduce that for new dates.

Run from the repository root, selection region defaults to the Brest
study area:

    python3 src/simulation_run/scripts/bluerov_current_experiment/screen_copernicus_wind_dates.py \\
        --start 2024-09-01 --end 2025-03-31 --step-days 5
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_copernicus_wind import beaufort, mean_wind_speed  # noqa: E402

DATASET_ID = "cmems_obs-wind_glo_phy_nrt_l4_0.125deg_PT1H"

# Matches the Brest study region (extract_copernicus_profile.py /
# the original notebooks' minimumLongitude..maximumLatitude).
DEFAULT_BOUNDS = dict(lon_min=-6.25, lon_max=-6.0, lat_min=46.6, lat_max=47.0)


def download_wind(target_date: datetime.date, out_path: str, bounds: dict) -> bool:
    """+48h convention matching extract_copernicus_profile.py: request
    [target_date - 2 days, target_date], and extract_copernicus_wind.py's
    default --time-index -1 then reads the target_date slice."""
    start = target_date - datetime.timedelta(days=2)
    cmd = [
        "copernicusmarine", "subset",
        "--dataset-id", DATASET_ID,
        "--minimum-longitude", str(bounds["lon_min"]),
        "--maximum-longitude", str(bounds["lon_max"]),
        "--minimum-latitude", str(bounds["lat_min"]),
        "--maximum-latitude", str(bounds["lat_max"]),
        "--start-datetime", f"{start.isoformat()}T00:00:00",
        "--end-datetime", f"{target_date.isoformat()}T00:00:00",
        "--variable", "northward_wind", "--variable", "eastward_wind",
        "--output-filename", os.path.basename(out_path),
        "--output-directory", os.path.dirname(out_path) or ".",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and os.path.exists(out_path)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="first target date, YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="last target date, YYYY-MM-DD")
    ap.add_argument("--step-days", type=int, default=5,
                     help="spacing between candidate target dates (default 5)")
    ap.add_argument("--lon-min", type=float, default=DEFAULT_BOUNDS["lon_min"])
    ap.add_argument("--lon-max", type=float, default=DEFAULT_BOUNDS["lon_max"])
    ap.add_argument("--lat-min", type=float, default=DEFAULT_BOUNDS["lat_min"])
    ap.add_argument("--lat-max", type=float, default=DEFAULT_BOUNDS["lat_max"])
    ap.add_argument("--out", default="screened_wind_dates.csv")
    args = ap.parse_args()
    bounds = dict(lon_min=args.lon_min, lon_max=args.lon_max,
                  lat_min=args.lat_min, lat_max=args.lat_max)

    start = datetime.date.fromisoformat(args.start)
    end = datetime.date.fromisoformat(args.end)
    candidates = []
    d = start
    while d <= end:
        candidates.append(d)
        d += datetime.timedelta(days=args.step_days)

    print(f"Screening {len(candidates)} candidate date(s), "
          f"{args.step_days}-day spacing, {start} .. {end}")

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, target in enumerate(candidates):
            out_path = os.path.join(tmp, f"{target.isoformat()}_wind.nc")
            try:
                ok = download_wind(target, out_path, bounds)
            except subprocess.TimeoutExpired:
                ok = False
            if not ok:
                print(f"  [{i+1}/{len(candidates)}] {target}  download failed, skipped")
                continue
            speed, stamp = mean_wind_speed(out_path, time_index=-1)
            bft = beaufort(speed)
            rows.append((target.isoformat(), speed, bft))
            print(f"  [{i+1}/{len(candidates)}] {target}  "
                  f"U10={speed:6.2f} m/s  Bft={bft:2d}"
                  + ("  <-- notable" if bft >= 5 else ""))
            os.remove(out_path)

    rows.sort(key=lambda r: -r[1])
    with open(args.out, "w") as f:
        f.write("target_date,measured_u10_ms,measured_beaufort\n")
        for date, speed, bft in rows:
            f.write(f"{date},{speed:.3f},{bft}\n")

    print(f"\n{len(rows)} date(s) screened -> {args.out}, sorted by wind speed")
    print("Strongest 10:")
    for date, speed, bft in rows[:10]:
        print(f"  {date}  {speed:6.2f} m/s  Bft {bft}")


if __name__ == "__main__":
    main()
