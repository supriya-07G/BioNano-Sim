# Simulation methodology

## 1. What is actually simulated

Real molecular dynamics, using OpenMM 8.6:

| Component | Choice |
| --- | --- |
| Force field | `amber14-all.xml` |
| Solvent | `implicit/gbn2.xml` (GBn2 generalised Born) |
| Nonbonded method | `CutoffNonPeriodic`, 1.2 nm cutoff |
| Constraints | `HBonds` |
| Integrator | `LangevinMiddleIntegrator` |
| Friction | 1.0 ps⁻¹ |
| Timestep | 2.0 fs |
| Centre-of-mass motion | removed |
| Platform | auto-selected (CUDA → HIP → OpenCL → CPU → Reference) |

Hydrogens are added by OpenMM's own `Modeller` so they match force-field
expectations rather than whatever the depositor used. The integrator seed and
the initial-velocity seed are both set from the request's `random_seed`.

## 2. What is *not* simulated

**Standard OpenMM does not model ionising radiation.** There is no particle
transport, no track structure, no energy deposition, no radiolysis, no radical
chemistry and no covalent bond scission.

The dose, dose unit, particle group and exposure duration you set are recorded
in `request.json` and `reproducibility`, and every job whose dose is non-zero
carries this warning:

> A dose of *X* Gy was recorded for provenance. Standard OpenMM does not model
> ionising radiation: no particle track, energy deposition or bond scission is
> simulated. The trajectory reflects thermal dynamics at the requested
> temperature only.

Radiation reaches COSMORA's output **only** through the ML model's
categorical scenario feature — and that model was fitted on synthetic proxy
labels. Nothing in the physics path is radiation-aware.

Similarly, `mechanical_force_pn` is recorded but **no external pulling force is
applied**. Steered molecular dynamics is future scope, and a non-zero value
produces its own warning.

### The project's original radiation script

`legacy/simulate_radiation_damage.py` implemented radiation damage as
probabilistic residue deletion (LEO 5 %, deep space 15 %, solar flare 30 %
chance per residue). That is a **structural ablation**, not radiation physics:
it removes whole residues from the coordinate file rather than depositing energy
or breaking specific bonds. It is preserved for provenance but is not wired into
the simulation path, because presenting deleted residues as radiation damage
would misrepresent what happened.

## 3. Preparation pipeline

`app/simulation/preparation.py`, in order:

1. Parse with BioPython; take **model 1** only (NMR files carry many).
2. Keep the requested chain; drop all others, so SASA and dynamics do not depend
   on which other chains happen to be in the file.
3. Drop waters, ions and crystallisation additives (`HOH`, `SO4`, `GOL`, …).
4. Drop non-standard residues — amber14 has no template for them.
5. Drop residues with **no Cα atom**. Incomplete residues break force-field
   templates; this is the same rule that excludes 1TEN `A:802`, an arginine
   carrying only C and O.
6. Keep altloc `" "` or `"A"` only.
7. Strip hydrogens, then let OpenMM's `Modeller.addHydrogens` re-add them.
8. Write `prepared.pdb` (heavy atoms) and, after hydrogen addition,
   `topology.pdb` — the exact simulated system.

> `prepared.pdb` and `topology.pdb` differ in atom count (for 1UBQ: 602 vs
> 1231). **`topology.pdb` is the correct topology to pair with
> `trajectory.dcd`.** Using `prepared.pdb` will fail to load in MDTraj, VMD or
> PyMOL.

## 4. Presets

| Preset | Minimise | Equilibrate | Production | Simulated time | Typical wall clock |
| --- | --- | --- | --- | --- | --- |
| `rapid_demo` *(default)* | 500 | 1,000 | 5,000 | 12.0 ps | ~20 s GPU / 80–120 s CPU |
| `extended_demo` | 1,000 | 2,000 | 20,000 | 44.0 ps | ~60–90 s GPU / 5–8 min CPU |
| `minimisation_only` | 1,000 | 0 | 0 | 0 ps | < 15 s |

`minimisation_only` is the safe-retry preset offered when a run fails: it skips
dynamics entirely, which succeeds for structures that cannot equilibrate. It
produces no trajectory, so RMSD/RMSF/Rg and the degradation proxy are reported
as **unavailable** rather than estimated.

### Why a 1.2 nm cutoff

Measured on a 1,231-atom system (1UBQ with hydrogens), CPU platform:

