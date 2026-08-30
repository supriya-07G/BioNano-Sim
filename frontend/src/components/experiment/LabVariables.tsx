import { FlaskConical, Thermometer, Waves } from 'lucide-react'

import { cn } from '@/components/ui/cn'
import type { ExperimentDraft } from '@/stores/experimentStore'
import type { Scenario } from '@/types/prediction'
import type { SimulationPreset } from '@/types/simulation'

/**
 * The variables of the run, shown beside the structure in full screen.
 *
 * Read-only on purpose. Full screen is for looking at the molecule, and a form
 * that can be edited from two places is a form whose two copies drift. The
 * coupling badges are repeated from the workspace so the distinction between
 * what drives physics and what is only recorded survives the context switch --
 * that distinction is easiest to forget exactly when the structure is filling
 * the screen.
 */

type Coupling = 'physics' | 'ml' | 'provenance'

const COUPLING_STYLE: Record<Coupling, string> = {
  physics: 'border-ok/35 bg-ok/[0.08] text-ok',
  ml: 'border-accent/35 bg-accent/[0.08] text-accent',
  provenance: 'border-hairline bg-raised text-ink-faint',
}

const COUPLING_LABEL: Record<Coupling, string> = {
  physics: 'drives simulation',
  ml: 'affects ML',
  provenance: 'provenance only',
}

function Row({
  label,
  value,
  coupling,
}: {
  label: string
  value: string
  coupling: Coupling
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <div className="min-w-0">
        <p className="text-2xs text-ink-faint">{label}</p>
        <p className="tabular break-words font-mono text-xs text-ink">{value}</p>
      </div>
      <span className={cn('badge shrink-0', COUPLING_STYLE[coupling])}>
        {COUPLING_LABEL[coupling]}
      </span>
    </div>
  )
}

function Group({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Waves
  title: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h3 className="mb-1 flex items-center gap-1.5 text-2xs font-medium uppercase tracking-[0.14em] text-ink-faint">
        <Icon className="h-3 w-3 text-accent" aria-hidden />
        {title}
      </h3>
      <div className="divide-y divide-hairline">{children}</div>
    </section>
  )
}

export function LabVariables({
  draft,
  scenario,
  preset,
}: {
  draft: ExperimentDraft
  scenario: Scenario | undefined
  preset: SimulationPreset | undefined
}) {
  return (
    <>
      <Group icon={Waves} title="Environment">
        <Row
          label="Scenario"
          value={scenario?.label ?? draft.scenarioId ?? '—'}
          coupling="ml"
        />
        <Row
          label="Dose"
          value={`${draft.dose} ${draft.doseUnit}`}
          coupling="provenance"
        />
        <Row
          label="Exposure"
          value={`${draft.exposureDurationDays} days`}
          coupling="provenance"
        />
      </Group>

      <Group icon={Thermometer} title="Conditions">
        <Row
          label="Temperature"
          value={`${draft.temperatureKelvin} K`}
          coupling="physics"
        />
        <Row label="Random seed" value={`${draft.randomSeed}`} coupling="physics" />
      </Group>

      <Group icon={FlaskConical} title="Protocol">
        <Row
          label="Preset"
          value={preset?.label ?? draft.presetId}
          coupling="physics"
        />
        <Row
          label="Simulated time"
          value={preset ? `${preset.simulated_time_ps} ps` : '—'}
          coupling="physics"
        />
        <Row
          label="Mechanical load"
          value={
            preset?.pulling
              ? `${preset.pulling.spring_constant_kj_mol_nm2} kJ/mol/nm² @ ${preset.pulling.pull_velocity_nm_per_ps} nm/ps`
              : 'none for this preset'
          }
          coupling={preset?.pulling ? 'physics' : 'provenance'}
        />
      </Group>

      <p className="border-t border-hairline pt-3 text-2xs leading-relaxed text-ink-faint">
        Values are read-only here. Edit them in the workspace behind this view;
        press <kbd className="font-mono text-ink-muted">Esc</kbd> to return.
      </p>
    </>
  )
}
