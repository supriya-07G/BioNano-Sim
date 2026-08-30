# COSMORA

**Computational triage of protein domains as nanoscale mechanical components**

COSMORA measures how much load-bearing capacity a protein domain loses when
individual residues are damaged. It runs real molecular dynamics, pulls the
domain apart under a calibrated force, and reports the change in stiffness in
piconewtons per nanometre.

The question it answers is concrete: **if this residue is lost, how much of the
structure's mechanical function goes with it?**

## The headline result

Run blind across 13 protein domains — 520 paired simulations, 71 minutes — the
measurement ranked the known load-bearing folds first, without being told
anything about their mechanics:

| Domain | Stiffness (pN/nm) | Fit r² |
| --- | --- | --- |
| **1TIT** titin I27 | **713 ± 121** | 0.82 |
| **1UBQ** ubiquitin | **661 ± 142** | 0.77 |
| **1WIT** twitchin Ig | **645 ± 135** | 0.70 |
| **1AKI** lysozyme | **492 ± 94** | 0.52 |
| nine α-helical and loop-rich domains | ≤ 114 | ≤ 0.33 |

Titin I27 is the standard benchmark of mechanical stability in AFM force
spectroscopy. COSMORA placed it first. The separation between the load-bearing
group and the rest is complete — no overlap in stiffness or in fit quality.

Full analysis, including two quantified null results and their power analysis:
**[docs/RESULTS.md](docs/RESULTS.md)**.

## What it does

| Capability | What it is | Label used throughout |
| --- | --- | --- |
| Mechanical pulling | Constant-velocity steered MD on the terminal Cα distance, giving a force-extension curve and an apparent stiffness in pN/nm | **Steered MD Force-Extension (non-equilibrium)** |
| Molecular dynamics | Real OpenMM run, Amber14 + GBn2 implicit solvent, picosecond scale | **Rapid OpenMM Simulation** |
| Structural analysis | RMSD, RMSF, radius of gyration, energies from the real trajectory | **Simulation-derived degradation proxy** |
| Degradation estimate | Gradient-boosted regression on per-residue structural features | **ML Prediction** |

Each is labelled distinctly in the interface and in every export, so a number
is always traceable to the method that produced it.

## Scope

COSMORA models the **mechanical consequence of losing a residue**, not the
chemistry that causes the loss. Damage is applied as a structural lesion —
side-chain truncation — at residues selected using literature radiosensitivity.
No dose, particle track or energy deposition enters the simulation.

This is a deliberate boundary, and it is what makes the measurement tractable:
mechanical response to a defined structural change is something molecular
dynamics can compute honestly, whereas radiation chemistry is not.

## Quick start

Requirements: **Python 3.11** (not 3.12+), **Node 18+**, and about 1.5 GB of
disk for dependencies. A GPU is optional — it makes a demo run ~5× faster.

### One-shot setup

```bash
make setup && make validate
```

Then, in two terminals:

```bash
make backend
```

```bash
make frontend
```

### Windows without `make`

`make` is not installed by default on Windows. Run the same four steps
directly — this path is verified in
[docs/validation](docs/validation/2026-08-30-clean-checkout.md):

```bash
uv venv .venv311 --python 3.11 && uv pip install --python .venv311 -r backend/requirements-dev.txt
```

```bash
.venv311/Scripts/python.exe scripts/setup_local.py && cd frontend && npm install && cd ..
```

```bash
.venv311/Scripts/python.exe scripts/validate_environment.py && .venv311/Scripts/python.exe scripts/validate_model.py
```

Then the two servers, in separate terminals:

```bash
cd backend && ../.venv311/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm run dev
```