| Configuration | Speed | 6,000 steps |
| --- | --- | --- |
| GBn2, no cutoff | 3.4 steps/s | ~29 min |
| GBn2, 1.2 nm cutoff | 28.8 steps/s | ~3.5 min |
| Vacuum (no solvent) | 707 steps/s | ~7 s |

Uncut GBn2 computes Born radii over all atom pairs and is infeasible for a live
demonstration. The cutoff is standard practice for implicit solvent, and it does
neglect long-range electrostatics — which is why it is declared in the preset,
echoed in every result payload, and listed in the preset's limitations.

### Why platform auto-selection

Same system, GBn2 with cutoff:

| Platform | Speed | 6,000 steps |
| --- | --- | --- |
| CPU, 1 thread | 11.5 steps/s | ~8.7 min |
| CPU, 4 threads | 31.5 steps/s | ~3.2 min |
| CPU, 16 threads | 71.1 steps/s | ~85 s |
| OpenCL | 354.4 steps/s | **~17 s** |

Auto-selection walks CUDA → HIP → OpenCL → CPU → Reference. The trade-off:
**GPU platforms are not bit-reproducible.** The platform actually used is
recorded in `reproducibility.platform_resolved`, alongside
`bitwise_reproducible: true|false`. Requesting `CPU` explicitly gives an exactly
repeatable trajectory for a fixed seed.

You can see this in practice: two runs of 1UBQ with identical settings and seed
42 on OpenCL gave final RMSD 0.1442 nm and 0.1360 nm.

## 5. Progress reporting

Progress comes from the integrator's own step counter, never a timer. The
production loop advances in 250-step chunks and publishes after each:

- `steps_completed` / `steps_total` — exact integration counts
- `potential_energy_kj_mol` — read from the OpenMM context
- `temperature_kelvin` — computed as `2·KE / (dof · k_B)`, where
  `dof = 3·N_atoms − N_constraints − 3`

If a run stalls, the progress bar stalls with it. That is deliberate: a bar that
keeps moving while nothing happens is worse than no bar.

Stage weights for the overall percentage are declared in
`app/simulation/job_manager.py` and sum to 1.0. Within equilibration and
production the fraction is the real step ratio, so the bar tracks actual work
rather than interpolating.

## 6. Analysis

All metrics are computed from the real trajectory. MDTraj is used when
importable; otherwise a self-contained DCD reader in `app/simulation/engine.py`
handles OpenMM's fixed-format 32-bit little-endian DCD. Both paths convert to
nanometres, so downstream numbers are identical either way, and the reader used
is recorded in `metrics.trajectory_reader`.

| Metric | Definition | File |
| --- | --- | --- |
| RMSD | Cα RMSD vs frame 0, Kabsch superposition with a reflection guard | `analysis/rmsd.csv` |
| RMSF | Per-Cα fluctuation about the mean structure, after iterative superposition | `analysis/rmsf.csv` |
| Rg | Unweighted radius of gyration of the Cα set | `analysis/radius_gyration.csv` |
| Energies, temperature | Parsed from OpenMM's `StateDataReporter` CSV | `analysis/energy.csv` |

RMSF superposes onto the mean structure rather than frame 0, so it reports
internal flexibility rather than whole-molecule tumbling.

**Sanity check that the physics is real:** for 1UBQ the highest-RMSF residues
come out as A:76 (0.370 nm), A:75 (0.233 nm), A:74 (0.147 nm) — the C-terminal
tail, which is exactly what the experimental ubiquitin literature reports as the
most flexible region.

## 7. The degradation proxy

The single most easily misread number in the application.

```
degradation_proxy_percent = 100 · clip(
      0.50 · min(1, final_rmsd_nm / 0.60)
    + 0.20 · min(1, |Rg_final − Rg_initial| / Rg_initial / 0.25)
    + 0.30 · min(1, mean_rmsf_nm / 0.35)
    , 0, 1)
```

### What it is

A bounded, monotone score combining three trajectory observables, each
normalised against a reference scale. It answers *"how far did this structure
drift from its starting conformation, relative to a drift scale we chose"*.

### What it is not

- Not a measured degradation percentage.
- Not a radiation-damage yield.
- Not comparable to any experimental assay.

### The reference scales are engineering constants

