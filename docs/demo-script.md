# SIH demonstration script

**Total: 7 minutes.** Timings assume a GPU platform (Rapid Demo ≈ 20 s). On
CPU-only hardware the run takes 80–120 s — use the "while it runs" section to
fill that, or switch to `Minimisation only` for a sub-15 s run.

## Before you start

```bash
python scripts/validate_environment.py   # expect: No blocking problems found
python scripts/validate_model.py         # expect: 25/25 checks passed
```

Then start both servers and confirm the topbar shows green **Model** and
**OpenMM** chips.

**Pre-warm the run.** Execute one Rapid Demo before the presentation:

```bash
python scripts/run_demo_simulation.py
```

This loads OpenMM's kernels and populates History so the Compare page has
material. Optionally leave the results page open in a second tab.

**Have the fallback ready.** `/results/precomputed/1UBQ` works even if the live
engine fails. It is labelled *Precomputed OpenMM Result*.

---

## 0:00 — Landing page (40 s)

Open <http://localhost:5173>.

> "BioNano-Sim asks a narrow, answerable question: could specific protein
> domains work as nanoscale *mechanical* components — springs, switches,
> structural members — in the radiation environment of deep space.
>
> It is not a claim that proteins replace silicon. Those are separate
> technologies. What we do is combine three things and keep them strictly
> separated: a machine-learning degradation estimate, a real molecular-dynamics
> simulation, and structural analysis of the resulting trajectory."

Point at the three capability cards.

> "Each has its own provenance label. That separation is the point of the
> project: a prediction is never presented as physics, and physics is never
> presented as measurement."

Click **Launch Simulation Lab**.

---

## 0:40 — Experiment workspace (80 s)

> "Three panels: configuration, the molecular viewport, and the prediction."

**Left panel — the held-out badge.**

> "Five approved proteins. Notice the badges: 1UBQ and 1TEN say *held-out*, the
> others say *train*. That matters — a protein the model was fitted on will look
> more accurate than it is. We surface it at the point of selection rather than
> burying it in a footnote. 1UBQ is preselected because it is held out and it is
> the fastest to simulate."

**Radiation controls — the honest bit.**

Scroll to the dose field and point at the grey **"not an ML input"** chip.

> "This is the most important thing on the screen. We inspected the model
> bundle, and its fourteen features contain no dose, no duration, no
> temperature, no force. Radiation reaches the model *only* as a categorical
> scenario. So we label the control itself — moving this slider cannot change
> the estimate, and there is a regression test in the suite asserting exactly
> that."

Hover the tooltip to show the full explanation.

**Centre panel — the structure.**

> "Real coordinates from the PDB, rendered live. The orange spheres are the ten
> candidate residues the model will score — the most exposed, least packed,
> most chemically susceptible ones."

Switch **Cartoon → Surface**, then back.

**Right panel.**

> "Configuration is split into what the model consumes and what is provenance
> only. No ambiguity about which inputs matter."

---

## 2:00 — ML prediction (70 s)

Click **Estimate degradation**.

> "49.5 %, risk *moderate*."

**The aggregation.** Point at "How this number was built".

> "Ten residues scored, but only nine entered the mean. The model's target is
> *per residue* — a protein-level percentage is something this application
> constructs, so we show exactly how: the range, the spread, and a note that
> because these are the most susceptible residues, the mean leans high relative
> to the whole chain."

**Why one was excluded.** Scroll to the residue table and point at the warning
triangle on the GLY row.

> "The encoder was fitted on only fourteen of the twenty amino acids. 1UBQ's
> second-ranked candidate is glycine, which it never saw. And here is the
> problem we had to solve: the encoder was configured with
> `handle_unknown='ignore'`, so an unseen residue becomes an all-zero block and
> the model *still returns a confident-looking number*. We measured it — a known
> residue gives 60.5277 %, an unknown one gives 60.5295 %. A 0.002 point
> difference. Undetectable from the output.
>
> So we check every category against the encoder's own vocabulary before
> predicting, flag the affected residues, and exclude them from the headline
> figure."

**Confidence.**

> "Confidence is *null*, not a number. The bundle has no calibrated uncertainty,
> so we refuse to invent one. What we offer instead is the held-out error — 4.1
> percentage points MAE on unseen ubiquitin — clearly labelled as a
> retrospective dataset-level metric, not an error bar for this estimate."

Optionally expand **Limitations of this estimate** to show the five warnings.

---

## 3:10 — Simulation (60 s, or fill on CPU)

Click **Run rapid simulation**.

> "This is a real OpenMM run. Amber14 force field, GBn2 implicit solvent, a
> Langevin integrator, fixed seed."

Point at the step counter.

> "Progress comes from the integrator's own step counter, not a timer. If the
> run stalls, this bar stalls. Temperature is computed from the system's kinetic
> energy — you can watch it climb from zero through equilibration and settle
> around the 300 K setpoint. Potential energy dropped sharply during
> minimisation and is now fluctuating on a plateau."

**While it runs:**

> "And here is what we are *not* doing. Standard OpenMM does not model ionising
> radiation. No particle transport, no energy deposition, no radical chemistry,
> no bond scission. The dose we set is recorded as provenance and appears in the
> job warnings, but this trajectory is thermal dynamics at 300 K. Claiming
> otherwise would be the easiest way to make this project look better and be
> worthless."

