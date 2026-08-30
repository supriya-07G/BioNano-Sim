# Paired mechanical experiment contract — v1.0

The integration boundary between the simulation, ML, backend and dashboard
sides. A producer writes these artifacts; a consumer reads them without
renaming, re-deriving units, or asking the other team what a field means.

**Enforced by:** [`backend/app/contracts/paired_experiment.py`](../backend/app/contracts/paired_experiment.py)
**Tested by:** [`backend/tests/test_experiment_contract.py`](../backend/tests/test_experiment_contract.py) — 35 tests
**Fixtures:** `backend/tests/fixtures/contract/` — one valid, twelve invalid

Version 1.0 matches `SCHEMA_VERSION` in `scripts/run_paired_experiment.py`.
Bumping it is a breaking change and fails a test deliberately.

## Directory layout

One experiment is one directory. The two runs are siblings so a reader never
has to guess which damaged run pairs with which pristine one.

```
<experiment_id>/
  baseline_job/                 pristine run
    prepared.pdb
    trajectory.dcd
    force_extension.csv
  damaged_job/                  damaged run, same protocol, same seed
    prepared.pdb
    trajectory.dcd
    force_extension.csv
  baseline_force_extension.csv  copies hoisted for direct consumption
  damaged_force_extension.csv
  baseline_features.json
  damaged_features.json
  damage_manifest.json          what was removed, and its hashes
  manifest.json                 protocol, provenance, both run descriptors
  result.json                   the paired result -- the primary artifact
  stiffness_row.csv             this experiment as one dataset row
```

## `force_extension.csv`

Seven columns, fixed order. **Units are in the column names** — there is no
separate units file to fall out of sync.

| Column | Unit | Meaning |
|---|---|---|
| `time_ps` | picoseconds | simulation time since the pull began |
| `restraint_center_nm` | nanometres | where the moving restraint centre is |
| `end_to_end_nm` | nanometres | measured terminal Cα–Cα distance |
| `extension_nm` | nanometres | `end_to_end_nm` minus its value at pull start |
| `force_pn` | piconewtons | force carried by the restraint |
| `work_kj_mol` | kJ/mol | cumulative work done by the restraint |
| `potential_energy_kj_mol` | kJ/mol | system potential energy |

Force is stored in **piconewtons**, not kJ/mol/nm. The conversion factor is
1660.54, so a producer that writes the wrong unit inflates every stiffness by
three orders of magnitude. `stiffness_unit` is a literal type for this reason:
a wrong unit fails validation instead of silently poisoning a training set.

## `result.json`

The primary artifact. Required fields, grouped:

**Identity** — `experiment_id`, `schema_version`, `status`
**Subject** — `protein_id`, `pdb_id`, `chain_id`
**Damage** — `damage_residue_id`, `residue_type`, `proxy_type`,
`severity_label`, `n_residues_damaged`, `damage_residue_ids`,
`severity_is_a_dose`
**Provenance** — `random_seed`, `sim_config_hash`, `is_synthetic`
**Measurement** — `baseline_stiffness`, `damaged_stiffness`, `stiffness_unit`,
`mechanical_degradation_pct`, and optionally `baseline_fit` / `damaged_fit`
**Quality** — `qc_failures`

Additional fields are **allowed**. Producers extend as the science develops,
and rejecting a richer file would force four teams to release in lockstep.

### Rules the contract enforces

1. **`stiffness_unit` can only be `pN/nm`.**
2. **`status='QC_FAILED'` requires a non-empty `qc_failures`.** Silent rejection
   is how unexplained holes appear in a dataset weeks later.
3. **`status='COMPLETED'` requires an empty `qc_failures`.** A run cannot both
   pass and fail.
4. **`status='COMPLETED'` requires finite stiffness and degradation values.**
5. **Degradation is re-derived and must agree** with
   `(baseline − damaged) / baseline × 100` to within 0.05 pp. A mismatch means
   the producer changed the definition, mixed units, or wrote two stiffnesses
   from different runs — all of which corrupt a training set silently.
6. **`n_residues_damaged` must equal `len(damage_residue_ids)`**, and
   `damage_residue_id` must appear in that list.
7. **`severity_is_a_dose` must be `false`.** Severity counts removed side
   chains. It is a structural axis and corresponds to no Gy, LET or fluence.
8. **`sim_config_hash` must be a full 64-character sha256.**
9. **Residue ids are chain-qualified** — `A:74`, never `74`.
10. **An unreliable fit must list `unreliable_reasons`**, and a fit interval
    must be increasing.

### Sign convention

Degradation preserves sign. A **negative** value means the damaged construct
measured *stiffer* than the pristine one. This happens, it is physically real
at short pull times, and it is reported as measured rather than clamped to
zero. Consumers must handle negative values.

## `stiffness_results_REAL_v1.csv`

One row per experiment — the flat projection the ML side consumes. Twenty-three
columns: the nineteen the ML spec fixed, then four severity columns appended
after them, so a reader selecting by position still finds the spec block first.

Unlike `result.json`, unknown columns are **rejected** here: a stray column
means the CSV writer drifted from the contract.

`is_synthetic` must be `false`. Synthetic rows belong in a separate file.

### Known producer gap

The Kaggle notebook is a second producer of this file and predates the
contract. It omits two columns, both pure provenance:

- `job_id`
- `git_commit`

The rows remain scientifically usable — every measurement, unit and quality
field is present and validated. The gap is pinned in
`KAGGLE_PRODUCER_GAP` so it cannot widen unnoticed; a third missing column
fails the test suite.

All **520 rows** of the committed dataset validate against this contract.

## Validation

```python
from app.contracts.paired_experiment import (
    validate_result_payload, validate_stiffness_row,
)

result = validate_result_payload(json.loads(path.read_text()))   # ValidationError on breach
row = validate_stiffness_row(csv_row)
```

Regenerate the invalid fixtures after changing a rule:

```bash
python backend/tests/fixtures/contract/make_invalid.py
```
