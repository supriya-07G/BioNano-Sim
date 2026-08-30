# Scientific claims checklist

Every claim COSMORA makes — in the README, the dashboard, or a presentation
— against the artifact that supports it and the limitation that qualifies it.
Run this before any tagged demo release (issue #27).

A claim with no supporting artifact does not ship. A claim whose limitation is
not stated where the claim appears does not ship either.

**Last completed:** 2026-08-30, commit `d6ceea2`
**Completed by:** clean-checkout run + source verification, not from memory

---

## 1. Claim → evidence → limitation

| Claim | Supporting artifact | Limitation, stated where the claim appears |
|---|---|---|
| Runs real molecular dynamics | OpenMM 8.6, Amber14 + GBn2; 9 `slow` tests execute real runs; [validation record](validation/2026-08-30-clean-checkout.md) | Picosecond scale, implicit solvent. Not a folding or binding simulation. |
| Applies a real pulling force | `app/simulation/pulling.py`, `MECHANICAL_PULL` preset, 24 tests | Constant-velocity steered MD at 0.03 nm/ps, ~10⁶× faster than AFM. Absolute forces are far above experiment; only within-protocol comparison is valid. |
| Measures stiffness in pN/nm | `force_extension.csv`, contract enforces `stiffness_unit` | An apparent stiffness from a non-equilibrium pull, not an equilibrium elastic modulus. |
| Discriminates load-bearing folds | [RESULTS.md §2](RESULTS.md) — 4 of 13 register, r² 0.52–0.82, others 0% QC | 13 proteins. 1TEN is a known false negative. |
| Damage is a structural proxy | `app/simulation/damage.py`, `PROXY_TYPE = SIDE_CHAIN_LOSS`, 17 tests | Side-chain truncation to ALA. Not radiation chemistry. |
| ML model trained on real simulation labels | `models/COSMORA_real_model_bundle.pkl`, `scripts/rebuild_real_bundle.py` | `scientifically_validated: false` — 18 labels of 30 required, 4 proteins of 8, worst label SE 13.6 pp against a 10.0 pp ceiling. Criteria and failures are recorded in the bundle itself. |
| Dataset is validated | `scripts/validate_dataset.py`, run in CI; 520 rows | Two provenance columns absent (documented producer gap). |
| Reproducible | `sim_config_hash`, seeded, `deterministic` mode pins CPU to 1 thread | Bit-reproducibility verified on CPU only, not across platforms. |

---

## 2. Which controls actually affect what

Verified against `app/simulation/validators.py` and `presets.py`.

| Control | Affects | Verified |
|---|---|---|
| `pdb_id` / `chain_id` / `upload_id` | thermal MD, pulling MD, ML | ✅ |
| `temperature_kelvin` | thermal MD, pulling MD | ✅ |
| `preset_id` | thermal MD, pulling MD | ✅ |
| `random_seed` | thermal MD, pulling MD | ✅ |
| `mechanical_force_pn` | **provenance only** | ✅ warned; preset-aware since `26c4304` |
| `dose` / `dose_unit` | **provenance only** | ✅ no dose enters any calculation |
| `exposure_duration_days` | **provenance only** | ✅ |
| `scenario_id` | **provenance only** | ✅ excluded from the model by construction |

✅ **Closed by #17.** Each input now carries its own badge in the experiment
form — `affects ML`, `drives simulation`, `not an ML input`, `provenance only` —
so the interface states the coupling before a run rather than leaving it to a
warning afterwards.

One correction was needed on top of it: the force control initially read
"pulling unavailable / future scope", which contradicted the Mechanical Pull
preset two rows below it in the same form. Steered MD shipped in #9. The badge
now reads `provenance only`, and the note points at the preset that does set
the load.

---

## 3. Metric definitions and units

| Metric | Unit | Defined in |
|---|---|---|
| `baseline_stiffness` / `damaged_stiffness` | pN/nm | [experiment-contract.md](experiment-contract.md) |
| `mechanical_degradation_pct` | percent, sign preserved | contract §rules 5 |
| `force_pn` | piconewtons | contract, `force_extension.csv` |
| `extension_nm`, `end_to_end_nm` | nanometres | contract |
| `rmsd_nm`, `rg_nm` | nanometres | `app/analysis/` |
| `potential_energy_kj_mol` | kJ/mol | `app/analysis/energy.py` |
| `fit_quality` / `r_squared` | dimensionless, 0–1 | contract, range-enforced |
| `target_sem` | percentage points | `scripts/aggregate_ml_labels.py` |

✅ Every reported metric carries a unit in its name or its schema.

---

## 4. Honesty checks

| Check | Status |
|---|---|
| Precomputed results visibly labelled | ✅ `precomputed_fallback` component; endpoint separate from live jobs |
| Synthetic labels never called experimental | ✅ mock bundle is `MOCK_PUBLIC_DATA_BOOTSTRAP`; `is_synthetic` enforced false in the real dataset |
| Damage proxy never called a radiation event | ✅ `severity_is_a_dose` must be `false`; scope notice says "Radiation is not simulated" since `a253518` |
| Model not presented as validated | ✅ `scientifically_validated: false` with three named failures |
| Negative results reported | ✅ [RESULTS.md §3–4](RESULTS.md) — two nulls with power analysis |

---

## 5. Numbers verified against CI

| Figure | Claimed | Actual | Status |
|---|---|---|---|
| Backend tests | 312 (303 fast + 9 slow) | 312 | ✅ verified |
| Experiments run | 520 | 520 | ✅ |
| Rows passing QC | 130 (25%) | 130 | ✅ |
| Usable labels / proteins | 18 / 4 | 18 / 4 | ✅ |
| Held-out R² | −0.004 | −0.004 | ✅ |

🔧 **Corrected across passes:** the README has twice drifted on this figure —
"100" and "147" in different sections, then "196" after the suite grew again.
It now reads 312, and `docs/architecture.md` was corrected with it. Test counts
drift faster than any other number here, which is why this row is checked
rather than trusted.

---

## 6. Demo script and screenshots

| Check | Status |
|---|---|
| Documented start commands work | ✅ verified in the clean-checkout record |
| Windows setup path documented | ✅ added this pass — `make` is not installed on Windows |
| `demo-script.md` matches current UI | ⚠️ **not re-verified**; the scope notice changed in `a253518` |
| Screenshots current | ⚠️ **no screenshots committed** |

---

## Release process

Before tagging a demo release:

1. Run `make validate` — environment, model and dataset checks.
2. Run `make test` and `make test-backend-all`; record the counts.
3. Walk this checklist top to bottom. Update every row that moved.
4. Update the "Last completed" line with today's date and the commit.
5. Any ⚠️ row is either fixed or called out explicitly in the demo.

An unchecked row is a claim you cannot defend when asked.