0.60 nm RMSD, 25 % ΔRg and 0.35 nm RMSF are **not physical constants**. They
were chosen so a well-behaved short implicit-solvent run of a small stable domain
lands in the low tens of percent and gross unfolding approaches 100 %. Changing
them changes the number without changing the underlying physics. They are
declared in `app/analysis/degradation.py`, echoed in every API response under
`degradation_proxy.reference_scales`, and shown in the UI with each term's
contribution.

### Thermal floor

A short run at 300 K produces non-zero drift from thermal motion alone. A
typical 1UBQ Rapid Demo scores 16–18 % with no radiation modelled whatsoever.
**Use the `BASELINE_NO_RADIATION` preset as a control** to see that floor before
attributing drift to anything else.

### Comparing against the ML estimate

The results page shows both figures, their difference in percentage points, and
an agreement band (close ≤ 10 pp, moderate ≤ 25 pp, divergent > 25 pp — bands
are presentational). The interpretation shipped with every response:

> These two numbers are different quantities. The ML value is a mock-model
> estimate of per-residue side-chain-loss degradation, aggregated over ranked
> candidate residues. The simulation value is a structural-drift score computed
> from the trajectory. Their difference measures disagreement between two
> proxies; it does NOT indicate which is closer to physical reality, and neither
> has been validated against experiment.

A typical 1UBQ run gives ML ≈ 49.5 % against a proxy ≈ 18 %, i.e. "divergent".
That is the expected outcome for two unrelated proxies on different scales, and
the UI says so rather than implying one is wrong.

## 8. Stability verdict

| Final Cα RMSD | Verdict |
| --- | --- |
| < 0.15 nm | `stable` |
| 0.15 – 0.30 nm | `mildly_perturbed` |
| 0.30 – 0.60 nm | `perturbed` |
| ≥ 0.60 nm | `strongly_perturbed` |

Presentational heuristics for this MVP, not published stability criteria. The
threshold note travels with the verdict in every response.

## 9. Safety limits

| Limit | Default | Rationale |
| --- | --- | --- |
| Concurrent jobs | 1 | OpenMM is device-bound; two concurrent runs on one device are slower than two in sequence |
| Production steps | 50,000 | Keeps a local run bounded |
| Minimisation steps | 5,000 | As above |
| Wall clock | 900 s | Backstop against a pathological system |
| Chain residues | 4 – 400 | Below 4 nothing meaningful can be built; above 400 a demo run stops being interactive |
| Temperature | 100 – 500 K | Below ~100 K the implicit-solvent model and HBonds constraints are not meaningful; above ~500 K a 2 fs timestep is unstable |
| Upload size | 8 MiB | With 100,000 atom and 2,000 residue caps |

## 10. Job directory

```
runtime/jobs/<job_id>/
├── request.json        submitted configuration, preset and scenario snapshot
├── status.json         atomically rewritten; the UI polls this
├── input.pdb           the structure as submitted (snapshotted at submit time)
├── prepared.pdb        cleaned, single chain, heavy atoms only
├── topology.pdb        the exact simulated system, hydrogens included
├── final.pdb           coordinates at the end of the run
├── trajectory.dcd      trajectory (pair with topology.pdb)
├── state.csv           OpenMM StateDataReporter output
├── metrics.json        every derived metric and series
├── analysis/
│   ├── rmsd.csv
│   ├── rmsf.csv
│   ├── radius_gyration.csv
│   └── energy.csv
└── simulation.log      full worker log with stage transitions and exceptions
```

`status.json` is written via temp file + `os.replace`, which is atomic on
Windows and POSIX. Without that, a UI poll landing mid-write would see a
truncated file.

**A failed job is never marked completed.** Failure and cancellation go through
a dedicated path that sets `failed`/`cancelled`, records `error_code` and
`error_message`, marks the active stage failed and remaining stages skipped, and
attaches a retry hint. `GET /simulations/{job_id}/results` returns 404 for any
non-completed job.

## 11. Reproducing a run

Every job records what is needed to repeat it: structure identity and chain,
scenario, preset, force field, solvent model, constraints, cutoff, integrator,
friction, timestep, all three step counts, temperature, seed, resolved platform,
and the versions of Python, OpenMM, MDTraj, NumPy and BioPython.

```bash
python scripts/run_demo_simulation.py --pdb-id 1UBQ --seed 42
```

For a bit-reproducible trajectory, select the `CPU` platform: GPU platforms
reorder floating-point reductions and will not reproduce exactly.
