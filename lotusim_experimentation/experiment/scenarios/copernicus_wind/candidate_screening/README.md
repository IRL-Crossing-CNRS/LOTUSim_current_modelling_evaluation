# Candidate date screening

Output of `screen_copernicus_wind_dates.py`, kept for reference so the
stratified date selection below doesn't need re-running the sweep.

- `brest_2024-06-15_2026-08-15.csv` -- Brest study region, step 4 days.
- `raz_blanchard_2024-06-15_2026-08-15.csv` -- Raz Blanchard / Alderney
  Race (49.65-49.78N, 2.10-1.95W), step 5 days. Chosen over the
  already-downloaded Kuroshio/Japan site because Kuroshio's shear is
  geostrophic (a boundary current), which neither Ekman nor Gauss-Markov
  represents; Raz Blanchard's shear comes from tidal bottom friction plus
  Atlantic wind, the two mechanisms the Ekman model actually models.
- `extra_dates_measured_wind.csv` -- individual dates measured off-grid
  from the 4-day sweep (via `download_wind`/`mean_wind_speed` directly,
  same convention), for dates chosen to extend the closed-loop
  model-as-environment study (`../../README.md`) rather than to appear in
  the sweep itself.

Both sweep files cover the near-real-time wind product's rolling window
(roughly 2024-06 onward as of 2026-08); it cannot reach the five original
original five dates (2023-11 through 2024-10), which is why those were checked
instead with `extract_copernicus_wind.py` against separately-archived
exports (see `../measured_wind.csv`).

Every date now simulated in the model-as-environment study spans Beaufort 3
to 8 (see the study README's per-date table); this file's job is only to
provide the measured wind used to classify each date's regime and to check
new candidates before running them, not to hold a fixed target sample.
