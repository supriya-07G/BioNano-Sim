# Architecture

## 1. Overview

```
┌─────────────────────────┐
│  React dashboard        │  TypeScript · Vite · TanStack Query · 3Dmol.js
│  localhost:5173         │
└───────────┬─────────────┘
            │  /api/v1  (same-origin in dev via the Vite proxy)
┌───────────▼─────────────┐
│  FastAPI backend        │  localhost:8000
├─────────────────────────┤
│  ML INFERENCE PATH      │
│   loader → featurise →  │  load once, verify SHA-256 + schema,
│   guards → aggregate    │  detect unknown categories, warn
├─────────────────────────┤
│  PHYSICS PATH           │
│   job manager → OpenMM  │  worker thread, atomic status.json,
│   → analysis            │  step-driven progress
├─────────────────────────┤
│  Compare + report       │  the only place the two paths meet
└───────────┬─────────────┘
            │
┌───────────▼─────────────┐
│  Local filesystem       │  no database
│  models/ data/ runtime/ │
└─────────────────────────┘
```

The two result paths stay separate all the way to the comparison step, and each
carries its own provenance label. That separation is the core design constraint:
nothing in the physics path can be relabelled as a prediction, and nothing in
the ML path can be presented as a trajectory.

## 2. Backend layout

```
backend/app/
├── main.py              app factory, lifespan, exception handlers, CORS
├── config.py            pydantic-settings; every path derived from the repo root
├── core/
│   ├── exceptions.py    error taxonomy + the single JSON error envelope
│   ├── logging.py       console + rotating file
│   └── security.py      filename sanitising, id validation, path confinement
├── ml/
│   ├── feature_schema.py  typed view over models/feature_schema.json
│   ├── loader.py          load-once singleton, self-verifying, never fatal
│   ├── preprocessing.py   featurisation (reference table vs recomputed)
│   └── inference.py       validation, unknown-category guard, aggregation
├── simulation/
│   ├── presets.py       three presets with declared limits and labels
│   ├── validators.py    pre-flight checks; OpenMM/MDTraj probes
│   ├── preparation.py   chain extraction, system build, platform selection
│   ├── engine.py        the OpenMM run + DCD reader + analysis
│   └── job_manager.py   worker pool, atomic state, lifecycle
├── analysis/
│   ├── rmsd.py rmsf.py radius_gyration.py energy.py
│   └── degradation.py   the drift proxy, with its formula and caveats
├── services/            orchestration; the only layer routes talk to
├── schemas/             pydantic request/response models
├── utils/               atomic writes, JSON-safe serialisation
└── api/routes/          health, proteins, predictions, simulations, reports
```

Routes contain no logic beyond calling a service and returning its result, which
is what keeps `scripts/run_demo_simulation.py` able to exercise the entire
pipeline without an HTTP layer.

## 3. Startup

`lifespan` in `main.py`:

1. Configure logging, create runtime directories.
2. Load the ML bundle **once**. Failures are recorded, never raised.
3. Probe OpenMM and log the available platforms.

Neither step can prevent boot. A missing model or a broken OpenMM install leaves
the API up with an accurate `/system/readiness` report, which is what lets the
frontend show precise per-subsystem indicators instead of a blank page.

### Model self-verification

`ml/loader.py` does more than unpickle:

- Computes the bundle's SHA-256 and compares it to `release_manifest.json`.
- Confirms the generated `feature_schema.json` still matches the live pipeline's
  own columns and encoder vocabularies.
- Records, rather than swallows, a scikit-learn `InconsistentVersionWarning`.

`sha256_verified` and `schema_verified` are surfaced through `/model` and
`/system/readiness`, and an unverified bundle adds a warning to every prediction
response. A silent drift between the schema and the model would mean the API
validates input against the wrong contract.

## 4. Job lifecycle

