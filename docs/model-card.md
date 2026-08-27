# Model card — BioNano-Sim Public Bootstrap Model

| Field | Value |
| --- | --- |
| Name | BioNano-Sim Public Bootstrap Model |
| Version | `0.2.0-mock` |
| Scientific status | `MOCK_PUBLIC_DATA_BOOTSTRAP` |
| Label source | `SYNTHETIC_PUBLIC_DATA_PROXY` |
| Scientifically validated | **No** |
| Approved use | `DASHBOARD_AND_API_INTEGRATION_TESTING_ONLY` |
| Created | 2026-08-26T18:59:01Z |
| Artifact | `models/bionano_mock_model_bundle.pkl` (56,267 bytes) |
| SHA-256 | `00828fda47e2550c834b2c2d9e6b6a4786ee62721cbda759b15462e39353b6ba` |
| Target | `mechanical_degradation_pct` — **per candidate residue** |

> This model is a demonstration artifact. Its training labels are a synthetic
> proxy derived from public structural data, not experimental measurements of
> protein degradation. It must not be used for scientific inference or cited as
> evidence about protein radiation tolerance.

---

## 1. Architecture

A scikit-learn `Pipeline` with two steps:

```
Pipeline
├── preprocessor : ColumnTransformer  (remainder='drop')
│   ├── numeric      : SimpleImputer(strategy='median', add_indicator=True)   → 8 columns
│   └── categorical  : SimpleImputer(strategy='most_frequent')
│                    → OneHotEncoder(handle_unknown='ignore', sparse_output=True) → 25 columns
└── model        : XGBRegressor
```

33 transformed features. Because preprocessing is bundled, BioNano-Sim calls
`pipeline.predict(DataFrame[feature_columns])` directly and never
re-implements the transforms.

Best hyperparameters from the shipped metadata: `n_estimators=350`,
`max_depth=3`, `learning_rate=0.03`, `subsample=1.0`, `colsample_bytree=0.7`,
`reg_lambda=0.5`, `reg_alpha=0.01`, `min_child_weight=1`.

Since `add_indicator=True` but the training data had no missing numerics,
`indicator_.features_` is empty and no indicator columns are appended. Passing
`NaN` at inference is therefore imputed to the training median without changing
the column count.

---

## 2. Features

### Numeric (8)

| Feature | Meaning | Training range | Imputer median |
| --- | --- | --- | --- |
| `protein_length` | Residues in the chain | 56 – 107 | 89.0 |
| `molecular_weight` | Da, from sequence | 6195.7 – 12273.6 | 9782.1027 |
| `hydrophobic_fraction` | Fraction in {A,F,I,L,M,V,W,Y} | 0.375 – 0.4045 | 0.4019 |
| `charged_fraction` | Fraction in {D,E,K,R} | 0.2472 – 0.3271 | 0.2857 |
| `residue_index_norm` | `i/(n−1)`, 0-based | 0 – 1 | 0.4205 |
| `residue_sasa_norm` | Per-chain min–max normalised SASA | 0.3607 – 1 | 0.7084 |
| `residue_contact_count` | Cα neighbours within 8.0 Å | 4 – 11 | 8.0 |
| `proxy_rank` | Candidate rank, 1 = most susceptible | 1 – 10 | 5.5 |

### Categorical (6) — the encoder's exact fitted vocabulary

| Feature | Values |
| --- | --- |
| `residue_type` | ARG, ASN, ASP, GLN, GLU, HIS, LEU, LYS, MET, PRO, THR, TRP, TYR, VAL **(14 of 20)** |
| `qualitative_susceptibility` | high, low, medium |
| `scenario_id` | GCR_DEEP_SPACE_REFERENCE, MARS_SURFACE_REFERENCE, SPE_REFERENCE_EVENT |
| `radiation_class` | GCR, SPE |
| `environment` | free_space, mars_surface |
| `proxy_type` | SIDE_CHAIN_LOSS |

`models/feature_schema.json` is **generated** from the pickled pipeline by
`scripts/generate_feature_schema.py`, so these vocabularies are the encoder's
own categories rather than a hand-maintained copy. The loader re-verifies the
file against the live pipeline at startup and refuses to trust it silently if
they disagree.

### Feature importance (gain, top 8)

