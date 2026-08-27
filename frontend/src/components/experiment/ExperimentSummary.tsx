import { ClipboardList } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import type { ExperimentDraft } from '@/stores/experimentStore'
import type { Scenario } from '@/types/prediction'
import type { SimulationPreset } from '@/types/simulation'

interface ExperimentSummaryProps {
  draft: ExperimentDraft
  scenario: Scenario | undefined
  preset: SimulationPreset | undefined
}

/**
 * The exact configuration that will be submitted.
 *
 * Rows are split into what the ML model consumes and what it does not, because
 * that boundary is the most consequential thing a viewer can misunderstand
 * about this application.
 */
export function ExperimentSummary({ draft, scenario, preset }: ExperimentSummaryProps) {
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
    ['Mechanical force', `${draft.mechanicalForcePn} pN`],
    ['Seed', `${draft.randomSeed}`],
    ['Preset', preset?.label ?? draft.presetId],
  ]

  return (
    <div className="space-y-3">
      <span className="label flex items-center gap-1.5">
        <ClipboardList className="h-3 w-3" aria-hidden />
        Experiment summary
      </span>

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
