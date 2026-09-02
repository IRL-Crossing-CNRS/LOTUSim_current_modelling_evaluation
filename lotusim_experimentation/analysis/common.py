#!/usr/bin/env python3
"""Shared loading and metric code for the three analysis scripts here.

Everything that reads a run, a fitted parameter set or a vehicle asset lives
here so the scripts cannot drift apart: the per-date tables and the aggregate
tables must be computed from the same definitions, or a reader comparing one
against the other finds numbers that disagree for no stated reason.
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import math
import os
import re
import statistics
import sys

# ---------------------------------------------------------------------------
# Where the data is
#
# Default: a local LOTUSim + LOTUSim-generic-scenario checkout, which is where
# runs land when you simulate the experiment yourself. Set LOTUSIM_EVAL_ROOT to
# this repository instead to regenerate every table straight from the released
# data, with no simulator installed -- that is the reproduction path a reader
# takes. SCENARIO_WS / LOTUSIM_WS override the checkout locations.
# ---------------------------------------------------------------------------
_SCENARIO_WS = os.environ.get(
    "SCENARIO_WS", os.path.expanduser("~/Documents/workspace/lotusim"))
_LOTUSIM_WS = os.environ.get("LOTUSIM_WS", os.path.expanduser("~/lotusim_ws"))
_SCENARIO_REPO = os.path.join(_SCENARIO_WS, "LOTUSim-generic-scenario")

_EVAL = os.environ.get("LOTUSIM_EVAL_ROOT")
if _EVAL:
    RESULTS = os.path.join(_EVAL, "lotusim_experimentation/results")
    CFG = os.path.join(_EVAL, "lotusim_experimentation/experiment/scenarios")
    ASSETS = os.path.join(_EVAL, "lotusim_experimentation/experiment/vehicle_assets/"
                                 "BlueROV2_current_fitted_ekman_{date}.yml")
else:
    RESULTS = os.path.join(_SCENARIO_REPO, "results/bluerov_environment_experiment")
    CFG = os.path.join(_SCENARIO_REPO, "src/simulation_run/config/bluerov_current_experiment")
    ASSETS = os.path.join(_LOTUSIM_WS, "src/LOTUSim/assets/models/"
                                       "bluerov2_heavy/BlueROV2_current_fitted_ekman_{date}.yml")

HERE = os.path.dirname(os.path.abspath(__file__))


def _import_ekman_model():
    """The Ekman model used to score the fit against the measured profile.

    Taken from `lotusim_sdk` rather than reimplemented here: it is a port of the
    same xdyn C++ model the simulation applied, and a second copy would be free
    to drift from it silently. A clone of LOTUSim-generic-scenario is enough --
    nothing needs building, and the module is loaded straight from its file
    rather than through the `lotusim_sdk` package, whose __init__ pulls in ROS.
    """
    try:  # an installed / sourced SDK: use it as-is
        from lotusim_sdk.control.current_feedforward import EkmanCurrentModel
        return EkmanCurrentModel
    except ImportError:
        pass

    import importlib.util

    candidates = []
    if os.environ.get("LOTUSIM_SDK_PATH"):
        candidates.append(os.path.join(os.environ["LOTUSIM_SDK_PATH"],
                                       "lotusim_sdk/control/current_feedforward.py"))
    candidates += sorted(glob.glob(os.path.join(
        _SCENARIO_WS, "*/src/lotusim_sdk/lotusim_sdk/control/current_feedforward.py")))
    for path in candidates:
        if not os.path.exists(path):
            continue
        spec = importlib.util.spec_from_file_location("_lotusim_current_feedforward", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.EkmanCurrentModel

    raise SystemExit(
        "cannot load the Ekman current model.\n"
        "The field-accuracy columns evaluate the fitted Ekman model, which lives in\n"
        "LOTUSim-generic-scenario (src/lotusim_sdk). Clone that repository -- no\n"
        "build and no ROS needed for this -- and point SCENARIO_WS at the directory\n"
        "containing it:\n"
        "    export SCENARIO_WS=<parent of LOTUSim-generic-scenario>")


EkmanCurrentModel = _import_ekman_model()

# ---------------------------------------------------------------------------
# Experiment geometry
# ---------------------------------------------------------------------------
# Depth band each transect sweeps, from generate_environment_experiment.py's
# centre +/- amplitude. Level holds one depth, so its band is a point.
BANDS = [("Level, 25 m", "flat", (25.0, 25.0)),
         ("Sweep A, 10-40 m", "shallow", (10.0, 40.0)),
         ("Sweep B, 45-75 m", "mid", (45.0, 75.0)),
         ("Sweep C, 80-110 m", "deep", (80.0, 110.0))]
CONDS = ["copernicus", "gauss", "ekman"]
METRICS = [("energy_wh", "Energy"), ("rms_cross_track_m", "Cross-track error"),
           ("rms_control_effort_N", "Control effort")]
ASSET_KEYS = ("top layer thickness", "bottom layer thickness", "current velocity",
              "current orientation", "U10", "seabed depth", "latitude")

# A date is "resolved" when the fitted wind-driven layer reaches the depths the
# vehicle flies, and "collapsed" when the fit put that layer entirely above
# them -- in which case the Ekman model has nothing depth-dependent left to
# contribute and reduces to the uniform current the baseline already applies.
RESOLVED_MIN_2DS_M = 10.0

# Measured 10 m wind (Copernicus wind product, independent of the current fit),
# Beaufort from the standard scale. Source: the candidate_screening CSV under
# scenarios/copernicus_wind/ for the wind-screened dates; computed directly
# from the raw NetCDF for dates screened before that CSV existed.
BEAUFORT = json.load(open(os.path.join(HERE, "wind_beaufort.json")))


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------
def open_csv(path):
    """Run CSVs are stored gzipped in this repository (they compress ~9x and
    are the bulk of it); a freshly simulated run writes them plain."""
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path)


def find_csv(directory):
    """The run's telemetry CSV, gzipped or not."""
    return (glob.glob(os.path.join(directory, "*.csv"))
            or glob.glob(os.path.join(directory, "*.csv.gz")))


