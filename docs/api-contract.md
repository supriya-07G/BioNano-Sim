# API contract

Base URL: `http://localhost:8000/api/v1`
Interactive reference: `http://localhost:8000/docs`

Every request receives an `X-Request-ID` response header (echoing the request's
own if supplied), which also appears in the error envelope and the server log.

## Error envelope

Every failure — validation, not-found, conflict, unavailable, unhandled — uses
one shape:

```json
{
  "error": {
    "code": "INVALID_SIMULATION_INPUT",
    "message": "The selected PDB file could not be prepared.",
    "details": [],
    "request_id": "3f1c…"
  }
}
```

`details` is a list. For pydantic failures it contains
`{"field": "dose", "message": "...", "type": "..."}`; for domain failures it
contains strings or objects naming what went wrong.

### Codes

| Code | HTTP | Meaning |
| --- | --- | --- |
| `VALIDATION_FAILED` | 422 | Request body failed schema validation |
| `NOT_FOUND` | 404 | Unknown protein, scenario, job or artifact |
| `INVALID_PDB_ID` | 400 | Not a 4-character PDB identifier |
| `INVALID_JOB_ID` | 400 | Not a 32-hex-character job id |
| `UNSAFE_PATH` | 400 | A resolved path escaped its permitted directory |
| `MODEL_UNAVAILABLE` | 503 | ML bundle could not be loaded |
| `PREDICTION_FAILED` | 400 | Feature frame invalid, or the pipeline raised |
| `SCENARIO_NOT_ML_SUPPORTED` | 400 | Scenario outside the trained vocabulary |
| `INVALID_PROTEIN_FILE` | 400 | Upload rejected (see sub-codes below) |
| `INVALID_SIMULATION_INPUT` | 400 | Simulation request invalid |
| `SIMULATION_ENGINE_UNAVAILABLE` | 503 | OpenMM missing or unusable |
| `JOB_CONFLICT` / `CONCURRENCY_LIMIT` | 409 | A job is already running |
| `INTERNAL_ERROR` | 500 | Unhandled; traceback is in the server log |

Upload sub-codes: `INVALID_FILE_TYPE`, `EMPTY_FILE`, `FILE_TOO_LARGE`,
`NOT_TEXT`, `NO_PDB_RECORDS`, `NO_ATOM_RECORDS`, `TOO_MANY_ATOMS`,
`TOO_MANY_RESIDUES`, `NO_PROTEIN_CHAIN`, `UNPARSEABLE`.

Simulation sub-codes: `UNKNOWN_PRESET`, `PRESET_EXCEEDS_LIMIT`,
`STRUCTURE_MISSING`, `STRUCTURE_UNPARSEABLE`, `CHAIN_NOT_FOUND`,
`CHAIN_TOO_SHORT`, `CHAIN_TOO_LARGE`, `TEMPERATURE_OUT_OF_RANGE`,
`NO_SIMULATABLE_RESIDUES`, `HYDROGEN_ADDITION_FAILED`,
`SYSTEM_CONSTRUCTION_FAILED`, `PLATFORM_UNAVAILABLE`.

---

## System

### `GET /health`

Liveness. Always cheap.

```json
{"status": "ok", "app": "COSMORA", "version": "0.1.0", "time_utc": "…"}
```

### `GET /system/readiness`

Per-subsystem readiness, so a client can show precise indicators instead of
failing wholesale.

```json
{
  "ready": true,
  "status": "degraded",
  "time_utc": "…",
  "components": [
    {
      "name": "ml_model",
      "ready": true,
      "status": "ready",
      "version": "0.2.0-mock",
      "detail": "COSMORA Public Bootstrap Model 0.2.0-mock (MOCK_PUBLIC_DATA_BOOTSTRAP); integrity verified.",
      "remediation": null
    }
  ],
  "counts": {
    "approved_proteins": 5, "scenarios": 5, "ml_supported_scenarios": 3,
    "total_jobs": 4, "completed_jobs": 4, "failed_jobs": 0,
    "active_jobs": 0, "presets": 3
  }
}
```

