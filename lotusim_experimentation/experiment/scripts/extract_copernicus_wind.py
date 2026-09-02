#!/usr/bin/env python3
"""Extract the MEASURED wind speed and Beaufort class for a Copernicus export,
as an independent cross-check on the Ekman model's own FITTED U10.

Why this exists. fit_ekman_profile.py's fitted U10 is not a wind
measurement: it is whichever value, together with the other four fitted
parameters, makes the Ekman model's current profile best match the measured
CURRENT profile. Nothing constrains it to match the true wind. Checking it
against `wind.nc` -- the Copernicus wind product downloaded alongside the
current export, independent of any fit -- turned up a large discrepancy on
2023-11-04: fitted U10 1.19 m/s (Beaufort 1) vs. measured 17.45 m/s
(Beaufort 8, consistent with Storm Ciarán, which made landfall in Brittany
2023-11-01/02). The other four dates are also underestimated (measured
Beaufort 3, fitted Beaufort 1), just less dramatically. See
docs/PARAMETERS.md for the full comparison table.

Same spatial/temporal reduction as extract_copernicus_profile.py: mean over
every grid cell of the study region (a wind field, so no depth axis), at one
time slice (`--time-index`, default the last = same +48h target as the
current profile it is checked against -- MUST be run with the same
`--time-index` to be a fair comparison).

Input: `wind.nc` as downloaded by the Copernicus Marine toolbox
(`stress-equivalent wind at 10 m`, i.e. already U10; variables
`eastward_wind`/`northward_wind`, NetCDF4/HDF5, `scale_factor`/`add_offset`/
`_FillValue` per CF conventions). Requires `h5py` (not `netCDF4`, to keep the
dependency footprint small: h5py reads the file's raw HDF5 layer directly,
which is enough since the packing here needs no interpolation or CRS
machinery).

Run from the repository root:

    python3 src/simulation_run/scripts/bluerov_current_experiment/extract_copernicus_wind.py \\
        <path to wind.nc>
"""

from __future__ import annotations

import argparse
import datetime

import h5py
import numpy as np

# WMO Beaufort scale lower bounds in m/s, as used throughout this repository
# (tab:beaufort_douglas): class i is assigned to the highest i whose bound
# the wind speed meets or exceeds.
BEAUFORT_LOWER_BOUNDS_MS = [
    0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7,
]


def beaufort(u10_ms: float) -> int:
    return sum(u10_ms >= b for b in BEAUFORT_LOWER_BOUNDS_MS)


def mean_wind_speed(path: str, time_index: int) -> tuple[float, str]:
    with h5py.File(path, "r") as f:
        ew, nw = f["eastward_wind"], f["northward_wind"]
        sf, off = ew.attrs["scale_factor"], ew.attrs["add_offset"]
        fill = ew.attrs["_FillValue"]
        t = int(f["time"][time_index])
        stamp = (
            datetime.datetime(1990, 1, 1) + datetime.timedelta(seconds=t)
        ).isoformat()
        e = np.where(ew[time_index] == fill, np.nan, ew[time_index] * sf + off)
        n = np.where(nw[time_index] == fill, np.nan, nw[time_index] * sf + off)
        speed = np.sqrt(e**2 + n**2)
        mean_speed = float(np.nanmean(speed))
    return mean_speed, stamp


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("source", help="Copernicus wind.nc to read")
    ap.add_argument(
        "--time-index", type=int, default=-1,
        help="which hourly time slice to use (default -1, the last; must "
             "match the --time-index used for the paired current profile)",
    )
    args = ap.parse_args()

    speed, stamp = mean_wind_speed(args.source, args.time_index)
    bft = beaufort(speed)
    print(f"{args.source}")
    print(f"  time slice     {stamp}")
    print(f"  mean U10       {speed:.3f} m/s")
    print(f"  Beaufort       {bft}")


if __name__ == "__main__":
    main()
