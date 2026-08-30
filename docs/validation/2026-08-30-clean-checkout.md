# Clean-checkout validation record — 2026-08-30

Closes the acceptance criterion of issue #8: prove the full demo path runs from
a fresh clone, without relying on an existing local environment.

**Commit validated:** `7d605ab`
**Method:** `git clone` into an empty directory outside the working tree, then
every documented command run against that clone only.

## Environment

| Component | Version |
|---|---|
| OS | Windows 10/11 AMD64 |
| Python | 3.11.14 |
| Node / npm | v24.12.0 / 11.6.2 |
| OpenMM | 8.6 |
| OpenMM platforms available | Reference, CPU, OpenCL |
| MDTraj | 1.11.1.post2 |
| scikit-learn | 1.7.1 |
| XGBoost | 2.1.3 |
| NumPy | 2.1.3 |
| FastAPI | 0.115.6 |

The simulation ran on the **CPU** platform. No GPU was used.

## Results

| Step | Command | Outcome |
|---|---|---|
| Environment check | `scripts/validate_environment.py` | **pass** — 5 structures, 4 runtime dirs, node/npm found. "No blocking problems found." |
| Model check | `scripts/validate_model.py` | **pass** — 25/25 checks. Bundle loadable, faithful to published metrics, consistent with `feature_schema.json`. |
| Backend fast tests | `pytest -m "not slow"` | **138 passed**, 9 deselected, 2.54 s |
| Backend slow tests | `pytest -m slow` | **9 passed**, 138 deselected, 266.65 s (4 m 27 s) — real OpenMM runs |
| Frontend typecheck | `npm run typecheck` | **pass** |
| Frontend lint | `npm run lint` | **pass**, zero warnings |

**Total: 147/147 backend tests pass on a clean checkout.**

## Live demo run

One `rapid_demo` simulation submitted over HTTP, no test harness involved.

- **Request:** `POST /api/v1/simulations` — 1UBQ chain A,
  `scenario_id=GCR_DEEP_SPACE_REFERENCE`, `preset_id=rapid_demo`, `random_seed=42`
- **Job id:** `d2b5ebfbac934159b6d577a912221b0d`
- **Wall clock: 18 s** (submit to `completed`)
- **Progress monotonic and in range:** observed 0.644 → 1.0, never below 0 or above 1

Readiness before the run reported all seven components ready: `ml_model`,
`simulation_engine`, `trajectory_analysis`, `protein_registry`, `scenarios`,
`runtime_storage`, `precomputed_fallback`.

### Downloads

Every artifact endpoint returned HTTP 200 with non-empty content:

| Endpoint | Bytes |
|---|---|
| `GET /simulations/{id}/results` | 28,499 |
| `GET /simulations/{id}/structure` | 101,023 |
| `GET /simulations/{id}/trajectory` | 888,036 |
| `GET /reports/{id}.json` | 31,241 |
| `GET /reports/{id}.csv` | 26,749 |
| `GET /simulations/{id}/log` | 2,154 |

### Physical sanity of the result

| Metric | Value |
|---|---|
| RMSD (mean / final / max) | 0.113 / 0.134 / 0.142 nm |
| Radius of gyration (initial → final) | 1.147 → 1.152 nm (+0.42%) |
| Potential energy (initial → final) | −12,958.7 → −11,680.7 kJ/mol |

A sub-2 Å RMSD, a radius of gyration essentially unchanged, and potential
energy relaxing upward from the minimised state are all what a short stable
implicit-solvent run should produce. The protein did not unfold or explode.

## Defect found and fixed by this exercise

The clean checkout **failed on the first attempt**, which is the point of the
issue. `data/precomputed/1UBQ/final.pdb` was matched by the broad `final.pdb`
ignore rule intended for run output, so it was never committed. A fresh clone
therefore had no precomputed structure, `GET /precomputed/1UBQ/structure`
returned 404 for the default `?which=final`, and
`test_precomputed_structure_is_downloadable` failed.

It passed on every developer machine that had once run a simulation, and CI
never caught it because the lint step failed first and the tests never ran.

Fixed in commit `f6467b2` by negating the ignore rule for
`data/precomputed/**` and committing the fixture. The `precomputed_fallback`
component now reports ready, as shown above.

## Known warnings (non-blocking)

- ~~`DeprecationWarning: invalid escape sequence` in
  `backend/app/core/security.py:23`~~ — found during this run and fixed in the
  same commit; the docstring is now a raw string. The suite is warning-free.
- XGBoost emits a cross-version serialisation notice when unpickling the mock
  bundle. `validate_model.py` verifies the numerical output regardless, and all
  25 checks pass.

## Reproducing this record

```bash
git clone <repo> bionano-check && cd bionano-check
make setup && make validate && make test && make test-backend-all
make backend    # then POST one rapid_demo job as above
```
