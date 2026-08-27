# Scientific scope

## 1. The question BioNano-Sim addresses

Deep-space missions expose hardware to galactic cosmic rays and solar energetic
particles for months at a time. If protein-based components are ever to serve as
nanoscale mechanical elements out there — molecular springs, switches, sensors,
structural members — someone has to be able to ask *which candidate domains hold
up, and under what conditions*, long before a wet-lab campaign is affordable.

BioNano-Sim is a computational triage bench for that question. It pairs a fast
machine-learning estimate with a real physics simulation, keeps the two
rigorously labelled, and exports a reproducible record of both.

The value is not that either number is authoritative — neither is — but that the
pipeline is honest enough to build on.

## 2. What BioNano-Sim is not about

**Proteins are not a silicon replacement.** Proteins and silicon are separate
technologies with different failure modes, operating envelopes and fabrication
routes. BioNano-Sim makes no claim about protein-based computation, logic or
electronics.

The scope is narrower and more defensible: whether selected proteins could act
as nanoscale **mechanical** components in radiation-exposed environments. That
framing is why the five approved proteins are chosen for mechanical character —
a spring (titin I27), an elastic linker (spectrin), a load-bearing β-sandwich
(fibronectin III), a compact switch body (ubiquitin) and a minimal stable module
(protein G B1) — rather than for any electronic property.

## 3. The three capabilities, and their standing

| Capability | Status | Basis |
| --- | --- | --- |
| **ML Prediction** | Not validated | Gradient-boosted regression on 450 rows of synthetic proxy labels |
| **Rapid OpenMM Simulation** | Method peer-reviewed, this application of it not validated | Amber14 + GBn2, real integration, picosecond scale |
| **Simulation-derived degradation proxy** | Constructed by this application | Weighted combination of RMSD, ΔRg and RMSF against chosen reference scales |

Each carries its own label everywhere it appears. The result labels are fixed
strings held in one module so they cannot drift:

- `ML Prediction`
- `Rapid OpenMM Simulation`
- `Precomputed OpenMM Result`
- `Energy Minimisation Only`
- `Visualization Estimate`
- `Production Simulation — Future Scope`

## 4. What this MVP does not claim

1. **Not a validated prediction of protein degradation in space.** The model's
   training labels are `SYNTHETIC_PUBLIC_DATA_PROXY` — a proxy generated from
   public structural data, not measured degradation. Its declared approved use is
   `DASHBOARD_AND_API_INTEGRATION_TESTING_ONLY`.

2. **Not a simulation of ionising radiation.** Standard OpenMM integrates
   Newtonian dynamics on a classical force field. There is no particle
   transport, no track structure, no energy deposition, no radiolysis, no radical
   chemistry, no covalent bond scission. The dose you set is recorded as
   provenance and warned about; the trajectory reflects thermal dynamics at the
   requested temperature and nothing else.

3. **Not production-timescale molecular dynamics.** Runs are 12–44 ps. Real
   degradation processes act over seconds to years — nine to sixteen orders of
   magnitude longer. Nothing here extrapolates to mission timescales.

4. **The degradation proxy is not measured damage.** It is a structural-drift
   score this application computes. Its reference scales (0.60 nm RMSD, 25 % ΔRg,
   0.35 nm RMSF) are engineering constants chosen for the MVP, not physical
   constants; changing them changes the number without changing the physics.

5. **Agreement between ML and simulation validates neither.** They are different
   quantities on different scales, built from different inputs. Their difference
   measures disagreement between two proxies and does not indicate which is
   closer to reality.

6. **The scenario values are not authoritative.** Dose, duration and temperature
   defaults are configurable demonstration presets, marked
   `CONFIGURABLE_DEMONSTRATION_PRESETS` in the data file. They are **not** NASA,
   ESA or ICRP reference environments and must not be cited as such.

7. **Model accuracy figures describe proxy agreement, not physical accuracy.**
   R² = 0.844 on the held-out test protein means the model learned the proxy's
   generating process well. It says nothing about physical reality.

8. **No confidence interval exists.** The bundle exposes no calibrated
   uncertainty, so `confidence` is `null`. The held-out MAE values shown in the
   UI are retrospective dataset-level metrics on two proteins, explicitly not
   per-prediction error bars.

9. **Generalisation beyond small single-domain proteins is unverified.**
   Training covered five proteins of 56–107 residues.

