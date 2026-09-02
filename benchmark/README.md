# Environmental-fidelity benchmark

**Standalone — does not need LOTUSim, LOTUSim-generic-scenario or
LOTUSim-Xdyn.** Everything here is Jupyter/Python, run in place.

Question: does the layered Ekman current model reproduce a real, measured
current profile more faithfully than the spatially-uniform Gauss-Markov
process conventionally used for ocean currents in Gazebo-based marine
simulators (UUVSim/DAVE)? Real profiles come from the
[Copernicus Marine Data Store](https://data.marine.copernicus.eu/products),
in the Bay of Brest.

## Layout

- `Code/` — one notebook per evaluation date
  (`benchmark_UWcurrent_brest.ipynb`, `..._2.ipynb`, …), each of which:
  1. downloads/loads that date's Copernicus current export
     (`DataOcean/<window>/brest/`, one 48h window per date, 6h resolution),
  2. runs the Gauss-Markov and Ekman reference implementations (below) over
     the same window,
  3. compares both against the measured profile (MAE/RMSE per depth layer)
     and plots the result.

  `info_experiments.ipynb` collects notes on the evaluation dates and data
  windows. `DataOcean/` holds the raw and intermediate Copernicus exports
  the notebooks read, one subfolder per 48h window.

- `reference_implementations/` — the two current models being compared,
  kept as **standalone code, independent of the LOTUSim/xdyn engine**, so
  the notebooks' comparison isn't circular (a bug shared between "the model
  under test" and "the model producing the ground truth" would hide itself):
  - `gauss_markov_uuvsim/` — the actual Gazebo/UUVSim Gauss-Markov current
    plugin (C++, `libGaussMarkov.so`), the real baseline being compared
    against, not a reimplementation of it. See its own
    [Readme.md](reference_implementations/gauss_markov_uuvsim/Readme.md) for
    build/run instructions (Gazebo + CMake required).
  - `python_ekman/` — the original Python prototype of the layered Ekman
    model, predating the C++ implementation that runs inside `LOTUSim-Xdyn`
    at simulation time. Entry points: `Test_Bench.py` (batch-runs the
    current/seabed/wave models and writes CSVs to `output/`),
    `visualisation.py` (animated 3D view of the same), `EOF.py` /
    `Profile_Interpolation.py` (data-reduction utilities used by the
    notebooks). Model code lives under `classes/underwater/`,
    `classes/surface/`, `classes/utils/`.

## Running a notebook

Each notebook is self-contained: open it in Jupyter and run top to bottom.
The first code cell installs its own dependencies
(`copernicusmarine`, `cartopy`) if missing. No repo-wide Python environment
or `requirements.txt` is assumed — each notebook manages its own.

## Relation to the LOTUSim half of this repo

This benchmark's result — that Ekman fits measured profiles better than
Gauss-Markov — is the *motivation* for the closed-loop BlueROV2 comparison
in [../lotusim_experimentation/](../lotusim_experimentation/), but the two
are otherwise independent: this benchmark's fitted Ekman/Gauss-Markov
parameters are derived separately by
`lotusim_experimentation/experiment/scripts/fit_ekman_profile.py` and
`lotusim_experimentation/experiment/scripts/fit_gauss_markov_profile.py` against
xdyn's own compiled model, not imported from here.
