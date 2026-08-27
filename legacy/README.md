# legacy/

The project's original scripts, preserved verbatim. Nothing here is imported by
the application — they are kept for provenance and to document what was carried
forward.

| File | Status | Notes |
| --- | --- | --- |
| `build_contact_graph.py` | **Logic carried forward** | 8 Å Cα contact graph via BioPython + NetworkX. The backend reimplements this vectorised in `app/ml/preprocessing.py::compute_contact_counts`, and it reproduces the training reference table's `residue_contact_count` *exactly* (56/56 for 1PGA, 76/76 for 1UBQ). |
| `simulate_radiation_damage.py` | **Not wired in** | Represents radiation damage as probabilistic residue deletion (LEO 5 %, deep space 15 %, solar flare 30 % per residue). That is a structural ablation, not radiation physics — it removes whole residues rather than depositing energy or breaking bonds. Presenting deleted residues as radiation damage would misrepresent what happened, so the simulation path does not use it. Discussed in `docs/simulation-methodology.md §2`. |
| `train_surrogate_model.py` | **Superseded** | Trained XGBoost on synthetic damage of 1L2Y with graph-topology features. The shipped bundle (`models/bionano_mock_model_bundle.pkl`) replaces it, and this project does not retrain. |
| `main.py` | **Superseded** | The original FastAPI app. Its `/predict-damage` endpoint did **not** use the trained model: it returned a hardcoded heuristic (`180.0 * edge_ratio ** 1.2`) with baselines fixed to 1L2Y's 20 residues and 45 edges. The reusable part — `extract_graph_features` — lives on in the backend; the hardcoded response does not, because live API responses must come from the model. |

## Sample structures

`data/samples/` holds the original repository's 1L2Y (Trp-cage) files:
`1L2Y_legacy.pdb` and `1L2Y_legacy_damaged.pdb`. 1L2Y is **not** one of the five
approved proteins, so it is not in the registry, but the files are kept because
they were part of the original work and are useful for testing upload
validation.