| Transformed feature | Importance |
| --- | --- |
| `radiation_class_SPE` | 0.2509 |
| `radiation_class_GCR` | 0.2399 |
| `scenario_id_SPE_REFERENCE_EVENT` | 0.1386 |
| `proxy_rank` | 0.0875 |
| `charged_fraction` | 0.0408 |
| `environment_free_space` | 0.0403 |
| `hydrophobic_fraction` | 0.0381 |
| `residue_sasa_norm` | 0.0369 |

Radiation category alone accounts for roughly 63 % of the model's importance.
Residue-level structural features matter much less.

---

## 3. Data

| Artifact | Rows | Contents |
| --- | --- | --- |
| `data/ml/data/public_residue_features.csv` | 417 | Per-residue static features for the 5 proteins |
| `data/ml/data/ranked_candidate_residues.csv` | 50 | Top-10 candidate residues per protein |
| `data/ml/data/bionano_mock_experiments_v1.csv` | 450 | 5 proteins × 10 residues × 3 scenarios × 3 seeds |
| `data/ml/splits/train.csv` | 270 | 1PGA, 1TIT, 2SPC |
| `data/ml/splits/validation.csv` | 90 | 1UBQ |
| `data/ml/splits/test.csv` | 90 | 1TEN |

Splits are **by protein**, not random — the right choice for measuring
generalisation to an unseen fold.

Target distribution across all 450 rows: min 34.13 %, Q1 46.23 %, median
52.34 %, Q3 58.91 %, max 78.29 %, mean 52.97 %. Those quartiles are what the
UI's low/moderate/elevated/high risk bands are derived from, so a "high"
reading means "in the top quartile of what this model produces" rather than
anything experimental.

---

## 4. Evaluation

| Split | Protein | Rows | MAE (pp) | RMSE | R² |
| --- | --- | --- | --- | --- | --- |
| Validation | 1UBQ (unseen) | 90 | 4.108 | 4.854 | 0.702 |
| Test | 1TEN (unseen) | 90 | 2.256 | 2.858 | 0.844 |

`scripts/validate_model.py` recomputes both from the shipped prediction reports
and confirms they match the published values to six decimal places. It also
confirms that inference in your environment reproduces
`data/ml/reports/{validation,test}_predictions.csv` to `max|diff| ≈ 1.9e-06`,
which is CSV write precision — i.e. the pipeline in your environment is
numerically the same one that produced the published metrics.

**These metrics describe agreement with synthetic proxy labels, not with
experimental measurements.** An R² of 0.844 against a proxy says the model
learned the proxy's generating process; it says nothing about physical reality.

---

## 5. Uncertainty

The bundle exposes no `predict_proba`, no quantile heads and no calibrated
interval. BioNano-Sim reports `confidence: null` rather than fabricating a
figure.

The held-out MAE values above are offered instead, clearly separated in the UI
under "Held-out error (retrospective, dataset-level)". They describe how the
model performed on two proteins overall — they are **not** an error bar for any
individual estimate.

---

## 6. Known failure modes

### 6.1 Unknown categories fail silently

`OneHotEncoder(handle_unknown='ignore')` encodes an unseen category as an
all-zero block and the model still returns a confident-looking number. Measured
directly:

| Input | Prediction |
| --- | --- |
| `residue_type='LYS'` (in vocabulary) | 60.5277 % |
| `residue_type='XXX'` (unknown) | 60.5295 % |

A 0.0018 pp difference — undetectable from the output alone. BioNano-Sim
therefore compares every categorical value against the encoder's vocabulary
*before* predicting, warns explicitly, flags the affected residues in the
inspector, and excludes them from the protein-level mean.

Because the vocabulary covers only 14 of 20 amino acids (missing ALA, CYS, GLY,
ILE, PHE, SER), this fires on the approved set too: **1UBQ's rank-2 candidate is
GLY** and **1TEN has a PHE candidate**.

### 6.2 No dose, duration, temperature or force input

Radiation intensity reaches the model only through the categorical scenario
fields. Setting the dose to 0.001 Gy or 900 kGy produces an identical estimate —
there is a regression test asserting exactly that
(`test_dose_does_not_change_the_ml_estimate`). The interface labels these
controls "not an ML input" at the control itself.

### 6.3 Only three scenario configurations exist

`scenario_id`, `radiation_class` and `environment` are perfectly correlated
across just three combinations. There is no zero-radiation control and no
mechanical-only condition. Requesting an estimate for the
`BASELINE_NO_RADIATION` or `MECHANICAL_STRESS_TEST` presets returns
`400 SCENARIO_NOT_ML_SUPPORTED` with an explanation, rather than extrapolating.

