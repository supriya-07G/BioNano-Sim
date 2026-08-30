import { ClipboardList } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import type { ExperimentDraft } from '@/stores/experimentStore'
import type { Scenario } from '@/types/prediction'
import type { SimulationPreset } from '@/types/simulation'
import type { ModelInfo } from '@/types/prediction'

interface ExperimentSummaryProps {
  draft: ExperimentDraft
  scenario: Scenario | undefined
  preset: SimulationPreset | undefined
  model: ModelInfo | undefined
}

/**
 * The exact configuration that will be submitted.
 *
 * Rows are split into what the ML model consumes and what it does not, because
 * that boundary is the most consequential thing a viewer can misunderstand
 * about this application.
 */
export function ExperimentSummary({ draft, scenario, preset, model }: ExperimentSummaryProps) {
  const structure = draft.uploadId
    ? `upload · ${draft.uploadFilename ?? draft.uploadId}`
    : (draft.pdbId ?? '—')

  const mlInputs: [string, string][] = [
    ['Structure', structure],
    ['Chain', draft.chainId],
    ['Scenario', scenario?.scenario_id ?? draft.scenarioId],
    ['Radiation class', scenario?.radiation_class ?? 'none'],
    ['Environment', scenario?.environment ?? '—'],
    ['Candidate residues', `${draft.topNResidues}`],
  ]

  const nonMlInputs: [string, string][] = [
    ['Dose', `${draft.dose} ${draft.doseUnit}`],
    ['Duration', `${draft.exposureDurationDays} days`],
    ['Temperature', `${draft.temperatureKelvin} K`],
    [
      'Mechanical force',
      preset?.pulling
        ? `set by the preset: ${preset.pulling.spring_constant_kj_mol_nm2} kJ/mol/nm² at ${preset.pulling.pull_velocity_nm_per_ps} nm/ps`
        : 'provenance only · this preset applies no pull',
    ],
    ['Seed', `${draft.randomSeed}`],
    ['Preset', preset?.label ?? draft.presetId],
  ]

  return (
    <div className="space-y-3">
      <span className="label flex items-center gap-1.5">
        <ClipboardList className="h-3 w-3" aria-hidden />
        Experiment summary
      </span>

      <CalculationMode
        draft={draft}
        scenario={scenario}
        preset={preset}
        model={model}
      />

      <Section
        title="Consumed by the ML model"
        tone="accent"
        rows={mlInputs}
        help="These are the only fields that reach the model. Change one of these and the estimate changes."
      />

      <Section
        title="Simulation & provenance only"
        tone="muted"
        rows={nonMlInputs}
        help="Recorded in the job record and used by OpenMM (temperature) or kept purely for provenance (dose, duration, force). None of these is an ML model input."
      />
    </div>
  )
}

function CalculationMode({
  draft,
  scenario,
  preset,
  model,
}: {
  draft: ExperimentDraft
  scenario: Scenario | undefined
  preset: SimulationPreset | undefined
  model: ModelInfo | undefined
}) {
  const features = model?.feature_order ?? []

  return (
    <div className="rounded-lg border border-accent/25 bg-accent/[0.05] p-2.5">
      <div className="mb-2">
        <span className="text-2xs font-medium text-accent">Calculation mode</span>
        <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">
          The ML estimate uses model features only. OpenMM receives the thermal and
          preset parameters below. Radiation dose and mechanical force are provenance
          fields, not active physics inputs.
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-2xs">
        <div>
          <dt className="text-ink-faint">ML scenario</dt>
          <dd className="truncate text-ink">{scenario?.scenario_id ?? draft.scenarioId}</dd>
        </div>
        <div>
          <dt className="text-ink-faint">ML support</dt>
          <dd className={scenario?.ml_supported ? 'text-ok' : 'text-warn'}>
            {scenario?.ml_supported ? 'enabled' : 'unavailable'}
          </dd>
        </div>
        <div>
          <dt className="text-ink-faint">OpenMM temperature</dt>
          <dd className="text-ink">{draft.temperatureKelvin} K</dd>
        </div>
        <div>
          <dt className="text-ink-faint">Preset</dt>
          <dd className="truncate text-ink">{preset?.label ?? draft.presetId}</dd>
        </div>
        <div>
          <dt className="text-ink-faint">Timestep</dt>
          <dd className="text-ink">{preset?.timestep_fs ?? '—'} fs</dd>
        </div>
        <div>
          <dt className="text-ink-faint">Production</dt>
          <dd className="text-ink">{preset?.production_steps ?? '—'} steps</dd>
        </div>
        <div>
          <dt className="text-ink-faint">Pulling force</dt>
          {/*
            Preset-dependent, not a constant. This said "inactive (0 pN)" in
            red for every preset, including Mechanical Pull, which applies a
            real load -- so the summary contradicted the run it was
            summarising.
          */}
          <dd className={preset?.pulling ? 'text-ok' : 'text-ink-muted'}>
            {preset?.pulling
              ? `${preset.pulling.spring_constant_kj_mol_nm2} kJ/mol/nm² @ ${preset.pulling.pull_velocity_nm_per_ps} nm/ps`
              : 'none for this preset'}
          </dd>
        </div>
        <div>
          <dt className="text-ink-faint">Radiation physics</dt>
          <dd className="text-ink-muted">not simulated</dd>
        </div>
      </dl>

      <div className="mt-2 border-t border-hairline pt-2">
        <span className="text-2xs font-medium text-ink-muted">Exact ML feature columns</span>
        <p className="mt-1 text-2xs leading-relaxed text-ink-faint">
          {features.length
            ? features.join(' · ')
            : 'Model schema unavailable; feature columns will be reported by the backend.'}
        </p>
      </div>
    </div>
  )
}

function Section({
  title,
  rows,
  tone,
  help,
}: {
  title: string
  rows: [string, string][]
  tone: 'accent' | 'muted'
  help: string
}) {
  return (
    <div
      className={
        tone === 'accent'
          ? 'rounded-lg border border-accent/25 bg-accent/[0.05] p-2.5'
          : 'rounded-lg border border-hairline bg-void/50 p-2.5'
      }
    >
      <div className="mb-1.5 flex items-center gap-1.5">
        <span
          className={
            tone === 'accent'
              ? 'text-2xs font-medium text-accent'
              : 'text-2xs font-medium text-ink-muted'
          }
        >
          {title}
        </span>
        <Tooltip width="md" content={help} />
      </div>
      <dl className="tabular grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-2xs">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="truncate text-ink-faint">{label}</dt>
            <dd className="truncate text-ink" title={value}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