```
POST /simulations
  ├── require OpenMM                      → 503 if unavailable
  ├── resolve structure                   → 404 / 400 on a bad id
  ├── validate request                    → 400 with a specific code
  ├── check the concurrency slot          → 409 if one is running
  ├── create runtime/jobs/<job_id>/
  ├── snapshot input.pdb                  (so results survive upload deletion)
  ├── write request.json + status.json
  └── submit to the ThreadPoolExecutor    → 202 with the initial record

worker thread
  ├── input_validation
  ├── protein_preparation      → prepared.pdb
  ├── system_construction      → topology.pdb
  ├── energy_minimization
  ├── equilibration            ┐ 250-step chunks,
  ├── production               ┘ publishing real step counts
  ├── trajectory_analysis      → analysis/*.csv
  └── report_generation        → metrics.json, status = completed
```

Cancellation sets a `threading.Event`; the worker observes it at the next chunk
boundary, normally within a second, and terminates through the failure path so
the job records `cancelled` — never `completed`.

### Why state lives on disk

`status.json` is the single source of truth, written atomically via temp file +
`os.replace`. Consequences:

- History survives a backend restart, because `GET /simulations` enumerates job
  directories rather than reading memory.
- A UI poll can never observe a half-written file.
- A job directory is self-describing, so results remain readable after a
  restart, and a directory with an unreadable `status.json` is *surfaced* as a
  failed job rather than hidden.

In-memory state holds only the cancel flags for live jobs.

### Concurrency

Capped at one. This is a real constraint, not a placeholder: OpenMM runs are
CPU- or GPU-bound, and two concurrent jobs on one device finish later than two
run in sequence. Raising `COSMORA_MAX_CONCURRENT_JOBS` enlarges the thread pool
but does not add a queue — a second submission is rejected with `409
CONCURRENCY_LIMIT`. Supporting real concurrency means adding a queue with
admission control, which is deliberately out of MVP scope.

## 5. Frontend layout

```
frontend/src/
├── main.tsx App.tsx routes/router.tsx
├── pages/          one per route
├── components/
│   ├── layout/     AppShell, Sidebar, Topbar, Starfield, ArchitectureDiagram
│   ├── proteins/   viewer (3Dmol), selector, summary, residue inspector
│   ├── experiment/ scenario form, radiation and mechanical controls
│   ├── prediction/ prediction card, risk gauge, confidence, feature summary
│   ├── simulation/ progress, stage timeline, console, controls
│   ├── results/    charts, metrics grid, comparison, exports
│   ├── common/     status badges, notices, error/empty/loading states
│   └── ui/         tooltip, progress, cn
├── hooks/          usePrediction, useSimulation, useJobPolling, useStructure
├── services/       api (error envelope unwrapping) + one module per domain
├── stores/         experimentStore (zustand, persisted draft only)
├── types/          mirrors of the API contract
└── utils/          formatters, validators, error descriptions, result labels
```

### Layout strategy

`AppShell` is `h-screen overflow-hidden` with one scrolling `<main>`. The
experiment workspace is a three-column grid filling that height, with each
column scrolling independently. That is what keeps the 3D viewport free of page
scrolling at 1366×768.

`html`/`body`/`#root` use `min-height: 100%`, deliberately **not** `height`. A
fixed height there clamps the document and silently clips long pages such as the
landing page — a bug this project hit and fixed.

### Polling

`useJobPolling` returns `false` from `refetchInterval` once the job is terminal,
so polling stops on its own. There is no `setInterval` to leak: unmounting
removes the last observer and the query goes idle. Interval is configurable via
`VITE_JOB_POLL_INTERVAL_MS`, clamped to [500, 10000] at the use site.

### Query caching

| Data | Stale time | Why |
| --- | --- | --- |
| Protein registry, scenarios, presets | `Infinity` | Static, shipped with the repo |
| Structure coordinates | `Infinity` | Immutable for a given id |
| Completed job results | `Infinity` | Cannot change |
| Live job status | `0` | Always refetch |
| Model status | 5 min | Only changes on a backend restart |
| Readiness | 15 s | Enough to notice a restart, not enough to add noise |

4xx responses are never retried: an unsupported scenario fails identically on a
second attempt, and retrying only delays the error the user needs to see.

