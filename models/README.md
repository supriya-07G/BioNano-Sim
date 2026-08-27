# models/

| File | Purpose |
| --- | --- |
| `bionano_mock_model_bundle.pkl` | The ML bundle. joblib + zlib, 56,267 bytes. |
| `model_metadata.json` | Shipped metadata: version, status, features, metrics, splits. |
| `release_manifest.json` | SHA-256 of the bundle, checked at load time. |
| `feature_schema.json` | **Generated.** Do not hand-edit. |

## Scientific status

`MOCK_PUBLIC_DATA_BOOTSTRAP` · labels `SYNTHETIC_PUBLIC_DATA_PROXY` ·
`scientifically_validated: false` · approved use
`DASHBOARD_AND_API_INTEGRATION_TESTING_ONLY`.

This is a demonstration artifact. Its training labels are a synthetic proxy
derived from public structural data, not experimental measurements. Do not use it
for scientific inference or cite it as evidence about protein radiation
tolerance. See [`../docs/model-card.md`](../docs/model-card.md) for the full
card, including measured failure modes.

## Bundle contents

A dict with keys `pipeline`, `metadata`, `feature_columns`, `target_column`,
`model_version`, `scientific_status`.

`pipeline` is a scikit-learn `Pipeline([('preprocessor', ColumnTransformer),
('model', XGBRegressor)])`. **Preprocessing is bundled**, so call
`pipeline.predict(DataFrame[feature_columns])` and never re-implement the
transforms.

## feature_schema.json is generated

```bash
python scripts/generate_feature_schema.py
```

Every vocabulary and bound in it is read out of the pickled pipeline itself, so
the contract the API validates against cannot drift from the model it validates
for. `app/ml/loader.py` re-verifies the file against the live pipeline at startup
and reports `schema_verified: false` through `/model` and `/system/readiness` if
they disagree.

## Loading requirements

The pins in `backend/requirements.txt` are load-bearing:

- **scikit-learn == 1.7.1.** The exact version the pipeline was fitted with.
  Unpickling a scikit-learn estimator under a different minor version raises
  `InconsistentVersionWarning` and is not guaranteed to reproduce the training
  transforms.
- **NumPy >= 2.0.** The pickle references `numpy._core.multiarray`, which does
  not exist on NumPy 1.x. NumPy 1.x simply cannot open this file.
- **Python 3.11.** The pinned set does not resolve on 3.12+.
- **xgboost == 2.1.3.** XGBoost warns on any cross-version pickle; numerical
  fidelity is verified separately by reproducing the shipped prediction reports.

## Verifying

```bash
python scripts/validate_model.py
```

25 checks. The decisive one reproduces
`data/ml/reports/{validation,test}_predictions.csv` from
`data/ml/splits/{validation,test}.csv` and confirms
`max|diff| < 1e-4` — actual measured value ≈ 1.9e-06, which is CSV write
precision. If that passes, the pipeline in your environment is numerically the
same one that produced the published metrics.

It also confirms the SHA-256 against the manifest, that the schema matches the
live encoder, that repeated prediction is deterministic, and — deliberately —
that the model returns a plausible number for an unknown category, which is why
the unknown-category guard exists.

## Replacing the bundle

1. Drop the new `.pkl` in, update `release_manifest.json` with its SHA-256.
2. `python scripts/generate_feature_schema.py`
3. `python scripts/validate_model.py`
4. `cd backend && python -m pytest tests/test_prediction.py`

If the new bundle has different feature names, the schema regenerates to match
and the API's validation guards follow automatically — nothing in the backend
hardcodes a feature name.

## What a scientifically usable successor needs

From the shipped metadata: *"Retrain using real paired baseline and damaged
simulation stiffness results."* Beyond that: all 20 amino acids in the encoder
vocabulary, numeric dose and dose rate as genuine features, a no-radiation
control condition, calibrated uncertainty, and enough proteins that
generalisation can be measured rather than hoped for.
