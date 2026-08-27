# Contributing to BioNano-Sim

Thank you for contributing. BioNano-Sim combines molecular simulation, mechanical analysis, machine learning, and a scientific dashboard. A small undocumented change can invalidate results across several parts of the system, so all contributors must follow the rules below.

## 1. Non-negotiable rules

1. **Do not push feature work directly to `main`.**
2. **Do not commit secrets, local environments, runtime jobs, large raw trajectories, or generated caches.**
3. **Do not change a scientific formula, unit, simulation preset, feature definition, or data schema without documentation and tests.**
4. **Do not add rows directly to the real ML dataset unless they pass the approved dataset validator and have `quality_status = valid`.**
5. **Do not mix synthetic/bootstrap data with validated real simulation-derived data.**
6. **Do not describe a damage proxy as literal cosmic-radiation physics.**
7. **Do not report a test count, accuracy, benchmark, or scientific result that current CI and committed artifacts cannot reproduce.**
8. **A feature is not complete until its tests, error handling, documentation, and acceptance criteria are complete.**

If you are unsure whether a change affects scientific meaning, open or comment on a `scientific concern` issue before implementation.

## 2. Project boundaries

BioNano-Sim contains three distinct evidence sources:

| Source | Meaning | Allowed wording |
| --- | --- | --- |
| Mock bootstrap ML model | Model trained on synthetic proxy labels | Demo/mock prediction |
| Rapid OpenMM simulation | Real classical molecular dynamics over short timescales | Thermal structural simulation |
| Paired mechanical experiment | Pristine and damaged structures tested with the same pulling protocol | Simulation-derived mechanical degradation |

Standard OpenMM does not directly simulate particle transport, radiolysis, quantum chemistry, or cosmic-radiation bond breaking. A mutation, residue deletion, side-chain transformation, or other controlled alteration must be called a **damage proxy** unless a validated radiation-chemistry implementation is introduced.

## 3. Before starting work

1. Read the relevant GitHub issue completely.
2. Confirm that the issue has clear acceptance criteria.
3. Check whether another issue or pull request already implements the same work.
4. Identify dependencies and blocking issues.
5. Comment on the issue that you are taking it.
6. Create a branch from the latest `main`.

Recommended branch names:

```text
feature/issue-18-paired-structure-viewer
fix/issue-1-precomputed-structure
simulation/issue-9-pulling-protocol
ml/issue-10-real-model
data/issue-6-dataset-validator
docs/issue-27-claims-checklist
test/issue-29-release-gates
```

Keep one logical issue per branch whenever practical.

## 4. Local setup

Required versions:

- Python 3.11
- Node.js 18 or newer
- Git

Initial setup:

```bash
make setup
make validate
```

Run the application in separate terminals:

```bash
make backend
```

```bash
make frontend
```

Before changing code, run the relevant existing tests so you know the starting state.

## 5. Repository areas

| Area | Location | Responsibility |
| --- | --- | --- |
| FastAPI application | `backend/app/` | APIs, orchestration, security and persistence |
| Simulation engine | `backend/app/simulation/` | OpenMM preparation, execution and job lifecycle |
| Analysis | `backend/app/analysis/` | Structural and mechanical metrics |
| ML | `backend/app/ml/`, `models/` | Feature schema, model loading and inference |
| Backend tests | `backend/tests/` | Unit, API, scientific and simulation tests |
| Dashboard | `frontend/src/` | React UI, charts, 3D viewer and user workflows |
| Validated data | `data/real_experiments/` | Accepted paired simulation-derived experiments |
| Mock data | `data/ml/` | Synthetic/bootstrap artifacts; never merge with real data |
| Documentation | `docs/` | Architecture, scientific scope, model cards and demo guides |
| Runtime output | `runtime/` | Generated local jobs; not source-controlled |

Do not move files between these areas without updating imports, documentation, tests, and artifact paths.

## 6. Scientific change protocol

