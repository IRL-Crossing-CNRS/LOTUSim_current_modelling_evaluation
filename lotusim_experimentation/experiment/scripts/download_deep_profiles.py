#!/usr/bin/env python3
"""Download full-column (0.5-1000 m) Copernicus current profiles off Brest.

This is the download step for the current model-as-environment study: its
scenarios and fits are built from the full 0.5-1000 m column (35 depth
samples), not a shallow truncation. Fitting the Ekman model needs the depth
range that lets its layer thicknesses come off their bounds -- a shallow
(e.g. 0-70 m) profile gives too few samples for its five correlated
parameters to be identifiable, and pushes the fit into the same
constant-bias regime a depth-uniform model already covers, leaving nothing
for a depth-resolved model to add. 1000 m also matches the evaluation
domain of the environmental-fidelity table (Section IV), so that table and
this study finally describe the same water column.

Writes into <out-dir>/copernicus_profiles_deep/, matching
fit_ekman_profile.py's / fit_gauss_markov_profile.py's / generate_
environment_experiment.py's PROFILE_SUBDIR.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import subprocess
import sys

import h5py
import numpy as np

DATASET_ID = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
BOUNDS = dict(lon_min=-6.25, lon_max=-6.0, lat_min=46.6, lat_max=47.0)
MIN_DEPTH_M = 0.49
MAX_DEPTH_M = 1000.0
LABEL = "brest"
FILL_THRESHOLD = 1e30


def download(target: datetime.date, out_dir: str) -> str | None:
    """Retrieve one day's subset; returns the .nc path, or None on failure."""
    name = f"{LABEL}_deep_{target.isoformat()}.nc"
    path = os.path.join(out_dir, name)
    if os.path.exists(path):
        print(f"  {target}: deja telecharge")
        return path
    cmd = [
        "copernicusmarine", "subset", "--dataset-id", DATASET_ID,
        "--minimum-longitude", str(BOUNDS["lon_min"]),
        "--maximum-longitude", str(BOUNDS["lon_max"]),
        "--minimum-latitude", str(BOUNDS["lat_min"]),
        "--maximum-latitude", str(BOUNDS["lat_max"]),
        "--minimum-depth", str(MIN_DEPTH_M), "--maximum-depth", str(MAX_DEPTH_M),
        "--start-datetime", f"{target.isoformat()}T00:00:00",
        "--end-datetime", f"{target.isoformat()}T00:00:00",
        "--variable", "uo", "--variable", "vo",
        "-o", out_dir, "-f", name, "--overwrite",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0 or not os.path.exists(path):
        print(f"  {target}: ECHEC -- {r.stderr.strip()[:160]}")
        return None
    return path


def to_profile_csv(nc_path: str, out_csv: str) -> int:
    """Spatial-mean profile -> CSV in the schema the fit scripts expect.

    Copernicus names the eastward component ``uo`` and the northward one
    ``vo``; the fit scripts expect ``vx_north_ms``/``vy_east_ms``, so the two
    are swapped here rather than at the point of use.
    """
    with h5py.File(nc_path, "r") as f:
        depths = f["depth"][:]
        east = np.where(np.array(f["uo"])[0] > FILL_THRESHOLD, np.nan,
                        np.array(f["uo"])[0])
        north = np.where(np.array(f["vo"])[0] > FILL_THRESHOLD, np.nan,
                         np.array(f["vo"])[0])
    e = np.nanmean(east.reshape(east.shape[0], -1), axis=1)
    n = np.nanmean(north.reshape(north.shape[0], -1), axis=1)
    rows = [(float(z), float(a), float(b))
            for z, a, b in zip(depths, n, e)
            if np.isfinite(a) and np.isfinite(b)]
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["depth_m", "vx_north_ms", "vy_east_ms"])
        for z, a, b in rows:
            w.writerow([f"{z:.4f}", f"{a:.6f}", f"{b:.6f}"])
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dates", nargs="+", help="ISO dates, e.g. 2026-01-24")
    ap.add_argument("--bbox", default=None,
                    help="lon_min,lon_max,lat_min,lat_max. Default: the Brest box. "
                         "Brest is a 65 m tidal shelf where the flow is nearly "
                         "depth-uniform, i.e. the regime in which a constant is "
                         "already near-optimal and an Ekman spiral has little to "
                         "add; screening other regions needs this configurable.")
    ap.add_argument("--label", default="brest",
                    help="filename prefix for the written profiles")
    ap.add_argument("--out-dir", required=True,
                    help="config dir; profiles land in <out-dir>/copernicus_profiles_deep/")
    args = ap.parse_args()

    if args.bbox:
        lo1, lo2, la1, la2 = (float(v) for v in args.bbox.split(","))
        BOUNDS.update(lon_min=lo1, lon_max=lo2, lat_min=la1, lat_max=la2)
    prof_dir = os.path.join(args.out_dir, "copernicus_profiles_deep")
    nc_dir = os.path.join(args.out_dir, "raw_nc")
    os.makedirs(prof_dir, exist_ok=True)
    os.makedirs(nc_dir, exist_ok=True)

    global LABEL
    LABEL = args.label
    ok = 0
    for d in args.dates:
        target = datetime.date.fromisoformat(d)
        print(f"{target}: telechargement 0.5-{MAX_DEPTH_M:.0f} m ...")
        nc = download(target, nc_dir)
        if not nc:
            continue
        csv_path = os.path.join(prof_dir, f"{args.label}_{target.isoformat()}.csv")
        n = to_profile_csv(nc, csv_path)
        print(f"  -> {n} niveaux valides  {csv_path}")
        ok += 1
    print(f"\n{ok}/{len(args.dates)} profils profonds ecrits dans {prof_dir}")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