Components: `ml_model`, `simulation_engine`, `trajectory_analysis`,
`protein_registry`, `scenarios`, `runtime_storage`, `precomputed_fallback`.

`ready` reflects the five *core* components; the optional fallback and the
degradable trajectory analyser are excluded, so a missing precomputed result
reports `degraded` rather than `not_ready`. **Any component that is not ready
carries a non-null `remediation`** — asserted by a test.

---

## Proteins

### `GET /proteins`

The five approved proteins, Rapid Demo default first then shortest.

```json
[{
  "pdb_id": "1UBQ", "name": "Ubiquitin", "uniprot": "P0CG48",
  "proposed_role": "Compact switch / sensor body", "chain_id": "A",
  "protein_length": 76, "molecular_weight": 8564.7357,
  "experiment_method": "X-Ray Diffraction", "resolution_angstrom": 1.8,
  "ml_dataset_split": "validation", "is_rapid_demo_default": true
}]
```

`ml_dataset_split` is `train`, `validation` or `test`. A protein in `train` will
look optimistically accurate; treat only `validation` (1UBQ) and `test` (1TEN)
as honest generalisation cases.

### `GET /proteins/{pdb_id}?top_n=10`

Adds `why_selected`, composition fractions, deposition metadata, per-chain
summaries, `feature_source` and the ranked candidate residues.

`feature_source` is `reference_table` (exact — read from the table the model was
trained on) or `recomputed` (approximate).

Each candidate carries `residue_sasa_norm`, `residue_contact_count`,
`qualitative_susceptibility`, `inverse_packing`, `susceptibility_score`,
`candidate_score`, `proxy_rank` and `ranking_source`. The score satisfies
`0.45·sasa + 0.30·inverse_packing + 0.25·susceptibility` exactly — there is a
test asserting it to 1e-12.

### `GET /proteins/{pdb_id}/structure`

Raw PDB coordinates, `chemical/x-pdb`, cacheable for an hour. Only approved ids
resolve.

### `POST /proteins/upload`

`multipart/form-data`, field `file`. Validates extension, size (8 MiB cap, read
in chunks so an oversized upload is not fully buffered), decodability, PDB
record presence, ATOM records, atom count (100,000), parseability, residue count
(2,000) and the presence of a protein chain with Cα atoms. Nothing is written to
`runtime/uploads/` until every check passes.

```json
{
  "upload_id": "…32 hex…", "filename": "fragment.pdb", "size_bytes": 1234,
  "n_models": 1, "n_atoms": 25, "n_residues": 5, "default_chain": "A",
  "chains": [{"chain_id": "A", "n_residues": 5, "n_atoms": 25, "is_default": true}],
  "warnings": ["Features for uploaded structures are recomputed …"],
  "feature_source": "recomputed"
}
```

The filename is sanitised: `../../../evil.pdb` is stored as `evil.pdb`.

### `GET /proteins/upload/{upload_id}/structure`

Coordinates of an uploaded structure.

---

## Model and scenarios

### `GET /model`

Full model status: identity, `scientific_status`, `label_source`,
`scientifically_validated`, bundle SHA-256 with `sha256_verified` and
`schema_verified`, the complete feature order and categorical vocabulary,
`supports_uncertainty` (always `false`), held-out metrics, split membership, a
`limitations` array, and `top_feature_importances`.

### `GET /scenarios`

```json
{
  "scenarios": [{
    "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
    "label": "Deep-space GCR reference",
    "radiation_class": "GCR", "environment": "free_space",
    "ml_supported": true,
    "defaults": {"dose": 0.5, "dose_unit": "Gy", "exposure_duration_days": 180.0,
                 "temperature_kelvin": 300.0, "mechanical_force_pn": 0.0}
  }],
  "dose_units": [{"unit": "Gy", "label": "gray (Gy)", "to_gray": 1.0}],
  "provenance": {
    "status": "CONFIGURABLE_DEMONSTRATION_PRESETS",
    "statement": "… NOT authoritative NASA, ESA or ICRP reference values …",
    "ml_coupling": "The ML bundle consumes only the categorical fields …"
  }
}
```