A scientific change includes any modification to:

- force field, solvent model, constraints, integrator, timestep, temperature, or seeds;
- minimization, equilibration, production, or pulling settings;
- damage-proxy definition;
- stiffness fit method or interval;
- RMSD, RMSF, radius-of-gyration, SASA, contact, hydrogen-bond, or energy calculations;
- feature definitions, target calculation, dataset inclusion rules, or ML split logic;
- units, thresholds, quality gates, or uncertainty calculations.

Every scientific change must include:

1. the reason for the change;
2. the previous and new behavior;
3. equations and units where relevant;
4. a known-answer or reference validation test;
5. impact on existing datasets, models, precomputed results, and documentation;
6. a version bump when outputs are no longer comparable.

Never silently regenerate a precomputed result or trained model.

## 7. Simulation contribution rules

All paired pristine/damaged experiments must:

- use the approved experiment contract;
- use identical preparation, equilibration, and pulling protocols for both conditions;
- record the damage proxy and affected residue;
- write force-extension data with explicit units;
- record baseline and damaged stiffness;
- record stiffness-fit diagnostics;
- record random seeds and resolved OpenMM platform;
- record software and input hashes;
- pass all simulation quality gates;
- set `quality_status = valid` before dataset inclusion.

A failed, incomplete, warning, manually edited, or unreproducible experiment must not enter the real training dataset.

Do not commit large DCD trajectories to normal Git history. Use the approved artifact-storage process or small dedicated test fixtures.

## 8. Real dataset rules

The validated dataset is append-only through the approved ingestion and validation pipeline.

Before adding an experiment:

```text
raw simulation artifacts
        ↓
paired experiment contract validation
        ↓
scientific and quality gates
        ↓
artifact hashes and manifest
        ↓
quality_status = valid
        ↓
stiffness_results_REAL_v1.csv
```

Contributors must not:

- edit target values manually;
- copy synthetic rows into the real dataset;
- combine units without conversion;
- reuse an experiment ID;
- place related replicates across different ML splits;
- delete an accepted row without documenting the reason and creating a new dataset version.

Every dataset change must update its manifest, row count, coverage summary, and hash.

## 9. ML contribution rules

The real model must train only from validated simulation-derived rows.

Required safeguards:

- grouped splits by protein and damage configuration;
- no target leakage;
- preprocessing packaged with the estimator;
- deterministic feature generation;
- dataset and feature-schema versioning;
- baseline-model comparison;
- reproducible metrics;
- explicit uncertainty or `confidence: null`;
- out-of-domain detection;
- separate artifact names and scientific-status labels for mock and real models.

Do not overwrite the mock model with the real model or present synthetic evaluation metrics as physical accuracy.

A model pull request must include:

- training command;
- dataset manifest/hash;
- feature schema;
- model card;
- evaluation report;
- saved prediction reproduction;
- bundle integrity checks;
- inference tests.

## 10. Frontend contribution rules

The interface must keep evidence sources visually distinct:

- mock ML prediction;
- thermal OpenMM result;
- paired mechanical degradation;
- precomputed versus live result.

For UI work:

- use semantic design tokens rather than hard-coded theme colors;
- support Light, Dark, and System modes;
- preserve keyboard accessibility and visible focus;
- respect reduced-motion preferences;
- provide loading, empty, error, and retry states;
- test at 1366×768 and the agreed tablet/mobile viewports;
- ensure charts expose units and readable legends;
- ensure inactive/provenance-only controls cannot appear physically active;
- never remove scientific warnings merely to simplify the screen.

Judge-critical UI changes require component tests and browser or visual-regression coverage.

## 11. Testing requirements

Use the smallest relevant test command while developing and the complete required suite before opening a pull request.

Expected commands:

```bash
make validate
make test
make test-backend-all
make build
```

As Issue #29 is implemented, use:

```bash
make test-fast
make test-all
make test-e2e
make test-release
```

