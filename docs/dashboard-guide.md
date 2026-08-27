# Dashboard guide

Seven pages. Every one has explicit loading, empty, error and success states.

## Landing — `/`

Outside the app shell so it can use a full-bleed hero.

- Hero with the tagline and an honest summary of the three capabilities.
- Status chips: 5 approved proteins, ML degradation estimation, OpenMM rapid
  simulation, interactive molecular analysis, plus a live backend-readiness chip.
- Five-step workflow strip.
- Three capability cards, each listing its own limitations rather than only its
  features.
- The scientific-scope notice.

The starfield is a canvas that pauses when the tab is hidden and stops entirely
under `prefers-reduced-motion`, so it never competes with the protein for
attention or burns CPU while a simulation runs.

## Dashboard — `/dashboard`

Four stat cards: approved proteins, completed simulations, model status,
simulation-engine status. Each hover-explains itself; the model card reports
whether the bundle's SHA-256 and feature schema verified.

- **Quick-start scenarios** — one click sets the scenario and opens the
  workspace. Each is badged `ML + sim` or `sim only`, and the panel carries the
  provenance statement that these are demonstration presets rather than mission
  data.
- **Recent experiments** — click through to results (completed) or the monitor
  (running). Shows both the ML estimate and the simulation proxy per run.
- **Approved proteins** — comparison cards with the train/held-out badge.
- **System readiness** — every subsystem with its detail line, and for anything
  not ready, the exact command to fix it.

## Experiment workspace — `/experiment`

Three columns filling the viewport height, each scrolling independently, so the
3D viewport needs no page scrolling at 1366×768.

### Left — configuration

- **Protein selector** with train/held-out badges. The badge is the most
  important thing on the panel: a `train` protein will look optimistically
  accurate.
- **PDB upload** (8 MiB cap), validated server-side before anything is stored.
  Uploaded structures are flagged as recomputed and therefore approximate.
- **Chain selector**, shown only when the structure has more than one chain.
- **Radiation environment** — scenario, dose, unit, duration. The dose block
  carries a *"not an ML input"* chip because the model has no dose feature.
- **Mechanical & thermal** — temperature (badged *"drives simulation"*, the one
  numeric input that genuinely reaches the engine), mechanical force (badged
  *"recorded only"*), preset and seed.
- **Validate** checks everything against the same bounds as the backend and
  lists every problem at once. **Reset** restores defaults.

Numeric inputs and selects blur on mouse wheel, so scrolling the panel cannot
silently change a value you set.

### Centre — molecular viewport

- Render modes: cartoon, surface, stick, sphere. Colour by chain, spectrum or
  element.
- Candidate residues highlighted, weighted by predicted degradation once an
  estimate exists — red for higher, cyan for lower.
- Zoom, reset view, PNG screenshot, full screen (Esc exits). Hovering a residue
  shows its identifier.
- Below the viewport, the **candidate residue table**: rank, residue, SASA,
  contacts, susceptibility, and once predicted, the per-residue estimate. A
  warning triangle marks residues outside the model's vocabulary.

### Right — prediction and summary

- **Prediction card.** The provenance label and *MVP model* badge come before any
  number. Then the risk gauge, whose bands are the quartiles of the model's own
  training distribution, with dashed ticks marking the observed output range.
- **How this number was built** — residues scored, how many entered the mean,
  their range and spread, and why the mean leans high.
- **Uncertainty** — states plainly that confidence is unavailable and why, then
  offers held-out error as a separate, clearly-labelled thing.
- **What the model keys on** — feature importances, which make the
  dose-versus-scenario point concrete.
- **Experiment summary** — split into *consumed by the ML model* and *simulation
  & provenance only*.
- **Run rapid simulation** is disabled until the prediction completes (unless the
  scenario has no ML support), and while another job is running.

## Simulation monitor — `/simulation/:jobId`

