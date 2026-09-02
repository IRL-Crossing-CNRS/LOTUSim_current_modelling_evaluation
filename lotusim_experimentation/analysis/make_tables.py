#!/usr/bin/env python3
"""Regenerate the summary tables: field accuracy and closed-loop margin,
aggregated by regime, from the raw runs and the deployed vehicle assets.

Two things this script exists to keep honest:

1. The deployed Gauss-Markov mean is fit to match the best-fitting depth-
   uniform current over the same 0-150 m band the Ekman model is fitted on
   (see fit_gauss_markov_profile.py) -- confirmed against the actual scenario
   JSON, not assumed. Its field-level RMSE against the measured profile is
   therefore numerically identical to the uniform baseline's, so one constant
   baseline is reported rather than two which would silently print the same
   numbers twice under different names.
2. Closed-loop comparisons are reported as the geometric-mean ratio
   eps_GM/eps_Ekman with a binomial sign test, not as raw win counts, so the
   result carries a p-value rather than "5 of 6 runs".

Both summary tables are aggregated by regime (whether the fitted wind-driven
layer reaches the sampled depths) because a per-date table stops being
readable past about fifteen rows; the per-date detail is what
per_date_tables.py writes.

Writes regimes.json next to this script: the date lists the other scripts and
the README's per-date tables are keyed on.

Usage:
    python3 analysis/make_tables.py                  # every complete date
    python3 analysis/make_tables.py DATE [DATE ...]  # only these
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (BANDS, CONDS, HERE, METRICS, all_dates, complete,   # noqa: E402
                    energy_pct, field_accuracy, geo, metric_ratio, pooled_ratio)
from scipy import stats as spstats  # noqa: E402


def sign_test(vals):
    wins = sum(1 for v in vals if v > 1)
    n = len(vals)
    return wins, n, spstats.binomtest(wins, n, 0.5).pvalue if n else float("nan")


def main(dates):
    dates = sorted(d for d in dates if complete(d)) if dates else all_dates()
    print(f"complete dates: {len(dates)}", file=sys.stderr)
    fa = {d: field_accuracy(d) for d in dates}
    en = {d: energy_pct(d) for d in dates}
    res = sorted(d for d in dates if fa[d]["resolved"])
    col = sorted(d for d in dates if not fa[d]["resolved"])
    print(f"resolved ({len(res)}): {res}\ncollapsed ({len(col)}): {col}", file=sys.stderr)

    def fa_row(group):
        b = [fa[d]["bft"] for d in group]
        t = [fa[d]["two_ds"] for d in group]
        return dict(n=len(group), bft=(min(b), max(b)), two_ds=(min(t), max(t)),
                    ek=statistics.median(fa[d]["ek"] for d in group),
                    unif=statistics.median(fa[d]["unif"] for d in group),
                    red=statistics.median(fa[d]["red"] for d in group))

    def cl_transect(group):
        return {label: geo([pooled_ratio(d, b) for d in group])
                for label, b, _ in BANDS}

    def cl_metric(group):
        out = {}
        for mkey, name in METRICS:
            vals = [metric_ratio(d, b, mkey) for d in group for _, b, _ in BANDS]
            out[name] = geo(vals)
        return out

    def en_row(group):
        ref = statistics.median(en[d]["ref_wh"] for d in group)
        gm = statistics.median(en[d]["gm_pct"] for d in group)
        ek = statistics.median(en[d]["ek_pct"] for d in group)
        closer = sum(1 for d in group if abs(en[d]["ek_pct"]) < abs(en[d]["gm_pct"]))
        below = sum(1 for d in group if en[d]["ek_pct"] < 0)
        _, _, p_below = sign_test([2 if en[d]["ek_pct"] < 0 else 0 for d in group])
        # Magnitude test: is Ekman's |departure| paired-significantly smaller than
        # Gauss-Markov's, date by date? Distinct from p_below, which tests DIRECTION
        # (does a model's error lean one way), not size -- the two can and do differ,
        # e.g. a model with no directional bias can still be reliably more accurate.
        mag_diffs = [abs(en[d]["gm_pct"]) - abs(en[d]["ek_pct"]) for d in group]
        p_closer = (spstats.wilcoxon(mag_diffs).pvalue
                    if any(d != 0 for d in mag_diffs) else float("nan"))
        return dict(ref=ref, gm=gm, ek=ek, closer=(closer, len(group)),
                    below=(below, len(group)), p_below=p_below, p_closer=p_closer)

    out = {}
    for name, g in (("resolved", res), ("collapsed", col), ("all", dates)):
        pooled_vals = [pooled_ratio(d, b) for d in g for _, b, _ in BANDS]
        w, n, p = sign_test(pooled_vals)
        out[name] = dict(fa=fa_row(g), transect=cl_transect(g), metric=cl_metric(g),
                         energy=en_row(g), pooled_ratio=geo(pooled_vals),
                         pooled_wins=(w, n), pooled_p=p, dates=g)
        print(f"\n{name} n={len(g)} Bft{out[name]['fa']['bft']} "
              f"2Ds{out[name]['fa']['two_ds']}  fieldRMSE ek={out[name]['fa']['ek']:.4f} "
              f"unif={out[name]['fa']['unif']:.4f} red={out[name]['fa']['red']:.1f}%  "
              f"pooled_ratio={out[name]['pooled_ratio']:.2f} wins={w}/{n} p={p:.3f}")
        print(f"  energy: ref={out[name]['energy']['ref']:.1f}Wh "
              f"GM={out[name]['energy']['gm']:+.1f}% Ek={out[name]['energy']['ek']:+.1f}% "
              f"closer={out[name]['energy']['closer']} p_closer={out[name]['energy']['p_closer']:.4f} "
              f"below={out[name]['energy']['below']} p_below={out[name]['energy']['p_below']:.3f}")
        print("  per transect: " + "  ".join(
            f"{label}={out[name]['transect'][label]:.2f}" for label, _, _ in BANDS))
        print("  per metric:   " + "  ".join(
            f"{k}={v:.2f}" for k, v in out[name]['metric'].items()))

    # Does the closed-loop margin track the fitted layer extent continuously,
    # rather than just splitting by regime? Each date's four transects are
    # pooled first (one ratio per date, same unit as the date-level Wilcoxon
    # above) and correlated against that date's 2Ds.
    date_ratio = {d: geo([pooled_ratio(d, b) for _, b, _ in BANDS]) for d in dates}
    rho, rho_p = spstats.spearmanr([fa[d]["two_ds"] for d in dates],
                                   [date_ratio[d] for d in dates])
    print(f"\ndate-pooled ratio vs 2Ds, all {len(dates)} dates: "
          f"Spearman rho={rho:.3f} p={rho_p:.3f}")

    with open(os.path.join(HERE, "regimes.json"), "w") as f:
        json.dump({"resolved": res, "collapsed": col, "all": dates,
                   "field_accuracy": fa, "energy": en}, f, indent=2)
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