### Provenance labels in one place

`utils/resultLabels.ts` holds the exact label strings the scientific-integrity
rules require, and `components/common/StatusBadge.tsx` is the only component that
renders them. An ML estimate, a live run and a precomputed result therefore
cannot drift into sharing a badge.

## 6. Error handling

One envelope for every failure:

```json
{"error": {"code": "...", "message": "...", "details": [], "request_id": "uuid"}}
```

Four handlers in `main.py` cover `COSMORAError`, Starlette HTTP exceptions,
pydantic validation errors (flattened into `details` with field names) and a
last-resort handler that logs the traceback and returns a generic message.

Every request gets an `X-Request-ID` (echoed in the response header and the
envelope), so a user-visible error maps to a log line.

On the client, `services/api.ts` unwraps the envelope into a typed `ApiError`
with `code`, `status`, `details` and `requestId`, plus `isUnavailable` and
`isConflict` helpers. `utils/errors.ts` maps codes to concrete remediation —
`SIMULATION_ENGINE_UNAVAILABLE` becomes "install it with `pip install
openmm==8.6.0`" rather than a bare message.

## 7. Security

This is a local single-user MVP with no authentication, but everything reaching
the filesystem is still guarded:

| Input | Guard |
| --- | --- |
| PDB id | Strict `^[0-9A-Za-z]{4}$` allow-list, then registry membership |
| Job / upload id | Strict `^[0-9a-f]{32}$` (uuid4 hex) |
| Upload filename | Unicode normalise, strip directories including Windows `\`, collapse to `[A-Za-z0-9._-]` |
| Every resolved path | `resolve_within()` proves the result stays inside its base directory |
| Artifact names | Fixed allow-list, not user-supplied |
| Upload body | Read in 1 MiB chunks with a hard cap, so an oversized upload is rejected without being fully buffered |

CORS is restricted to the local frontend dev origins — deliberately not `*`,
since the API accepts uploads and serves downloads.

## 8. Extension points

**Adding a database.** Job state is accessed only through `JobManager`. Its
public surface (`submit`, `read_status`, `detail`, `list_jobs`, `metrics`,
`cancel`, `delete`) is what a SQL-backed implementation would need to satisfy;
nothing above it reads `status.json` directly.

**Replacing the model.** Drop in the new bundle, run
`scripts/generate_feature_schema.py`, then `scripts/validate_model.py`. The
loader verifies the schema against the live pipeline and refuses to trust a
stale one. If the new bundle has different feature names, the schema regenerates
to match and the validation guards follow automatically.

**Real radiation modelling.** The clean seam is
`app/simulation/preparation.py` (system construction) plus a new stage in
`engine.py`. The stage list in `schemas/simulation.py` is ordered and weighted,
so an inserted stage appears in the timeline without frontend changes.

**Real concurrency.** Replace the `ThreadPoolExecutor` in `JobManager` with a
queue plus admission control. The cancel mechanism (a per-job
`threading.Event`) already works for queued-but-not-started jobs.

## 9. Testing

| Layer | Coverage |
| --- | --- |
| `test_health.py` | Liveness, per-subsystem readiness, error envelope, request ids |
| `test_proteins.py` | Registry, exact candidate-score formula, structure serving, traversal guards, upload validation |
| `test_prediction.py` | Bundle load and self-verification, determinism, dose-invariance, OOV detection, envelope warnings, scenario refusal |
| `test_simulation_validation.py` | Presets and their declared limits, missing-OpenMM degradation, request validation, job lifecycle, precomputed labelling, real OpenMM runs (`-m slow`) |

312 tests. The suite passes with OpenMM absent — the slow tests skip and the
degradation tests assert that the API reports 503 with remediation rather than
crashing. Two notable assertions:

- `test_dose_does_not_change_the_ml_estimate` — proves the documented
  dose-invariance rather than just describing it.
- `test_failed_job_is_never_marked_completed` — feeds a structure OpenMM cannot
  build and asserts the terminal status is not `completed`.