def asset_params(date):
    """The Ekman parameters actually deployed that date, read back out of the
    vehicle YAML the simulation used -- not out of the fit that produced it."""
    p = ASSETS.format(date=date)
    if not os.path.exists(p):
        return None
    out = {}
    for line in open(p):
        m = re.match(r"\s*([a-zA-Z0-9 ]+):\s*\{\s*value:\s*([0-9.eE+-]+)", line)
        if m and m.group(1).strip() in ASSET_KEYS:
            out.setdefault(m.group(1).strip(), float(m.group(2)))
    return out


def gauss_params(date):
    """The deployed Gauss-Markov parameters for a date, or None."""
    p = os.path.join(CFG, "fitted_params_deep", f"gauss_{date}.json")
    return json.load(open(p))["fitted"] if os.path.exists(p) else None


def ekman_fit(date):
    """The Ekman fit record for a date (parameters, held-fixed values, RMSE)."""
    p = os.path.join(CFG, "fitted_params_deep", f"ekman_{date}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def summary(band, cond, date):
    f = glob.glob(f"{RESULTS}/env_{band}_{cond}_{date}/*_summary.json")
    return json.load(open(f[0])) if f else None


def complete(date):
    """A date counts only with all twelve runs and its deployed vehicle asset."""
    return asset_params(date) is not None and all(
        summary(b, c, date) for _, b, _ in BANDS for c in CONDS)


def all_dates():
    """Every date with a complete set of results, chronologically."""
    seen = {os.path.basename(d).rsplit("_", 1)[1]
            for d in glob.glob(os.path.join(RESULTS, "env_*_*_*"))}
    return sorted(d for d in seen if complete(d))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def field_accuracy(date):
    """Ekman RMSE and the single constant-baseline RMSE over the flown column.

    The deployed Gauss-Markov mean is fit to the best depth-uniform current
    over the same 0-150 m band the Ekman model is fitted on, so its field-level
    RMSE is numerically that of the uniform baseline: one constant baseline is
    reported rather than two that would print identical numbers under different
    names.
    """
    p = asset_params(date)
    rows = [(float(r["depth_m"]), float(r["vx_north_ms"]), float(r["vy_east_ms"]))
            for r in csv.DictReader(open(f"{CFG}/copernicus_profiles_deep/brest_{date}.csv"))]
    rows = [r for r in rows if r[0] <= 150]
    ek = EkmanCurrentModel(p["current velocity"], p["current orientation"],
                           p["top layer thickness"], p["bottom layer thickness"],
                           p["U10"], p.get("seabed depth", 902.0),
                           p.get("latitude", 47.0), 20.0)
    mn = statistics.fmean(r[1] for r in rows)
    me = statistics.fmean(r[2] for r in rows)

    def rmse(f):
        return math.sqrt(statistics.fmean((f(z)[0] - vx) ** 2 + (f(z)[1] - vy) ** 2
                                          for z, vx, vy in rows))

    e = rmse(lambda z: ek.current_at(z))
    u = rmse(lambda z: (mn, me))
    two_ds = 2 * p["top layer thickness"]
    return dict(date=date, bft=BEAUFORT[date], two_ds=two_ds, ek=e, unif=u,
                red=100 * (u - e) / u, resolved=two_ds >= RESOLVED_MIN_2DS_M)


def transect_layer(date, band_depths):
    """Which Ekman layer a transect flies in, from the model's own boundaries.

    The three-layer model switches branches at 2*top_layer (wind-driven layer)
    and at seabed - 2*bottom_layer (benthic layer), exactly as
    EkmanCurrentModel.current_at does; a band straddling a boundary is
    reported as mixed. Computed rather than assigned by hand so the column
    stays consistent as dates are added.
    """
    p = asset_params(date)
    lo, hi = band_depths
    top_edge = 2 * p["top layer thickness"]
    bottom_edge = p.get("seabed depth", 902.0) - 2 * p["bottom layer thickness"]
    if hi < top_edge:
        return "top"
    if lo >= top_edge and hi <= bottom_edge:
        return "mid"
    if lo > bottom_edge:
        return "bottom"
    return "mixed"


def power_trace(band, cond, date):
    d = os.path.join(RESULTS, f"env_{band}_{cond}_{date}")
    c = find_csv(d)
    if not c:
        return None
    t, p = [], []
    for r in csv.DictReader(open_csv(c[0])):
        t.append(float(r["t"]))
        p.append(float(r["power_W"]))
    return ([x - t[0] for x in t], p) if len(t) > 50 else None


def energy_to(t, p, t_end):
    """Trapezoidal integral of power up to t_end, in watt-hours."""
    e = 0.0
    for i in range(1, len(t)):
        if t[i] > t_end:
            break
        e += 0.5 * (p[i] + p[i - 1]) * (t[i] - t[i - 1])
    return e / 3600.0


def energy_cells(date):
    """Per-transect energy of the three runs, integrated over a window common
    to all three, so a few tenths of a second of duration spread cannot
    masquerade as an energy difference."""
    out = {}
    for _, band, _ in BANDS:
        tr = {c: power_trace(band, c, date) for c in CONDS}
        if not all(tr.values()):
            continue
        t_end = min(v[0][-1] for v in tr.values())
        out[band] = {c: energy_to(*tr[c], t_end) for c in CONDS}
    return out


def energy_pct(date):
    """Reference energy level and each model's signed relative departure.

    Signed on purpose: an absolute error says how far a model lands from the
    reference but not on which side, and the side is the operationally useful
    part -- a simulator that overestimates consumption sizes a battery
    conservatively, one that underestimates it plans a mission the vehicle
    cannot finish.
    """
    cells = energy_cells(date)
    ref = statistics.median(c["copernicus"] for c in cells.values())
    gm = statistics.median(100 * (c["gauss"] - c["copernicus"]) / c["copernicus"]
                           for c in cells.values())
    ek = statistics.median(100 * (c["ekman"] - c["copernicus"]) / c["copernicus"]
                           for c in cells.values())
    return dict(date=date, ref_wh=ref, gm_pct=gm, ek_pct=ek, n=len(cells))


def metric_ratio(date, band, mkey):
    """eps_GM / eps_Ekman for one metric: above 1 favours the Ekman model."""
    s = {c: summary(band, c, date) for c in CONDS}
    ref = s["copernicus"][mkey]
    eg = abs(s["gauss"][mkey] - ref) / ref
    ee = abs(s["ekman"][mkey] - ref) / ref
    return eg / ee if ee > 0 else None


def pooled_ratio(date, band):
    rs = [metric_ratio(date, band, mkey) for mkey, _ in METRICS]
    rs = [r for r in rs if r and r > 0]
    return math.exp(statistics.fmean(math.log(r) for r in rs)) if rs else None


def geo(vals):
    vals = [v for v in vals if v and v > 0]
    return math.exp(statistics.fmean(math.log(v) for v in vals))
