#!/usr/bin/env python3
"""Regenerate the per-date tables in experiment/README.md.

The summary tables report the two-regime aggregate; these are the per-date
detail behind them -- every date, every transect. They are generated rather
than maintained by hand, so that adding dates is one command and every column
in them has a stated definition.

Three tables are written, between the markers in that README:

  fitted-params    what was actually deployed that date (read back out of the
                   vehicle YAML and the Gauss-Markov scenario parameters)
  field-accuracy   how well each model fits the measured 0-150 m column
  closed-loop      per-transect eps_GM/eps_Ekman, and the energy departure

Usage:
    python3 analysis/per_date_tables.py            # print to stdout
    python3 analysis/per_date_tables.py --write    # splice into the README
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (BANDS, HERE, all_dates, asset_params, energy_pct,  # noqa: E402
                    field_accuracy, gauss_params, geo, pooled_ratio,
                    transect_layer)

README = os.path.normpath(os.path.join(HERE, "..", "experiment", "README.md"))
MARKERS = ("fitted-params", "field-accuracy", "closed-loop")


def fitted_params_table(dates):
    out = ["| date | Bft | v (m/s) | orient (deg) | top layer (m) | "
           "bottom layer (m) | U10 (m/s) | GM mean_x | GM mean_y | GM std_dev |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for d in dates:
        p = asset_params(d)
        g = gauss_params(d)
        fa = field_accuracy(d)
        out.append(
            f"| {d} | {fa['bft']} | {p['current velocity']:.3f} | "
            f"{p['current orientation']:.1f} | {p['top layer thickness']:.2f} | "
            f"{p['bottom layer thickness']:.2f} | {p['U10']:.2f} | "
            f"{g['mean_x']:+.4f} | {g['mean_y']:+.4f} | {g['std_dev']:.4f} |")
    return "\n".join(out)


def field_accuracy_table(dates):
    out = ["| date | Bft | regime | 2Ds (m) | eps_Ekman | eps_const | reduction (%) |",
           "|---|---|---|---|---|---|---|"]
    for d in dates:
        fa = field_accuracy(d)
        out.append(
            f"| {d} | {fa['bft']} | {'resolved' if fa['resolved'] else 'collapsed'} | "
            f"{fa['two_ds']:.0f} | {fa['ek']:.4f} | {fa['unif']:.4f} | {fa['red']:.0f} |")
    return "\n".join(out)


def closed_loop_table(dates):
    out = ["| date | Bft | 2Ds (m) | " +
           " | ".join(f"{label.split(',')[0]} (layer)" for label, _, _ in BANDS) +
           " | pooled ratio | ref (Wh) | GM (%) | Ekman (%) |",
           "|---|---|" + "---|" * (len(BANDS) + 5)]
    for d in dates:
        fa = field_accuracy(d)
        en = energy_pct(d)
        cells = []
        for _, band, depths in BANDS:
            r = pooled_ratio(d, band)
            cells.append(f"{r:.2f} ({transect_layer(d, depths)})" if r else "-")
        pooled = geo([pooled_ratio(d, b) for _, b, _ in BANDS])
        out.append(f"| {d} | {fa['bft']} | {fa['two_ds']:.0f} | " + " | ".join(cells) +
                   f" | {pooled:.2f} | {en['ref_wh']:.1f} | "
                   f"{en['gm_pct']:+.1f} | {en['ek_pct']:+.1f} |")
    return "\n".join(out)


TABLES = {"fitted-params": fitted_params_table,
          "field-accuracy": field_accuracy_table,
          "closed-loop": closed_loop_table}


def splice(text, name, table):
    """Replace what lies between this table's markers, leaving them in place."""
    start, end = f"<!-- BEGIN {name} -->", f"<!-- END {name} -->"
    i, j = text.find(start), text.find(end)
    if i < 0 or j < 0:
        raise SystemExit(f"markers for {name} not found in {README}")
    return text[:i + len(start)] + "\n" + table + "\n" + text[j:]


def main(write):
    dates = all_dates()
    print(f"dates: {len(dates)}", file=sys.stderr)
    if not write:
        for name in MARKERS:
            print(f"\n<!-- {name} -->\n{TABLES[name](dates)}")
        return
    text = open(README).read()
    for name in MARKERS:
        text = splice(text, name, TABLES[name](dates))
    open(README, "w").write(text)
    print(f"updated {README} ({len(dates)} dates)", file=sys.stderr)


if __name__ == "__main__":
    main("--write" in sys.argv[1:])