Three scenarios have `ml_supported: true`. `BASELINE_NO_RADIATION` and
`MECHANICAL_STRESS_TEST` have `ml_supported: false` plus an
`ml_unsupported_reason`; they simulate but produce no ML estimate.

---

## Predictions

### `POST /predictions`

Exactly one of `pdb_id` or `upload_id` is required.

```json
{
  "pdb_id": "1UBQ", "chain_id": "A",
  "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
  "dose": 0.5, "dose_unit": "Gy",
  "exposure_duration_days": 180.0,
  "temperature_kelvin": 300.0, "mechanical_force_pn": 0.0,
  "random_seed": 42, "top_n_residues": 10
}
```

> `dose`, `dose_unit`, `exposure_duration_days`, `temperature_kelvin`,
> `mechanical_force_pn` and `random_seed` are **not model features**. They are
> recorded for provenance and echoed under
> `input_summary.not_used_by_model`. Changing them does not change the estimate.

Response:

```json
{
  "prediction_id": "uuid",
  "model_version": "0.2.0-mock",
  "model_status": "MOCK_PUBLIC_DATA_BOOTSTRAP",
  "degradation_percent": 49.5216,
  "risk_level": "moderate",
  "confidence": null,
  "warnings": ["MVP estimate; not experimentally validated. …"],
  "input_summary": {
    "structure": {...}, "scenario": {...},
    "used_by_model": {...}, "not_used_by_model": {"_note": "…", "dose": 0.5}
  },
  "residue_predictions": [{
    "residue_id": "A:74", "residue_type": "ARG", "proxy_rank": 1.0,
    "degradation_percent": 60.8391,
    "residue_type_in_model_vocabulary": true
  }],
  "aggregation": {
    "method": "mean_over_ranked_candidate_residues",
    "risk_band_basis": "Bands are the quartiles of the mock model's own …",
    "explanation": "The model's target is per-residue degradation …",
    "n_residues_predicted": 10, "n_residues_used_in_mean": 9,
    "n_residues_excluded_unknown_type": 1,
    "per_residue_min": 45.749, "per_residue_max": 60.839, "per_residue_std": 4.53,
    "whole_chain_mean_note": "A whole-chain mean is not available …",
    "exclusion_note": "1 residue(s) were excluded …"
  },
  "held_out_error": {"supported": false, "note": "…", "validation": {...}, "test": {...}}
}
```

`confidence` is **always** `null` — the bundle exposes no calibrated
uncertainty. `held_out_error` gives retrospective dataset-level metrics instead,
explicitly not a per-prediction interval.

`residue_type_in_model_vocabulary: false` means that row's one-hot block was all
zeros: the model has no information about that residue type and its estimate is
unreliable. Such rows are reported but excluded from `degradation_percent`.

Errors: `422` malformed, `404` unknown scenario, `400 INVALID_PDB_ID`,
`400 SCENARIO_NOT_ML_SUPPORTED` (with the supported list in `details`),
`503 MODEL_UNAVAILABLE`.

---

## Simulations

### `GET /simulation/presets`

Three presets, each declaring `platform`, `solvent`, `forcefield`,
`nonbonded_cutoff_nm`, step counts, `timestep_fs`, `simulated_time_ps`,
`estimated_runtime_note`, `scientific_label` and `limitations`.

### `GET /simulation/engine`

OpenMM availability and platforms, MDTraj availability, `max_concurrent_jobs`,
`active_jobs`, and which trajectory reader will be used.

### `POST /simulations` → `202`

