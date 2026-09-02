#!/usr/bin/env python3
"""Per-date energy: the reference level, and each model's signed departure.

Reported signed on purpose. An absolute error says how far a model lands from
the reference but not on which side, and the side is the operationally useful
part: a simulator that overestimates consumption sizes a battery conservatively,
one that underestimates it plans a mission the vehicle cannot finish.

Energy is integrated over a window common to the three runs of a date-transect
cell rather than taken from each run's own summary, so a few tenths of a second
of duration spread cannot masquerade as an energy difference.

Usage:
    python3 analysis/energy_table.py                  # every complete date
    python3 analysis/energy_table.py DATE [DATE ...]  # only these
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HERE, all_dates, energy_cells  # noqa: E402


def main(dates):
    dates = dates or all_dates()
    print(f"{'date':12s} {'ref Wh':>8s} {'GM Wh':>8s} {'Ek Wh':>8s} "
          f"{'GM %':>8s} {'Ek %':>8s}")
    rows = []
    for date in dates:
        cells = list(energy_cells(date).values())
        if not cells:
            continue
        ref = statistics.median(c["copernicus"] for c in cells)
        # Signed relative departure, per cell, then the median over transects.
        gm = statistics.median(100 * (c["gauss"] - c["copernicus"]) / c["copernicus"]
                               for c in cells)
        ek = statistics.median(100 * (c["ekman"] - c["copernicus"]) / c["copernicus"]
                               for c in cells)
        gmw = statistics.median(c["gauss"] - c["copernicus"] for c in cells)
        ekw = statistics.median(c["ekman"] - c["copernicus"] for c in cells)
        rows.append((date, ref, gmw, ekw, gm, ek, len(cells)))
        print(f"{date:12s} {ref:8.2f} {gmw:+8.2f} {ekw:+8.2f} {gm:+7.1f}% {ek:+7.1f}%")
    if rows:
        print(f"\nmedian |GM| = {statistics.median(abs(r[4]) for r in rows):.1f}%   "
              f"median |Ekman| = {statistics.median(abs(r[5]) for r in rows):.1f}%")
        print(f"GM over-predicts on {sum(1 for r in rows if r[4] > 0)}/{len(rows)}, "
              f"Ekman on {sum(1 for r in rows if r[5] > 0)}/{len(rows)}")
    with open(os.path.join(HERE, "energy_table.json"), "w") as f:
        json.dump([dict(zip(("date", "ref_wh", "gm_wh", "ek_wh", "gm_pct", "ek_pct", "n"), r))
                   for r in rows], f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1:])