- **Progress** — status, current stage, overall percentage, exact step counts,
  elapsed time, live temperature and potential energy. All from backend job
  state; nothing is interpolated client-side.
- **Stage timeline** — the eight stages with pending/active/done/failed/skipped
  states.
- **Console** — the worker log, colour-coded, autoscrolling while you are at the
  bottom and releasing when you scroll up to read. Full log downloadable.
- **Controls** — cancel (with confirmation explaining the job will be marked
  cancelled, not completed), open results, or on failure the error code, message
  and a **Retry with safe preset** button plus the precomputed-fallback offer.
- **Reproducibility** — everything needed to repeat the run, including the
  resolved platform and whether it is bit-reproducible.

Polling runs every ~1.2 s and stops automatically when the job reaches a terminal
state. Navigating away does not stop the run; return here or open it from
History.

## Results laboratory — `/results/:jobId`

- **Metrics grid** — eight tiles, each with a plain-language tooltip.
- **Structure comparison** — side by side, overlay (final in translucent violet
  over the original in cyan) or final only. The caption notes the visible
  difference is thermal motion, not radiation damage.
- **ML prediction vs simulation** — both figures, their difference, an agreement
  band, the proxy's full formula, a per-term contribution table, and the
  interpretation limits.
- **Trajectory analysis** — RMSD, radius of gyration, per-residue RMSF,
  potential energy, temperature. Every chart's tooltip explains what the metric
  means, what a normal curve looks like and what would be concerning.
- **Structural stability** — verdict, explanation, threshold note, and the
  highest-mobility residues.
- **Experiment metadata and reproducibility.**
- **Exports** — JSON and CSV reports, plus final/topology structures, the
  trajectory and the log. Artifacts that were not produced are shown disabled and
  labelled *not produced* rather than hidden.

`/results/precomputed/:pdbId` shows a bundled fallback, labelled *Precomputed
OpenMM Result* with a notice as the first thing on the page.

For a minimisation-only run, trajectory metrics render as *Not available* with
an explanation rather than being estimated.

## Compare — `/compare/:jobIdA/:jobIdB`

- Two selectors over completed runs.
- A prominent warning when the presets differ, because RMSD grows with
  trajectory length and the comparison is then not like-for-like.
- Run header cards, a metric difference table with a per-metric winner, a
  stability ranking, and two synchronised charts.
- Interpretation limits: a ranking says which run drifted less under these
  settings, not which protein is more radiation-tolerant.

Reachable from History by selecting two completed runs.

## History — `/history`

Read from the job directories on disk, so records survive a backend restart.

Filter by status; select two completed runs to compare; per row, view results,
monitor a running job, or delete with confirmation. Shows both the ML estimate
and the simulation proxy.

A directory with an unreadable `status.json` is *shown* as a failed job rather
than hidden.

## Methodology — `/methodology`

The judge-facing page. Collapsible sections covering the problem, an inline
architecture diagram, what the ML model predicts (including the four properties
that shape the whole interface), dataset provenance and the recovered formulas,
what OpenMM simulates and the radiation disclaimer, a prediction-versus-simulation
comparison table, the proxy definition, and future scope.

It ends with a red panel: **What this MVP does not claim** — ten items.

---

## Design system

Near-black navy ground (`#050816`), layered opaque surfaces, fine borders, and
restrained cyan/violet illumination. Translucency is reserved for accents and
never used behind body text, so contrast stays predictable.

Monospace is used only for experiment ids, parameters, metrics and logs — the
places where character alignment carries meaning.

Optimised for 1366×768 and 1920×1080, usable on tablets. Wide tables and
diagrams scroll inside their own containers; the page body never scrolls
horizontally.

Accessibility: visible focus rings on every interactive element, tooltips
reachable by keyboard and not mouse-only, `aria-label`s on icon-only controls,
`role="progressbar"` with live values, `role="log"` on the console, and full
`prefers-reduced-motion` support.
