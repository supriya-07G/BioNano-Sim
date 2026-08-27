import { useState } from 'react'
import {
  Ban,
  BookOpen,
  Boxes,
  ChevronDown,
  Cpu,
  Database,
  FlaskConical,
  Rocket,
  Sparkles,
} from 'lucide-react'

import { ScientificNotice } from '@/components/common/ScientificNotice'
import { PageHeader } from '@/components/layout/PageHeader'
import { ArchitectureDiagram } from '@/components/layout/ArchitectureDiagram'
import { cn } from '@/components/ui/cn'
import { useModelInfo, useScenarios } from '@/hooks/usePrediction'
import { usePresets } from '@/hooks/useSimulation'
import { fmtNumber } from '@/utils/formatters'

const NOT_CLAIMED = [
  'That proteins replace silicon electronics. Proteins and silicon are separate technologies; BioNano-Sim examines proteins as candidate nanoscale mechanical components only.',
  'That the ML degradation estimate is a validated prediction. Its training labels are a synthetic public-data proxy, not experimental measurements.',
  'That the simulation models ionising radiation. Standard OpenMM has no particle-track transport, no energy deposition, no radical chemistry and no bond scission.',
  'That the simulation reaches degradation timescales. Runs are picoseconds; real degradation acts over seconds to years.',
  'That the "degradation proxy" is measured damage. It is a bounded structural-drift score computed by this application from RMSD, radius of gyration and RMSF, with reference scales chosen for the MVP.',
  'That agreement between ML and simulation validates either. Both are proxies; their difference measures disagreement, not accuracy.',
  'That the scenario dose values are authoritative. They are configurable demonstration presets, not NASA, ESA or ICRP reference environments.',
  'That the model generalises beyond small single-domain proteins. It was trained on five proteins and 450 rows.',
]

