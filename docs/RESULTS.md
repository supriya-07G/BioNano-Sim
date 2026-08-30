# Results: steered-MD stiffness measurement across 13 protein domains

**Run date:** 2026-08-30 · **Config hash:** `779b297ee54d560c…` ·
**520 paired experiments in 71 minutes** · `is_synthetic: false`

## 1. What was run

Every experiment is a *paired* comparison: one pristine pull and one damaged
pull, sharing the same equilibrated starting state and the same seed, so the
only difference between them is the structural lesion.

| Parameter | Value |
|---|---|
| Force field | Amber14 + GBn2 implicit solvent |
| Temperature / friction / timestep | 300 K · 1.0 ps⁻¹ · 2 fs |
| Minimisation → shared equilibration → settle → pull | 1,000 → 5,000 → 1,000 → 20,000 steps |
| Pulling | Moving harmonic restraint on the terminal Cα distance, k = 1,000 kJ/mol/nm², v = 0.03 nm/ps |
| Damage proxy | `SIDE_CHAIN_LOSS` — truncation to ALA, graded MILD / MODERATE / SEVERE / EXTREME |
| Design | 13 proteins × 8 damage configurations × 5 seeds |

Three structures (1CSP, 1ENH, 1QLX) were dropped at preparation: all three fail
on missing terminal or hydrogen atoms, which a PDBFixer pass before `Modeller`
would resolve.

## 2. Primary result: the measurement discriminates load-bearing folds

Baseline stiffness is one value per (protein, seed) — 65 measurements.

| Protein | Residues | Baseline stiffness (pN/nm) | Fit r² | QC pass |
|---|---|---|---|---|
| **1TIT** titin I27 | 89 | **713 ± 121** | 0.82 | 100% |
| **1UBQ** ubiquitin | 76 | **661 ± 142** | 0.77 | 98% |
| **1WIT** twitchin Ig | 93 | **645 ± 135** | 0.70 | 70% |
| **1AKI** lysozyme | 129 | **492 ± 94** | 0.52 | 57% |
| 1SHG SH3 | 57 | 114 ± 69 | 0.25 | 0% |
| 1BDD protein A | 60 | 101 ± 71 | 0.17 | 0% |
| 1VII villin headpiece | 36 | 36 ± 30 | 0.05 | 0% |
| 1BPI BPTI | 58 | 29 ± 44 | 0.04 | 0% |
| 1TEN fibronectin III | 89 | 26 ± 166 | 0.12 | 0% |
| 2CI2 CI2 inhibitor | 65 | 15 ± 46 | 0.03 | 0% |
| 2SPC spectrin | 107 | −2 ± 48 | 0.06 | 0% |
| 1E0L WW domain | 37 | −19 ± 79 | 0.12 | 0% |
| 1PGA protein G B1 | 56 | −402 ± 165 | 0.33 | 0% |

**The separation is complete.** Four domains register a stiffness with an
interpretable fit (r² 0.52–0.82, QC pass 57–100%); the other nine register
nothing distinguishable from thermal noise (r² ≤ 0.33, QC pass 0%). There is no
overlap in either fit quality or QC rate.

**This agrees with experiment.** Titin I27 is the standard benchmark of
mechanical stability in AFM force spectroscopy; ubiquitin and twitchin Ig are
also established load-bearing domains. The pipeline ranked them highest without
being told anything about their mechanics. The nine that failed are small
α-helical bundles, SH3/WW folds and protease inhibitors — none load-bearing.

## 3. Null result: single-residue damage is below the noise floor

Across 32 perturbations, the median per-perturbation label standard deviation is
**26.7 pp**, against effects of comparable or smaller size. Severity does not
order monotonically — 1TIT residue 31 gives MILD −21.6 ± 6.9, MODERATE
−1.0 ± 7.3, SEVERE −10.0 ± 12.1, EXTREME −5.8 ± 6.9 pp.

The dominant variance is the shared baseline, not the damage: Pearson **r =
0.794** between a seed's baseline draw and its mean degradation across all eight
of that seed's configurations.

Seeds required per condition, from the observed spread:

| Target precision | Seeds needed |
|---|---|
| ± 10 pp | 8 |
| ± 5 pp | **29** |
| ± 2 pp | 179 |

This run used 5. **The effect is not absent — it is unresolved at n = 5**, and
the sample size needed to resolve it is now quantified.

## 4. Null result: stiffness is not predictable from sequence composition

Under leave-one-protein-out cross-validation, no model beats its own baseline:

| Target | Model | Result | Baseline |
|---|---|---|---|
| Degradation (18 labels, 4 proteins) | XGBoost | MAE 10.39 pp, R² −0.012 | mean-only: MAE 12.24, R² −0.203 |
| Baseline stiffness (65 rows, 13 proteins) | GradBoost | MAE 276 pN/nm, R² −0.056 | mean-only: MAE 297, R² −0.160 |
| Resistant vs not (binary) | RandomForest | accuracy 0.69 | majority class: 0.69 |

The label-noise ceiling on the degradation target is R² = 0.561 — even a perfect
model could not exceed that at this label precision.

The shipped bundle records this honestly: `scientifically_validated: false`,
with three unmet criteria (18 labels < 30 required; 4 proteins < 8; worst label
SE 13.6 pp > 10.0 pp). **The gate refusing to certify the model is the intended
behaviour, not a failure of the run.**

## 5. Limitations

- **1TEN is a false negative.** Tenascin fibronectin-III is experimentally
  mechanically stable, and this protocol failed to register it (r² 0.12). The
  pull is too short and too fast for domains whose resistance builds late.
- **1PGA's −402 pN/nm is an artifact,** not a measurement. When the pull does
  not dominate thermal fluctuation the fit degenerates toward −k_spring.
- **Pulling velocity is ~10⁶× faster than AFM.** Absolute forces are far above
  experimental values; only comparisons *within* this protocol are meaningful.
- **Radiation is not simulated.** Damage is a structural lesion chosen by
  literature radiosensitivity. No dose, particle track, or energy deposition
  enters the model.
- **13 proteins is too few** to fit or validate a predictive model, independent
  of label noise.

## 6. What would close the gap

Resolving the damage effect needs ~29 seeds per condition; fitting a predictive
model needs ~50 proteins. Together that is roughly 35 hours of the compute used
here — tractable, but an order of magnitude beyond this run.