```json
{
  "pdb_id": "1UBQ", "chain_id": "A",
  "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
  "preset_id": "rapid_demo", "temperature_kelvin": 300.0,
  "dose": 0.5, "dose_unit": "Gy", "exposure_duration_days": 180.0,
  "mechanical_force_pn": 0.0, "random_seed": 42,
  "prediction_id": "uuid", "ml_degradation_percent": 49.5216
}
```

`prediction_id` and `ml_degradation_percent` link the run to the estimate that
preceded it, so the results page can compare without a second call.

Returns the initial job record. Poll `GET /simulations/{job_id}`.

Errors: `503` OpenMM unavailable (with remediation in `details`), `409` a job is
already running, `400` invalid configuration, `404` unknown scenario.

### `GET /simulations/{job_id}`

```json
{
  "job_id": "…", "status": "running", "progress": 0.46,
  "current_stage": "production",
  "steps_completed": 2000, "steps_total": 6000,
  "elapsed_seconds": 11.4,
  "temperature_kelvin": 297.2, "potential_energy_kj_mol": -11513.4,
  "stages": [{"stage": "production", "label": "Production steps",
              "state": "active", "started_at": "…", "detail": "…"}],
  "log_tail": ["…last 200 lines…"],
  "artifacts": {"final_pdb": true, "trajectory_dcd": true, "…": true},
  "reproducibility": {"platform_resolved": "OpenCL",
                      "bitwise_reproducible": false, "…": "…"},
  "warnings": ["…"], "retry_hint": null,
  "ml_degradation_percent": 49.5216,
  "simulation_degradation_proxy_percent": null
}
```

`status` ∈ `queued | running | completed | failed | cancelled`.
`steps_completed` is the integrator's own counter — the ground truth for
progress. Poll roughly every 1–2 s and stop once status is terminal.

On failure, `error_code`, `error_message` and `retry_hint` are populated.
`retry_hint.preset_id` is `minimisation_only`.

### `GET /simulations` — history

Array of job summaries, newest first, read from the job directories on disk so
it survives a restart. `?limit=` 1–500, default 100.

### `POST /simulations/{job_id}/cancel`

Sets the cancel flag; the worker stops at its next 250-step boundary. Returns
`409 JOB_ALREADY_TERMINAL` if the job has finished. A cancelled job records
`cancelled`, never `completed`.

### `DELETE /simulations/{job_id}` → `204`

Deletes the directory and its artifacts. `409` if the job is still active.

### `GET /simulations/{job_id}/results`

`404` unless the job is `completed`. Contains `result_label`, the full `metrics`
block (including `degradation_proxy` with its formula, components and caveats),
six time `series`, per-residue `rmsf`, `highest_mobility_residues`,
`stability_summary`, the `comparison` block, `metadata`, `reproducibility`,
`warnings` and `limitations`.

For a minimisation-only run, `metrics.dynamics_run` is `false`, `n_frames` is 0
and there is **no** `degradation_proxy` — the metrics are reported as
unavailable rather than estimated.

### `GET /simulations/{job_id}/structure?which=final|prepared|topology|input`

- `input` — the file as submitted
- `prepared` — cleaned, single chain, heavy atoms only
- `topology` — **the exact simulated system, hydrogens included**
- `final` — coordinates at the end of the run

Pair `trajectory.dcd` with `topology`, not `prepared`: they differ in atom count
(1231 vs 602 for 1UBQ) and `prepared` will fail to load.

### `GET /simulations/{job_id}/trajectory`

DCD, `application/octet-stream`. `404` for a run that produced no trajectory.

### `GET /simulations/{job_id}/log`

Full worker log as `text/plain`.

### `GET /simulations/compare/{job_id_a}/{job_id_b}`

Both briefs, a `comparable` flag (false when presets differ — RMSD scales with
trajectory length, so it is not like-for-like), per-metric `differences` with a
winner, a `stability_ranking`, contextual `notes` and `interpretation_limits`.

---

## Precomputed fallback

### `GET /precomputed`

`{"available": ["1UBQ"], "notice": "…never presented as a live run."}`