Optionally open the log panel to show real stage transitions.

---

## 4:10 — Results (100 s)

Click **Open results**.

**Metrics.**

> "Every number here comes from the real trajectory. Final backbone RMSD 0.14
> nanometres — small, this domain stayed folded. Radius of gyration changed under
> two percent, so it stayed compact. 60 frames over 12 picoseconds."

**RMSF — the credibility check.**

Scroll to the per-residue RMSF chart.

> "This is where you can tell the physics is real rather than decorative. The
> peak is at residues 74, 75, 76 — ubiquitin's C-terminal tail. That is exactly
> what the experimental literature reports as its most flexible region. We did
> not put that there; it fell out of the integration."

**Structure comparison.** Switch to **Overlay**.

> "Original in cyan, final frame in violet. The visible difference is 12
> picoseconds of thermal motion, and the caption says so."

**The comparison panel.**

> "Now the part that matters most. ML estimate 49.5 %. Simulation drift proxy
> 18 %. Difference 31 points — labelled *divergent*.
>
> We could have hidden that. Instead: these are different quantities on
> different scales. One is a mock model's guess at side-chain loss; the other is
> a structural-drift score we compute ourselves. We publish the proxy's formula
> and each term's contribution right here, so you can recompute it by hand. And
> the reference scales in it are engineering constants we chose — not physical
> constants. Change them and the number changes without the physics changing.
>
> The difference measures disagreement between two proxies. It does not tell you
> which is closer to reality, because neither has been validated against
> experiment."

**Exports.** Click the JSON report.

> "Thirty-two kilobytes: the scientific notice, protein and scenario provenance,
> the prediction with its caveats, every metric and series, per-residue RMSF, the
> comparison, and full reproducibility metadata — force field, seed, step
> counts, resolved platform, library versions. The CSV is the same content
> flattened for a spreadsheet."

---

## 5:50 — Compare and methodology (50 s)

Go to **Compare**, select two completed runs.

> "Same protein, same settings, same seed — and the final RMSD differs slightly.
> That is because the run used a GPU platform, which is not bit-reproducible.
> Rather than hide it, each job records the platform it actually used and a
> `bitwise_reproducible` flag. Choose the CPU platform and you get an exactly
> repeatable trajectory."

Go to **Methodology** and scroll to the red panel.

> "*What this MVP does not claim.* Ten items. Not a validated prediction. Not a
> simulation of radiation. Not production timescales. The proxy is not measured
> damage. Agreement validates neither. The scenario doses are demonstration
> presets, not NASA values.
>
> We wrote this section first and built the interface to be consistent with it."

---

## 6:40 — Close (20 s)

> "What is genuinely working: real ML inference from a real bundle that we
> verified reproduces its own published metrics to six decimal places. Real
> OpenMM molecular dynamics with backend-driven progress. Real trajectory
> analysis. Full exports and reproducibility metadata.
>
> What is honestly labelled as not yet real: radiation physics, experimental
> validation, and production timescales. The next step is coupling a
> particle-transport code to reactive dynamics, and retraining on real paired
> stiffness measurements — which is the model's own stated replacement
> requirement.
>
> The reason to trust the second list is that we were willing to write it down."

---

## Contingencies

| Problem | Response |
| --- | --- |
| Simulation fails | The monitor shows the specific error code, message, and a **Retry with safe preset** button, plus an offer to open the precomputed fallback. Say: "the failure path is designed too — a failed job is never recorded as completed." |
| Run too slow | Switch the preset to **Minimisation only** (< 15 s). It reports no trajectory metrics rather than estimating them — itself a good point. |
| Backend not running | The topbar shows *Backend unreachable* and every page shows the exact uvicorn command. |
| Model unavailable | Readiness shows it red with the remediation command; simulation still works. Good demonstration of graceful degradation. |
| Viewer blank | The rest of the app works; the viewer reports the missing vendor file inline. Run `python scripts/fetch_viewer.py`. |
| Asked about accuracy | "R² of 0.844 on the held-out protein — but that is agreement with *synthetic proxy labels*. It means the model learned the proxy's generating process. It says nothing about physical reality, and the model card says so." |
| Asked "is this useful then?" | "As a triage bench and an honest pipeline, yes. Swap the bundle for one trained on real paired measurements and every number becomes meaningful — the loader verifies the new schema automatically. The infrastructure is the deliverable; the model is a placeholder that says so." |

## Numbers worth memorising

| Fact | Value |
| --- | --- |
| ML estimate, 1UBQ / GCR | 49.52 % (moderate) |
| Drift proxy, 1UBQ Rapid Demo | 16–18 % |
| Held-out MAE | 4.11 pp (1UBQ), 2.26 pp (1TEN) |
| Reproduction of shipped predictions | max diff 1.9e-06 |
| Rapid Demo | 6,000 steps, 12 ps, 60 frames |
| Runtime | ~20 s GPU, 80–120 s CPU |
| Vocabulary coverage | 14 of 20 amino acids |
| Encoder blind spot | known 60.5277 % vs unknown 60.5295 % |
| Backend tests | 100 passing |
| Highest-RMSF residues, 1UBQ | A:76, A:75, A:74 (the C-terminal tail) |