If you do not have [uv](https://docs.astral.sh/uv/), substitute
`python3.11 -m venv .venv311` and `.venv311/Scripts/python.exe -m pip install`.

- Dashboard: <http://localhost:5173>
- API: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>

### Manual setup

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# Backend — Python 3.11 is required
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
python scripts\setup_local.py
python scripts\validate_environment.py
python scripts\validate_model.py

# Run the API (leave this running)
cd backend
uvicorn app.main:app --reload --port 8000
```

```powershell
# Frontend — in a second terminal
cd frontend
npm install
npm run dev
```

If `py -3.11` is not available, install the interpreter with
[uv](https://docs.astral.sh/uv/): `uv python install 3.11`, then
`uv venv backend\.venv --python 3.11`.
</details>

<details>
<summary><b>Linux / macOS</b></summary>

```bash
# Backend
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt
python scripts/setup_local.py
python scripts/validate_environment.py
python scripts/validate_model.py

cd backend && uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend — in a second terminal
cd frontend && npm install && npm run dev
```
</details>

---

## Why Python 3.11 specifically

The dependency set is pinned, not merely bounded, and the pins are load-bearing:

- The ML bundle was serialised by **joblib under scikit-learn 1.7.1** with a
  **NumPy 2.x** memory layout — the pickle references `numpy._core.multiarray`,
  which does not exist on NumPy 1.x. Unpickling a scikit-learn estimator under a
  different minor version voids the guarantee that training transforms are
  reproduced, so scikit-learn is pinned exactly.
- **MDTraj ≤ 1.10.x caps NumPy below 2.0**, which directly conflicts with the
  bundle. 1.11.x is the first line declaring `numpy ~=2.0`, so that is the floor.
- OpenMM publishes `cp311` wheels for Windows, Linux and macOS from 8.5
  onwards, which is what lets this project install with plain `pip`.

`scripts/validate_environment.py` checks all of this and names the exact problem
if something is off.

---

## The demonstration path

1. Open <http://localhost:5173> and click **Launch Simulation Lab**.
2. **1UBQ** (ubiquitin) is preselected — the Rapid Demo default and a *held-out*
   protein for the ML model, so its estimate is an honest generalisation result.
3. Keep the **Deep-space GCR reference** scenario.
4. Click **Estimate degradation**. You get ~49.5 %, risk *moderate*, confidence
   `null`, and a warning that one candidate residue (GLY) is outside the model's
   14-amino-acid vocabulary and was excluded from the mean.
5. Click **Run rapid simulation**. The monitor shows real integrator progress
   through eight stages — 6,000 steps, live temperature and potential energy.
   It takes roughly 20 s on a GPU platform or 80–120 s on CPU.
6. Click **Open results**. RMSD, per-residue RMSF, radius of gyration,
   potential energy and temperature, all computed from the real trajectory,
   plus a side-by-side and overlay structure comparison.
7. The **ML prediction vs simulation** panel shows both figures, their
   difference, and why that difference does not mean either is wrong.
8. Download the **JSON** and **CSV** reports, or the raw trajectory.

`docs/demo-script.md` has a timed walkthrough with the exact talking points.

If a live run cannot complete on your machine, the results interface stays
demonstrable via the bundled fallback at
<http://localhost:5173/results/precomputed/1UBQ>, labelled **Precomputed OpenMM
Result** everywhere it appears.

---

## Approved proteins

| PDB | Protein | UniProt | Proposed mechanical role | ML split |
| --- | --- | --- | --- | --- |
| 1TIT | Titin I27 domain | Q8WZ42 | Molecular spring / force-bearing | train |
| 1TEN | Fibronectin type III (tenascin) | P24821 | Structural / load-transmitting | **test** |
| 2SPC | Spectrin repeat | P13395 | Elastic linker | train |
| 1UBQ | Ubiquitin | P0CG48 | Compact switch / sensor body | **validation** |
| 1PGA | Protein G B1 domain | P06654 | Minimal stable module | train |

The **ML split** column matters: a protein in `train` will look optimistically
accurate. 1UBQ and 1TEN are the only honest held-out cases, and the UI badges
them as *held-out* so this is visible at the point of selection.

Custom PDB upload is supported, validated (type, size, parseability, atom and
residue counts, chain availability) and clearly flagged: uploaded structures are
featurised by COSMORA's own extractor rather than read from the training
reference table.

---

## Repository layout

```
COSMORA/
├── backend/            FastAPI service
│   ├── app/
│   │   ├── ml/         bundle loading, featurisation, inference guards
│   │   ├── simulation/ presets, validation, OpenMM engine, job manager
│   │   ├── analysis/   RMSD, RMSF, Rg, energy, degradation proxy
│   │   ├── services/   orchestration for proteins, predictions, jobs, reports
│   │   └── api/        versioned routes
│   └── tests/          312 tests, including real OpenMM runs
├── frontend/           React + TypeScript + Vite dashboard
├── data/
│   ├── proteins/       the five approved PDB structures + metadata
│   ├── ml/             training data, splits and eval reports (provenance)
│   ├── scenarios/      radiation scenario presets
│   └── precomputed/    labelled fallback results
├── models/             the ML bundle, its metadata and generated feature schema
├── runtime/            job directories, uploads, reports, logs (gitignored)
├── scripts/            setup and validation utilities
├── docs/               architecture, API contract, model card, methodology
└── legacy/             the project's original scripts, preserved verbatim
```

`legacy/` holds the four scripts this project started from. The 8 Å Cα
contact-graph logic in `legacy/build_contact_graph.py` is preserved in the
backend (vectorised, and verified to reproduce the reference table exactly);
`legacy/main.py` is superseded because it returned hardcoded heuristic values
rather than model output.

---

## Commands

```bash
make help              # list everything
make setup             # install backend + frontend, fetch data and viewer
make validate          # environment and model checks
make test              # backend tests + frontend typecheck and lint
make test-backend-all  # include the real OpenMM simulation tests
make demo              # run one simulation without the HTTP layer
make precomputed       # regenerate the labelled fallback result
make build             # production frontend build
make clean             # delete generated runtime artifacts
```

### Validation status

All of the following pass on a clean checkout:

- `scripts/validate_model.py` — **25/25 checks**. The decisive one: inference in
  your environment reproduces the shipped
  `data/ml/reports/{validation,test}_predictions.csv` to `max|diff| ≈ 1.9e-06`
  (CSV write precision) and the published MAE to six decimal places.
- `backend`: **312 tests** — 303 fast plus 9 marked `slow` that execute real
  OpenMM runs, including paired steered-MD pulls.
- `frontend`: `tsc --noEmit` clean, `eslint --max-warnings 0` clean, production
  build succeeds.
- End-to-end: verified in-browser at 1366×768 with zero console errors or
  warnings.

---

## API

Base URL `http://localhost:8000/api/v1`. Full reference in
[`docs/api-contract.md`](docs/api-contract.md); interactive docs at `/docs`.

```
GET    /health                              liveness
GET    /system/readiness                    per-subsystem readiness
GET    /proteins                            approved protein registry
GET    /proteins/{pdb_id}                   detail + ranked candidate residues
GET    /proteins/{pdb_id}/structure         raw PDB coordinates
POST   /proteins/upload                     validate and stage a custom PDB
GET    /model                               ML bundle status and limitations
GET    /scenarios                           radiation scenario presets
POST   /predictions                         ML degradation estimate
GET    /simulation/presets                  available simulation presets
POST   /simulations                         submit a job (202)
GET    /simulations                         history, read from disk
GET    /simulations/{job_id}                live status and progress
POST   /simulations/{job_id}/cancel         request cancellation
GET    /simulations/{job_id}/results        analysis results
GET    /simulations/{job_id}/structure      final / prepared / topology / input
GET    /simulations/{job_id}/trajectory     DCD trajectory
GET    /reports/{job_id}.json               full experiment report
GET    /reports/{job_id}.csv                flat report for spreadsheets
```

Every error uses one envelope:

```json
{
  "error": {
    "code": "INVALID_SIMULATION_INPUT",
    "message": "The selected PDB file could not be prepared.",
    "details": [],
    "request_id": "uuid"
  }
}
```

---

## Limitations and scope

Stated plainly so every number above can be read correctly.

### Scientific

- **Radiation is not simulated.** OpenMM integrates Newtonian dynamics on a
  classical force field: no particle transport, no energy deposition, no
  radiolysis, no bond scission. Dose and exposure are recorded as provenance
  and are visibly marked as such in the interface.
- **The pull is non-equilibrium.** At 0.03 nm/ps it is roughly a million times
  faster than an AFM experiment, so absolute forces are far above experimental
  values. Comparisons are valid *within* this protocol, not against literature
  force values.
- **Runs are picoseconds.** Real degradation acts over seconds to years.
- **The damage proxy is a structural lesion, not measured damage.** Severity
  counts removed side chains; it corresponds to no dose, LET or fluence value,
  and the contract enforces `severity_is_a_dose: false`.
- **1TEN is a known false negative.** Tenascin fibronectin-III is
  experimentally load-bearing and this protocol did not register it (r² 0.12) —
  the pull is too short for domains whose resistance builds late.
- **1PGA's −402 pN/nm is a fit artifact,** not a measurement. When the pull
  does not dominate thermal fluctuation the fit degenerates.

### The ML model

The shipped default is a **mock bootstrap model**
(`MOCK_PUBLIC_DATA_BOOTSTRAP`) whose labels are a synthetic proxy, present so
the interface and API can be exercised end to end. It is labelled as such in
the dashboard, the API and every export.

A **real model trained on the 520 paired simulations** ships alongside it
(`models/COSMORA_real_model_bundle.pkl`). It records
`scientifically_validated: false` against four criteria fixed before training:

| Criterion | Required | Achieved |
| --- | --- | --- |
| Training labels | ≥ 30 | 18 |
| Distinct proteins | ≥ 8 | 4 |
| Worst label uncertainty | ≤ 10.0 pp | 13.6 pp |
| Beat the mean baseline | yes | R² −0.004 vs −0.203 |

The constraint is sample size, not modelling. Label noise of 26.7 pp caps
achievable R² at 0.561, and resolving the damage effect needs ~29 seeds per
condition against the 5 that were run. The gate exists so no result can be
presented as validated while these hold; see
[docs/RESULTS.md](docs/RESULTS.md) §3–4 for the power analysis.

### Engineering

- **One simulation at a time.** Raising `COSMORA_MAX_CONCURRENT_JOBS` needs a
  real queue: OpenMM runs are device-bound, and two concurrent jobs on one
  device are slower than two in sequence.
- **No database.** Job state lives in `runtime/jobs/<job_id>/` with atomic
  `status.json` writes, rebuilt from disk after a restart. Service interfaces
  are shaped so SQLite or Postgres can be added later.
- **No authentication.** Local single-user MVP.
- **GPU runs are not bit-reproducible.** The platform is auto-selected for
  speed and recorded per job; choosing `CPU` gives an exactly repeatable
  trajectory for a fixed seed.
- **`residue_sasa_norm` for uploads is approximate** — r = 0.93–0.99 against
  the training table, not bit-identical, so upload estimates are less faithful
  than those for the five approved proteins. See
  [docs/model-card.md](docs/model-card.md).

---

## Documentation

**Results and method**

| Document | Contents |
| --- | --- |
| [RESULTS.md](docs/RESULTS.md) | The 520-experiment run: measurements, two null results, power analysis, limitations |
| [simulation-methodology.md](docs/simulation-methodology.md) | Force field, presets, pulling protocol, analysis, the proxy formula |
| [experiment-contract.md](docs/experiment-contract.md) | The paired pristine-vs-damaged data contract, v1.0 |
| [model-card.md](docs/model-card.md) | Model provenance, features, metrics, failure modes |
| [scientific-scope.md](docs/scientific-scope.md) | What is and is not claimed, and why |
| [scientific-claims-checklist.md](docs/scientific-claims-checklist.md) | Every claim against its supporting artifact and its limitation |

**Building and running**

| Document | Contents |
| --- | --- |
| [architecture.md](docs/architecture.md) | Components, data flow, job lifecycle, extension points |
| [api-contract.md](docs/api-contract.md) | Every endpoint, schema and error code |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Local, tunnel, Codespaces and permanent deployment |
| [dashboard-guide.md](docs/dashboard-guide.md) | Page-by-page walkthrough |
| [demo-script.md](docs/demo-script.md) | Timed presentation script |
| [validation/](docs/validation/) | Clean-checkout validation records |

---

## License

Code is released under the MIT License — see [LICENSE](LICENSE).

Protein coordinate data is distributed by [RCSB PDB](https://www.rcsb.org/)
under CC0 1.0 Universal.

The **mock** bundle (`COSMORA_mock_model_bundle.pkl`) is a demonstration
artifact for interface and API testing, not for scientific inference. The
**real** bundle (`COSMORA_real_model_bundle.pkl`) is trained on the paired
simulations in `data/ml/` and carries its own validation status and criteria in
`models/real_model_metadata.json`. Simulation outputs are reproducible from the
protocol and seeds recorded in `models/reproducibility_manifest.json`.