### `GET /precomputed/{pdb_id}/results`

Same shape as job results, with `engine: "precomputed"`,
`result_label: "Precomputed OpenMM Result"` and a first warning stating it is
not a run performed on this machine now.

### `GET /precomputed/{pdb_id}/structure?which=final|input`

---

## Reports

### `GET /reports/{job_id}.json`

The complete record, `Content-Disposition: attachment`. Sections:
`scientific_notice` (including `what_this_is_not`), `experiment`, `protein`,
`scenario` with provenance, `ml_prediction` with its caveats, `simulation`,
`analysis` (all series plus per-residue RMSF), `comparison`,
`reproducibility`, `warnings`, `limitations`. Roughly 32 KB for a Rapid Demo run.

### `GET /reports/{job_id}.csv`

The same content flattened to `section,key,value,unit,note` rows — one shape that
holds scalars, time series and per-residue rows without a ragged header. Roughly
600 rows.

Prefixed with a UTF-8 BOM so Excel on Windows renders the units and symbols
correctly; pandas, R and text editors ignore it.

---

## Paired Mechanical Experiments

Exposes paired pristine-vs-damaged steered-MD mechanical pulling experiments.

### `POST /experiments/import`

Imports and validates an experiment artifact directory into the repository runtime.

```json
{
  "source_path": "path/to/experiment_directory",
  "experiment_id": "optional_override_id"
}
```

Response (`201 Created`):
```json
{
  "experiment_id": "1UBQ_MILD_74_seed1",
  "status": "imported",
  "message": "Successfully imported experiment '1UBQ_MILD_74_seed1'",
  "detail": { ... }
}
```

### `GET /experiments`

Lists available paired experiments (`?limit=100`, 1–500).

```json
[{
  "experiment_id": "1UBQ_MILD_74_seed1",
  "protein_id": "1UBQ",
  "pdb_id": "1UBQ",
  "chain_id": "A",
  "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
  "status": "COMPLETED",
  "severity_label": "MILD",
  "damage_residue_id": "A:74",
  "residue_type": "ARG",
  "baseline_stiffness": 603.0,
  "damaged_stiffness": 504.0,
  "stiffness_unit": "pN/nm",
  "mechanical_degradation_pct": 16.4179,
  "random_seed": 1,
  "is_synthetic": false,
  "qc_failures": []
}]
```

### `GET /experiments/{experiment_id}`

Full metadata, stiffness metrics, linear fit parameters, structural damage analysis beyond RMSD/RMSF (contact maps, SASA, hydrogen bonds, secondary structure, local RMSF), quality status, and available artifacts. Includes explicit non-causation scientific caveats.

Artifacts include downloadable `structural_analysis.json` and `structural_analysis.csv`.

### `GET /experiments/{experiment_id}/force-extension`

Paired time series data points (`time_ps`, `restraint_center_nm`, `end_to_end_nm`, `extension_nm`, `force_pn`, `work_kj_mol`, `potential_energy_kj_mol`) for both pristine baseline and damaged runs.

### `GET /experiments/{experiment_id}/structures/{condition}`

Serves raw PDB coordinates (`chemical/x-pdb`). Condition options: `baseline`, `pristine`, `damaged`, `baseline_prepared`, `damaged_prepared`, `baseline_topology`, `damaged_topology`.

### `GET /experiments/{experiment_id}/report`

Complete experiment record with manifests, features, and paired structural analysis as a downloadable JSON file.

---

## CORS

Restricted to the local frontend dev origins (5173 and 4173 on `localhost` and
`127.0.0.1`), configurable via `COSMORA_CORS_ORIGINS`. Deliberately not `*`: the
API accepts uploads and serves file downloads. Methods `GET, POST, DELETE,
OPTIONS`; `Content-Disposition` is exposed so a browser download gets its
filename.

In development the Vite proxy forwards `/api` to the backend, so the browser
sees a single origin and CORS does not apply at all.