10. **A visualization is never a simulation.** No animation in this application
    is generated from ML output and presented as a trajectory. The structure
    viewers show either the submitted coordinates or real frames from a real run.

## 5. Honest signals built into the interface

Rather than confining caveats to this document, the application surfaces them
where a number is read:

- **Held-out badges.** The protein selector marks each protein `train` or
  `held-out`. 1UBQ and 1TEN are the only honest generalisation cases; the other
  three will look optimistically accurate because the model was fitted on them.
- **"not an ML input" chips.** The dose, duration and force controls are labelled
  at the control itself, because the model has no such feature. A regression test
  asserts the estimate really is dose-invariant.
- **Out-of-vocabulary flags.** The residue table marks residues whose type the
  encoder never saw, and those residues are excluded from the protein-level mean.
  This fires on the approved set: 1UBQ's rank-2 candidate is GLY.
- **Scenario refusal.** Requesting an ML estimate for the no-radiation or
  mechanical-only preset returns an error explaining that the scenario is outside
  the trained vocabulary, instead of extrapolating.
- **Aggregation disclosure.** The protein-level percentage always shows how it
  was built: how many residues were scored, how many entered the mean, their
  range and spread, and a note that the candidates are the most susceptible
  residues so the mean leans high.
- **Proxy breakdown.** The comparison panel prints the proxy formula and each
  term's contribution, so a reader can recompute the score by hand.
- **Precomputed labelling.** A fallback result is labelled `Precomputed OpenMM
  Result`, and the first thing the page renders is a notice that it is not a run
  performed on this machine.

## 6. Dataset provenance

| Artifact | Source | Licence / status |
| --- | --- | --- |
| PDB coordinates | RCSB PDB (`files.rcsb.org`) | CC0 1.0 Universal |
| `public_residue_features.csv` | Shipped with the model release | Derived from public structural data |
| `bionano_mock_experiments_v1.csv` | Shipped with the model release | `SYNTHETIC_PUBLIC_DATA_PROXY` labels |
| `bionano_mock_model_bundle.pkl` | Shipped with the model release | `MOCK_PUBLIC_DATA_BOOTSTRAP` |

The training CSVs, splits and evaluation reports are committed deliberately: they
are what makes the model's predictions reproducible and auditable.
`scripts/validate_model.py` re-derives the published metrics from them on every
run.

No dataset was fabricated for this project. Where a formula was needed but not
shipped, it was recovered from the data and the recovery documented with its
verification error — see [model-card.md §7](model-card.md). Where recovery
failed (`residue_sasa_norm`), that is stated with the measured correlation rather
than papered over.

## 7. Future scope

| Direction | What it needs |
| --- | --- |
| Real radiation-damage modelling | Couple a particle-transport code (Geant4, PHITS) to reactive or QM/MM dynamics so energy deposition and bond scission are actually simulated |
| Experimental validation | Real paired baseline and post-exposure stiffness measurements as training labels — the model's own stated replacement requirement |
| Explicit solvent, longer trajectories | TIP3P with particle-mesh Ewald on GPU, reaching hundreds of nanoseconds, so stability metrics become statistically meaningful |
| Steered molecular dynamics | Apply the mechanical force the interface currently only records, so force-extension behaviour can be measured — the natural test for a protein proposed as a spring |
| Calibrated uncertainty | Quantile regression or a conformal wrapper, so `confidence` stops being `null` |
| Broader coverage | All 20 amino acids in the vocabulary, and enough proteins that generalisation can be measured rather than hoped for |

## 8. How to talk about results

**Defensible:**

> "The MVP model estimates 49.5 % side-chain-loss degradation for ubiquitin's
> ten most susceptible residues under the deep-space GCR reference scenario. A
> 12 ps OpenMM run of the same structure gives a structural-drift proxy of 18 %.
> Neither is experimentally validated, and the two are different quantities."

**Not defensible:**

> "Ubiquitin degrades 49.5 % in deep space." — The model is not validated, the
> figure covers only the most susceptible residues, and no radiation was
> simulated.

> "The simulation confirms the prediction." — The simulation models no
> radiation; the two numbers are unrelated proxies.

> "Radiation damage was simulated at 0.5 Gy." — No radiation physics ran. The
> dose is recorded provenance only.
