## What changed

<!-- One or two sentences. -->

## Why

<!-- The problem this solves. Link an issue if there is one. -->

## Verification

- [ ] `python scripts/validate_environment.py` — no blocking problems
- [ ] `python scripts/validate_model.py` — all checks pass
- [ ] `cd backend && python -m pytest -q` — all tests pass
- [ ] `cd frontend && npm run typecheck && npm run lint && npm run build`
- [ ] Verified in a browser at 1366×768 with no console errors

<!-- Paste relevant output, especially if a number changed. -->

## Scientific integrity checklist

Tick every item that applies, or state why it does not.

- [ ] No fabricated dataset, accuracy figure or confidence value was introduced.
- [ ] Every new result carries its provenance label (`ML Prediction`,
      `Rapid OpenMM Simulation`, `Precomputed OpenMM Result`, …).
- [ ] No visualization is presented as a simulation, and no precomputed output
      as a live run.
- [ ] Nothing implies that standard OpenMM models ionising radiation.
- [ ] Any new derived metric documents its formula and states whether its
      constants are physical or chosen.
- [ ] If a model input changed, `models/feature_schema.json` was regenerated and
      `docs/model-card.md` updated.
- [ ] If a limitation changed, `docs/scientific-scope.md` and the Methodology
      page were updated.

## Anything a reviewer should look at closely

<!-- Trade-offs, or a decision you are unsure about. -->