export function MethodologyPage() {
  const model = useModelInfo()
  const presets = usePresets()
  const scenarios = useScenarios()

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 pb-16">
      <PageHeader
        title="Methodology and limitations"
        description="What BioNano-Sim computes, how each number is produced, and what it deliberately does not claim."
        badges={
          <span className="badge border-violet/40 bg-violet/10 text-violet">
            <BookOpen className="h-3 w-3" aria-hidden />
            Judge-facing
          </span>
        }
      />

      {/* --- Problem --------------------------------------------------- */}
      <Section
        icon={Rocket}
        title="What BioNano-Sim addresses"
        defaultOpen
      >
        <p>
          Deep-space missions expose hardware to galactic cosmic rays and solar
          particle events for months at a time. If protein-based components are ever
          to serve as nanoscale mechanical elements out there — molecular springs,
          switches, sensors, structural members — someone has to be able to ask{' '}
          <em>which candidate domains hold up, and under what conditions</em>, long
          before a wet-lab campaign is affordable.
        </p>
        <p>
          BioNano-Sim is a computational triage bench for that question. It pairs a
          fast machine-learning estimate with a real physics simulation, keeps the two
          rigorously labelled, and exports a reproducible record of both. The value is
          not that either number is authoritative — neither is — but that the pipeline
          is honest enough to build on.
        </p>
      </Section>

      {/* --- Architecture ---------------------------------------------- */}
      <Section icon={Boxes} title="Architecture" defaultOpen>
        <ArchitectureDiagram className="my-2" />
        <p>
          A React front end talks to a FastAPI backend over a versioned JSON API. The
          backend loads the ML bundle once at startup, serves the protein registry from
          local PDB files, and runs simulations in a background worker thread with job
          state persisted to disk. There is no database: job metadata and artifacts live
          under <code>runtime/jobs/&lt;job_id&gt;/</code>, which is what lets History be
          rebuilt after a restart.
        </p>
      </Section>

      {/* --- ML model --------------------------------------------------- */}
      <Section icon={Sparkles} title="What the ML model predicts">
        <p>
          The bundle is <strong>{model.data?.model_name ?? 'a bootstrap model'}</strong>{' '}
          version <code>{model.data?.model_version ?? '—'}</code>, status{' '}
          <code>{model.data?.scientific_status ?? '—'}</code>. It is a scikit-learn
          pipeline: a <code>ColumnTransformer</code> (median imputation for 8 numeric
          features, one-hot encoding for 6 categorical ones) feeding an XGBoost
          regressor, 33 transformed features in total.
        </p>

        <KeyValue
          rows={[
            ['Target', `${model.data?.target_column ?? '—'} (per residue)`],
            ['Label source', model.data?.label_source ?? '—'],
            [
              'Validation (unseen 1UBQ)',
              model.data?.validation_metrics
                ? `MAE ${fmtNumber(model.data.validation_metrics.mae, 2)} pp · RMSE ${fmtNumber(
                    model.data.validation_metrics.rmse,
                    2,
                  )} · R² ${fmtNumber(model.data.validation_metrics.r2, 3)}`
                : '—',
            ],
            [
              'Test (unseen 1TEN)',
              model.data?.test_metrics
                ? `MAE ${fmtNumber(model.data.test_metrics.mae, 2)} pp · RMSE ${fmtNumber(
                    model.data.test_metrics.rmse,
                    2,
                  )} · R² ${fmtNumber(model.data.test_metrics.r2, 3)}`
                : '—',
            ],
            ['Train proteins', (model.data?.train_proteins ?? []).join(', ') || '—'],
            ['Confidence', 'null — no calibrated uncertainty exists in the bundle'],
          ]}
        />

        <h4>Four properties that shape the whole interface</h4>
        <ol>
          <li>
            <strong>The target is per residue, not per protein.</strong> The model
            predicts side-chain-loss degradation for one ranked candidate residue.
            Every protein-level percentage in this application is an aggregation
            BioNano-Sim performs (the mean over the top candidates) and is labelled as
            such. Because those candidates are the <em>most</em> susceptible residues,
            that mean leans high relative to the whole chain.
          </li>
          <li>
            <strong>There is no dose input.</strong> The 14 features contain no dose,
            duration, temperature or force. Radiation reaches the model only through
            the categorical <code>scenario_id</code>, <code>radiation_class</code> and{' '}
            <code>environment</code> — which together carry roughly two thirds of the
            model&rsquo;s feature importance. Moving the dose slider cannot and does
            not change the estimate, and the UI says so at the control itself.
          </li>
          <li>
            <strong>Only three scenarios were ever trained.</strong>{' '}
            {(scenarios.data?.provenance.trained_scenarios ?? []).join(', ')}. The
            baseline-control and mechanical-only presets are outside the vocabulary
            entirely, so they are marked <code>ml_supported: false</code> and the API
            refuses to produce an estimate for them rather than extrapolating.
          </li>
          <li>
            <strong>Unknown categories fail silently in the encoder.</strong> The
            one-hot encoder was fitted with <code>handle_unknown=&apos;ignore&apos;</code>,
            so an unseen category becomes an all-zero block and the model still returns
            a confident-looking number. The <code>residue_type</code> vocabulary covers
            only 14 of 20 amino acids, so even approved proteins trip this — 1UBQ&rsquo;s
            rank-2 candidate is GLY and 1TEN has a PHE. BioNano-Sim detects unknown
            categories <em>before</em> predicting, flags the affected residues in the
            table, and excludes them from the headline mean.
          </li>
        </ol>
      </Section>

      {/* --- Provenance ------------------------------------------------- */}
      <Section icon={Database} title="Dataset provenance and preprocessing">
        <p>
          Structures come from RCSB PDB (CC0 1.0). Per-residue features come from{' '}
          <code>data/ml/data/public_residue_features.csv</code>, the exact table the
          model was fitted on, so approved proteins are featurised with zero
          recomputation error.
        </p>
        <p>
          Uploaded structures have no such table, so their features are recomputed. The
          generating code was not shipped with the dataset, so the formulas were
          recovered from the CSVs and verified against all five proteins:
        </p>
        <ul>
          <li>
            <code>hydrophobic_fraction</code> = fraction in {'{'}A, F, I, L, M, V, W, Y
            {'}'} — exact for all five. Note it excludes C and G, which the obvious
            guess includes.
          </li>
          <li>
            <code>charged_fraction</code> = fraction in {'{'}D, E, K, R{'}'} —
            histidine excluded.
          </li>
          <li>
            <code>residue_contact_count</code> = Cα neighbours within 8.0 Å, self
            excluded. Reproduces the reference table <em>exactly</em> (56/56 for 1PGA,
            76/76 for 1UBQ), and matches the threshold in the project&rsquo;s original
            contact-graph script.
          </li>
          <li>
            <code>candidate_score</code> = 0.45·SASA + 0.30·(1 − packing) +
            0.25·susceptibility — verified exact to 1.1 × 10⁻¹⁶ across all 50 ranked
            rows.
          </li>
          <li>
            Residue inclusion requires a Cα atom. That single rule reconciles a naive
            90-residue parse of 1TEN with the reference table&rsquo;s 89: residue A:802
            is an arginine carrying only C and O.
          </li>
        </ul>
        <p>
          One feature does <strong>not</strong> reproduce.{' '}
          <code>residue_sasa_norm</code> is per-chain min–max normalised solvent
          accessibility, but the reference used a different implementation or atom-radius
          set. BioPython&rsquo;s Shrake-Rupley correlates r = 0.93 (1UBQ), 0.98 (1PGA)
          and 0.99 (1TIT) with it, but is not bit-identical. Upload predictions
          therefore carry an explicit approximation warning, and approved proteins never
          use the recomputed path.
        </p>
      </Section>

      {/* --- Simulation ------------------------------------------------- */}
      <Section icon={Cpu} title="What OpenMM simulates">
        <p>
          Real molecular dynamics: Amber14 force field with GBn2 implicit solvent, a
          Langevin middle integrator, hydrogen-bond constraints, and a 1.2 nm nonbonded
          cutoff. Hydrogens are added by OpenMM&rsquo;s own <code>Modeller</code> so they
          match force-field expectations. The seed drives both the integrator and the
          initial velocities.
        </p>

        {presets.data && (
          <KeyValue
            rows={presets.data.map((preset) => [
              preset.label,
              `${preset.equilibration_steps} + ${preset.production_steps} steps × ${preset.timestep_fs} fs = ${preset.simulated_time_ps} ps · ${preset.estimated_runtime_note}`,
            ])}
          />
        )}

        <h4>Assumptions and their consequences</h4>
        <ul>
          <li>
            <strong>Implicit solvent.</strong> No explicit water, so hydration-shell
            structure and solvent viscosity are approximated. This is what makes a
            laptop-scale run possible at all.
          </li>
          <li>
            <strong>1.2 nm cutoff.</strong> Uncut GBn2 is roughly 8× slower and
            infeasible for a live demo. The cutoff is standard practice for implicit
            solvent but does neglect long-range electrostatics.
          </li>
          <li>
            <strong>Picosecond timescale.</strong> Long enough to show real thermal
            dynamics and produce genuine metrics; far too short for equilibrium
            sampling or any statistical claim.
          </li>
          <li>
            <strong>Platform auto-selection.</strong> A GPU platform is used when
            available (roughly 5× faster), falling back to multi-threaded CPU. GPU runs
            are not bit-reproducible; the platform actually used is recorded per job, and
            selecting <code>CPU</code> gives an exactly repeatable trajectory.
          </li>
        </ul>

        <ScientificNotice title="Radiation is not simulated" variant="warning" className="mt-3">
          <p>
            This is the most important limitation in the project. Standard OpenMM
            integrates Newtonian dynamics on a classical force field. It has no model
            for ionising radiation: no particle-track transport, no energy deposition, no
            radiolysis, no radical chemistry, no covalent bond scission.
          </p>
          <p className="mt-2">
            The dose and particle class you set are recorded as provenance and appear in
            the job warnings, but the trajectory reflects thermal dynamics at the
            requested temperature and nothing more. Any radiation effect in BioNano-Sim
            enters through the <em>ML model&rsquo;s scenario category</em>, which was
            itself fitted on synthetic proxy labels. Genuine radiation-damage modelling —
            coupling a transport code to reactive dynamics — is future scope.
          </p>
        </ScientificNotice>
      </Section>

      {/* --- Prediction vs simulation ---------------------------------- */}
      <Section icon={FlaskConical} title="How prediction differs from simulation">
        <div className="scroll-x">
          <table className="w-full min-w-[560px] border-collapse text-left text-2xs">
            <thead>
              <tr className="border-b border-hairline">
                <th className="px-2 py-1.5 font-medium text-ink-faint">Aspect</th>
                <th className="px-2 py-1.5 font-medium text-accent">ML Prediction</th>
                <th className="px-2 py-1.5 font-medium text-ok">Rapid OpenMM Simulation</th>
              </tr>
            </thead>
            <tbody className="text-ink-muted">
              {[
                ['What it is', 'Statistical regression on tabular features', 'Numerical integration of Newtonian dynamics'],
                ['Ground truth', 'Synthetic public-data proxy labels', 'None — it is a first-principles calculation'],
                ['Radiation', 'A categorical scenario the model was fitted on', 'Not modelled at all'],
                ['Output', 'Degradation percent per candidate residue', 'Coordinates, energies, temperatures over time'],
                ['Timescale', 'Not time-resolved', 'Picoseconds'],
                ['Cost', 'Milliseconds', 'Seconds to minutes'],
                ['Validated?', 'No', 'Force field is peer-reviewed; this application of it is not'],
              ].map(([aspect, ml, sim]) => (
                <tr key={aspect} className="border-b border-hairline/50">
                  <td className="px-2 py-1.5 text-ink">{aspect}</td>
                  <td className="px-2 py-1.5">{ml}</td>
                  <td className="px-2 py-1.5">{sim}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h4>The degradation proxy</h4>
        <p>
          To place both on one axis, BioNano-Sim computes a bounded structural-drift
          score from the trajectory: a weighted combination of final RMSD (0.50),
          relative change in radius of gyration (0.20) and mean per-residue RMSF (0.30),
          each normalised against a reference scale. The formula and every component
          contribution are published in the results payload and both exports.
        </p>
        <p>
          The reference scales (0.60 nm RMSD, 25% ΔRg, 0.35 nm RMSF) are{' '}
          <strong>engineering constants chosen for this MVP</strong>, not physical
          constants: changing them changes the number without changing the physics. A
          short run at 300 K produces non-zero drift from thermal motion alone, which is
          exactly why the no-radiation baseline preset exists as a control.
        </p>
      </Section>

      {/* --- Future scope ---------------------------------------------- */}
      <Section icon={Rocket} title="Future scope">
        <ul>
          <li>
            <strong>Radiation-damage modelling.</strong> Couple a particle-transport
            code (Geant4 or PHITS) to a reactive or QM/MM treatment so energy deposition
            and bond scission are actually simulated, rather than represented by a
            scenario label.
          </li>
          <li>
            <strong>Experimental validation.</strong>{' '}
            {model.data?.replacement_requirement ??
              'Retrain on real paired baseline and damaged stiffness measurements.'}{' '}
            Until then no accuracy claim is defensible.
          </li>
          <li>
            <strong>Explicit solvent and longer trajectories.</strong> TIP3P water with
            particle-mesh Ewald on GPU, reaching hundreds of nanoseconds, would make the
            stability metrics statistically meaningful.
          </li>
          <li>
            <strong>Steered molecular dynamics.</strong> Apply the mechanical force the
            interface currently only records, so force-extension behaviour can be
            measured directly — the natural test for a protein proposed as a spring.
          </li>
          <li>
            <strong>Calibrated uncertainty.</strong> Quantile regression or a conformal
            wrapper, so a per-prediction interval exists and{' '}
            <code>confidence</code> stops being <code>null</code>.
          </li>
          <li>
            <strong>Broader protein coverage.</strong> All 20 amino acids in the encoder
            vocabulary, and enough proteins that generalisation can be measured rather
            than hoped for.
          </li>
        </ul>
      </Section>

      {/* --- Not claimed ------------------------------------------------ */}
      <section className="rounded-lg border border-danger/30 bg-danger/[0.06] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Ban className="h-4 w-4 text-danger" aria-hidden />
          What this MVP does not claim
        </h2>
        <ul className="mt-3 space-y-2">
          {NOT_CLAIMED.map((item, index) => (
            <li key={index} className="flex gap-2.5">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-danger" aria-hidden />
              <span className="text-xs leading-relaxed text-ink-muted">{item}</span>
            </li>
          ))}
        </ul>
      </section>

      {model.data && (
        <p className="text-center text-2xs text-ink-faint">
          Model {model.data.model_version} · bundle SHA-256{' '}
          <span className="font-mono">
            {model.data.bundle_sha256?.slice(0, 16)}…
          </span>{' '}
          · integrity {model.data.sha256_verified ? 'verified' : 'UNVERIFIED'} · schema{' '}
          {model.data.schema_verified ? 'verified' : 'UNVERIFIED'}
        </p>
      )}
    </div>
  )
}

function Section({
  icon: Icon,
  title,
  children,
  defaultOpen = false,
}: {
  icon: typeof Rocket
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-raised/50"
      >
        <span className="flex items-center gap-2.5">
          <Icon className="h-4 w-4 shrink-0 text-accent" aria-hidden />
          <span className="text-sm font-medium text-ink">{title}</span>
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-ink-faint transition-transform duration-200',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>
      {open && (
        <div className="prose-bionano border-t border-hairline px-4 py-3.5">
          {children}
        </div>
      )}
    </section>
  )
}

function KeyValue({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="my-3 space-y-1 rounded-lg border border-hairline bg-void/50 p-2.5">
      {rows.map(([key, value]) => (
        <div key={key} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <dt className="shrink-0 text-2xs text-ink-faint">{key}</dt>
          <dd className="tabular min-w-0 flex-1 font-mono text-2xs text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  )
}
