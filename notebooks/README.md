# notebooks/

Placeholders for the exploratory work that would accompany a scientifically
usable successor to the current bundle. They are intentionally empty: this MVP
does not retrain the model, and shipping a notebook that appears to derive the
shipped metrics would misrepresent where those numbers came from.

| Directory | Intended contents |
| --- | --- |
| `data_preparation/` | Feature extraction from structures, SASA computation, candidate ranking |
| `training/` | Hyperparameter search and fitting, replacing `COSMORA_mock_model_bundle.pkl` |
| `evaluation/` | Held-out analysis, error decomposition, calibration |
| `simulation_validation/` | Comparing simulation metrics against experimental force-spectroscopy data |

## What already exists as runnable code

The analysis a notebook would normally hold is already in scripts and tests,
so it runs in CI rather than rotting in a notebook:

| Question | Where it is answered |
| --- | --- |
| Does the bundle reproduce its published metrics? | `scripts/validate_model.py` (25 checks) |
| What exactly are the model's features and vocabularies? | `scripts/generate_feature_schema.py` reads them from the pipeline |
| Are the recovered feature formulas correct? | `backend/tests/test_proteins.py::test_candidate_score_formula_is_reproducible` |
| Is the estimate really dose-invariant? | `backend/tests/test_prediction.py::test_dose_does_not_change_the_ml_estimate` |
| Does a real simulation produce sane physics? | `scripts/run_demo_simulation.py`, and the `slow`-marked tests |

`legacy/train_surrogate_model.py` is the project's original training script,
preserved verbatim. It trained on synthetic damage of 1L2Y and is superseded by
the shipped bundle; it is kept for provenance, not for reuse.
