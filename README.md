# LOTUSim Current Modelling Evaluation

Reproducible evaluation suite for underwater current models (Gauss-Markov,
Ekman, Copernicus-measured) and their closed-loop impact on a BlueROV2
controlled with [LOTUSim](https://github.com/IRL-Crossing-CNRS/LOTUSim).

It contains everything needed to reproduce two evaluations:

1. **Environmental fidelity**: does the Ekman-layer model reproduce a
   measured Copernicus current profile more faithfully than the
   Gauss-Markov process used by UUVSim/DAVE?
2. **Model-as-environment evaluation**: with the vehicle and its PID
   controller held identical, does simulating in one current model rather
   than the other change the trajectory, the tracking error and the energy a
   mission costs — and on which dates and at which depths does it not matter
   at all? Each date is flown in four depth bands under three environments
   (measured Copernicus profile, Gauss-Markov, fitted Ekman), the measured
   profile being the reference the other two are read against.

The superseded feedforward and energy-impact studies — where the applied
current was always the measured profile and only the *controller's belief*
changed — are archived on the `appendix/superseded-experiments` branch, with
their own README explaining what each asked and why it was abandoned. Nothing
on this branch depends on them.

## Dependencies

This repository holds only the evaluation-specific configuration, scenario
generation, run orchestration, and result-analysis code. It depends on three
simulator repositories, built at the `main` branch commit used to produce
the results in `lotusim_experimentation/results/`:

- [LOTUSim](https://github.com/IRL-Crossing-CNRS/LOTUSim) —
  core simulation engine and physics interface, including the
  `CopernicusCurrent` source used to replay measured profiles
- [LOTUSim-generic-scenario](https://github.com/IRL-Crossing-CNRS/LOTUSim-generic-scenario) —
  scenario orchestration, agent SDK (`lotusim_sdk`), and the BlueROV2 GNC
  package (`bluerov_gnc`: guidance, control, feedforward, metrics recorder)
  that this repo's scenarios and scripts drive
- [LOTUSim-Xdyn](https://github.com/naval-group/LOTUSim-Xdyn) — ship/vehicle
  dynamics physics backend (Fossen equations of motion)

## Layout

Two independent halves, one folder each — the directory structure itself is
the answer to "does this need LOTUSim". Neither half needs the other to
run, but the second reuses the first's fitted current parameters (see
"Reproducing results").

```
benchmark/                    standalone — no LOTUSim checkout needed
lotusim_experimentation/      requires LOTUSim, LOTUSim-generic-scenario, LOTUSim-Xdyn
├── experiment/               scenarios, generators/drivers, vehicle assets
└── results/                  recorded runs, aggregates, figures
```

The superseded studies live on the `appendix/superseded-experiments` branch
rather than in a folder here, so that a clone of this branch carries only what
reproducing the current results needs.

**`benchmark/` — standalone, Python/Jupyter only.** Environmental-fidelity
evaluation: does the Ekman model fit a measured Copernicus profile better
than Gauss-Markov? Notebooks + reference implementations of both current
models, run and compared in-place, no simulator involved. See
[benchmark/README.md](benchmark/README.md).

**`lotusim_experimentation/` — feeds into / is produced by a LOTUSim run.**
Nothing in here runs a simulation by itself; it's data and tooling for a
`LOTUSim-generic-scenario` checkout. New to LOTUSim? Start with
[lotusim_experimentation/README.md](lotusim_experimentation/README.md) —
it defines the terms (agent, scenario, task, GNC split, xdyn) the
sub-folder READMEs below assume:

- `experiment/` — everything needed to reproduce the current study:
  one scenario JSON per (transect shape, environment, date) under
  `scenarios/`, the generators/drivers under `scripts/`, and the per-date
  fitted vehicle YAMLs under `vehicle_assets/`. See
  [lotusim_experimentation/experiment/README.md](lotusim_experimentation/experiment/README.md).
- `results/` — every run's recorded CSVs, `*_summary.json`, aggregates and
  figures, checked in so the analysis can be re-run without re-simulating.

### A note on paths inside `experiment/`

`experiment/{scenarios,scripts}/` are flat folders here, but the
scripts (and some docs) reference paths as they exist **after being copied
into `LOTUSim-generic-scenario`** — that's where they actually run. See
[lotusim_experimentation/experiment/README.md](lotusim_experimentation/experiment/README.md)
for the copy targets.

## Reproducing results

There are two entry points, and the cheap one is worth trying first.

### Without a simulator — re-derive every reported number from this repository

`lotusim_experimentation/results/` holds all 480 runs (40 dates x 4 transects x
3 environments) exactly as recorded, so the whole analysis can be re-run
without installing anything simulator-side:

```bash
export LOTUSIM_EVAL_ROOT=/path/to/this/repository
python3 scripts/make_tables.py $(python3 -c "import json;print(' '.join(json.load(open('scripts/regimes.json'))['all']))")
```

(`make_tables.py` lives in the analysis repository; pointing `LOTUSIM_EVAL_ROOT`
at this one makes it read the released data rather than a local simulator
checkout.) Every table in the study regenerates from these files alone.

Run telemetry is stored gzipped (`*.csv.gz`) — it compresses about nine-fold and
is otherwise the bulk of the repository. The readers open either form, so a
freshly simulated run, which writes plain CSV, needs no conversion.

### With a simulator — re-run the experiment itself

1. Clone and build `LOTUSim` and `LOTUSim-generic-scenario` (branch `main` of
   each) per their own READMEs, then source both `install/setup.bash`. The
   xdyn binary is tracked inside `LOTUSim`, so `LOTUSim-Xdyn` only needs
   cloning to change the C++ current models themselves.
2. Copy `lotusim_experimentation/experiment/vehicle_assets/*.yml` into
   `LOTUSim/assets/models/bluerov2_heavy/` (or symlink them).
3. Copy `lotusim_experimentation/experiment/scenarios/` into
   `LOTUSim-generic-scenario/config/bluerov_current_experiment/`, and
   `lotusim_experimentation/experiment/scripts/` into
   `LOTUSim-generic-scenario/scripts/bluerov_current_experiment/`.
4. Run `lotusim_experimentation/experiment/run_experiment.sh`. With no
   arguments it simulates the whole experiment; cells that already have a
   result are skipped, so it is equally the command for resuming an
   interrupted batch or for adding a newly generated date. Every run is
   verified by the summary file it is supposed to produce, and anything
   missing at the end is reported as a failure. See
   [lotusim_experimentation/experiment/README.md](lotusim_experimentation/experiment/README.md)
   for the date-selection workflow, the timing, and the Unity requirement.

   One run takes about six minutes, so the full 40-date experiment is roughly
   50 hours of wall clock. The scenario files define exactly the 40 dates
   reported; nothing else is left in the config directory, so a full run
   reproduces the reported set rather than a superset of it.

   In parallel, the environmental-fidelity comparison runs standalone from
   the notebooks under `benchmark/Code/` — no LOTUSim needed.
5. Regenerate the tables as above, leaving `LOTUSIM_EVAL_ROOT` unset so the
   scripts read your own freshly simulated results instead.

The previous version of this study — shallow-column only, closed-loop
feedforward-benefit rather than model-as-environment — is preserved in its
entirety on the `appendix/superseded-experiments` branch, including its own
README chain, but is not part of reproducing the current results above.

## License

Eclipse Public License 2.0 (see `LICENSE`).