At minimum, a pull request must include tests for:

- the expected success path;
- invalid or missing input;
- boundary values;
- failure and retry behavior;
- any changed scientific calculation;
- any changed API contract;
- any judge-critical UI workflow.

Never weaken, delete, skip, or increase a tolerance in a failing test without explaining why the previous expectation was incorrect.

## 12. Code quality

### Python

- Follow the existing type hints and project structure.
- Keep API routes thin; place logic in services, simulation, analysis, or ML modules.
- Use project exceptions and the common error envelope.
- Use safe path helpers for all user-controlled or job-controlled paths.
- Avoid broad exception handling unless it is a worker boundary that must never crash the service.
- Run Ruff and pytest.

### TypeScript and React

- Keep API types aligned with the backend contract.
- Avoid `any` unless unavoidable and documented.
- Keep server state in TanStack Query and shared experiment state in the approved store.
- Do not duplicate API-fetch logic inside components.
- Provide accessible labels for non-text controls and visualizations.
- Run typecheck, ESLint, component tests, and the production build.

## 13. Commits

Use clear imperative commit messages:

```text
Fix precomputed structure lookup
Add paired stiffness result schema
Validate pulling curve units
Add light theme chart tokens
Document damage proxy limitations
```

Avoid messages such as `update`, `changes`, `final`, `fixed stuff`, or `new code`.

Do not include unrelated formatting or generated-file changes in the same commit.

## 14. Pull requests

Every pull request must:

- link its issue using `Closes #<number>` when appropriate;
- explain what changed and why;
- list scientific or schema implications;
- describe how it was tested;
- include UI screenshots in Light and Dark modes when applicable;
- identify generated artifacts and their hashes;
- state whether existing precomputed results or models must be regenerated;
- pass all required CI checks;
- receive review from the owner of the affected workstream.

Recommended PR body:

```markdown
## Summary

## Related issue
Closes #

## What changed

## Scientific/data impact
- [ ] None
- [ ] Simulation behavior
- [ ] Analysis formula
- [ ] Dataset/schema
- [ ] ML model
- [ ] User-facing scientific claim

## Testing

## Screenshots

## Reproducibility/artifacts

## Checklist
- [ ] Acceptance criteria completed
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No secrets or runtime artifacts committed
- [ ] Scientific limitations remain accurate
```

## 15. Review ownership

Until a formal `CODEOWNERS` file is introduced, request review from the relevant workstream:

- simulation changes: simulation owner;
- dataset or ML changes: ML/data owner;
- API or security changes: backend owner;
- dashboard and visualization changes: frontend owner;
- scientific claims: project lead plus the relevant simulation/ML owner.

Cross-cutting changes require review from every affected workstream.

## 16. Files that must not be committed

Do not commit:

- `.env` files or credentials;
- virtual environments;
- `node_modules/`;
- runtime job directories;
- user-uploaded structures;
- unrestricted logs;
- large raw trajectories;
- temporary notebooks or checkpoint files;
- local IDE settings unless intentionally shared;
- regenerated model/precomputed artifacts without provenance.

Check `git status` and inspect the full diff before every commit.

## 17. Security

- Treat uploaded PDBs, filenames, IDs, and report paths as untrusted input.
- Never construct filesystem paths without the confinement helpers.
- Never expose the local simulation API publicly without the approved shared-demo security mode.
- Do not print tokens, environment variables, or personal filesystem paths in logs or issues.
- Report suspected credential exposure privately to the repository owner and rotate the credential immediately.

## 18. Definition of done

A contribution is done only when:

- the issue acceptance criteria are satisfied;
- implementation and error paths are tested;
- CI passes;
- documentation is accurate;
- scientific meaning and units are explicit;
- artifacts are reproducible and versioned;
- no synthetic data contaminates the real dataset;
- the pull request has the required review;
- the judge/demo workflow still works.

Merging code is not the definition of success. A reproducible, tested, scientifically honest result is.