### 6.4 Per-residue target, protein-level display

The model scores one residue at a time. BioNano-Sim's protein-level percentage
is the arithmetic mean over the ranked candidates, computed by the application
and labelled as such in `aggregation.method`. Because those candidates are the
*most* susceptible residues in the chain, the mean is an upper-leaning
indicator, not a whole-chain average. A whole-chain mean is deliberately not
offered: the model never saw low-ranked residues.

### 6.5 Tiny training set

Five proteins, 450 rows, all small single-domain folds of 56–107 residues.
Generalisation beyond that regime is unverified.

---

## 7. Featurising uploaded structures

Approved proteins are featurised from `public_residue_features.csv` — the exact
table the model was fitted on — so fidelity is perfect by construction.

Uploads have no such table. The dataset shipped no generating code, so the
formulas were recovered from the CSVs and verified against all five proteins:

| Quantity | Formula | Verification |
| --- | --- | --- |
| `hydrophobic_fraction` | fraction in {A,F,I,L,M,V,W,Y} | exact, 5/5 proteins |
| `charged_fraction` | fraction in {D,E,K,R} (no histidine) | exact, 5/5 proteins |
| `residue_index_norm` | `i/(n−1)`, 0-based | exact |
| `residue_contact_count` | Cα neighbours ≤ 8.0 Å, self excluded | **exact** (56/56 for 1PGA, 76/76 for 1UBQ) |
| `_inverse_packing` | `1 − contacts / max(contacts)` | exact |
| `_susceptibility_score` | high → 1.00, medium → 0.60, low → 0.25 | exact |
| `_candidate_score` | `0.45·sasa + 0.30·inv_packing + 0.25·susceptibility` | **exact to 1.1e-16** over all 50 rows |

Residue inclusion requires a **Cα atom** in addition to being a standard amino
acid with hetflag `" "`. That clause is what reconciles a naive 90-residue parse
of 1TEN with the reference table's 89: residue `A:802` is an arginine carrying
only C and O.

Qualitative susceptibility by residue: **high** = C, H, M, W, Y; **medium** =
R, N, Q, K, F, P, S, T; **low** = A, D, E, G, I, L, V.

### The one gap

`residue_sasa_norm` does **not** reproduce. It is per-chain min–max normalised
solvent accessibility, but the reference used a different implementation or
atom-radius set. BioPython's `ShrakeRupley` (probe 1.40 Å, 100 points, chain in
isolation, hydrogens stripped) gives:

| Protein | Pearson r | Spearman ρ |
| --- | --- | --- |
| 1UBQ | 0.933 | 0.938 |
| 1PGA | 0.975 | 0.974 |
| 1TIT | 0.991 | 0.991 |

Strongly correlated but not bit-identical. Alternatives were tested
systematically — relative solvent accessibility normalised by Tien et al.
maximum ASA, probe radii 1.0/1.4/1.8 Å, 100 and 960 sphere points, with and
without hydrogens — and none reproduced the reference. Every upload prediction
therefore carries an explicit warning that this feature is approximate, and the
approved-protein path never uses the recomputed value.

---

## 8. Replacement requirement

From the shipped metadata:

> Retrain using real paired baseline and damaged simulation stiffness results.

Until that happens, no accuracy claim about physical protein degradation is
defensible from this model. Additional work needed for a scientifically usable
successor:

1. Real paired measurements (baseline and post-exposure) as labels.
2. All 20 amino acids in the encoder vocabulary.
3. Numeric dose, dose rate, particle spectrum and exposure duration as genuine
   features, so the model can respond to exposure magnitude at all.
4. A no-radiation control condition in the training data.
5. Calibrated uncertainty — quantile regression or a conformal wrapper.
6. Enough proteins that generalisation can be measured rather than hoped for.

---

## 9. Reproducing every claim here

```bash
python scripts/validate_model.py          # 25 checks, including reproduction
python scripts/generate_feature_schema.py # regenerate the schema from the bundle
cd backend && python -m pytest tests/test_prediction.py -v
```

The environment must be Python 3.11 with `scikit-learn==1.7.1`, `numpy>=2`,
`xgboost==2.1.3`. The pickle references `numpy._core.multiarray`, which does not
exist on NumPy 1.x, and a different scikit-learn minor version voids the
guarantee that training transforms are reproduced.
