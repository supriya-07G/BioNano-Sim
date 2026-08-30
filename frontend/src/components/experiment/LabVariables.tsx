import { Eye, FlaskConical, Layers, Palette, Thermometer, Waves } from 'lucide-react'

import { ControlGroup } from '@/components/ui/ControlGroup'
import { cn } from '@/components/ui/cn'
import type { ExperimentDraft } from '@/stores/experimentStore'
import type { Scenario } from '@/types/prediction'
import type { SimulationPreset } from '@/types/simulation'

import type { ColourMode, RenderMode } from '@/components/proteins/ProteinViewer'

/**
 * The variables of the run, editable beside the structure in full screen.
 *
 * Every control writes to the same draft the workspace edits, so there is one
 * source of truth and no second copy to drift. The coupling badges are
 * repeated from the workspace because the distinction between what drives
 * physics and what is only recorded is easiest to forget exactly when the
 * structure is filling the screen.
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

function Field({
  label,
  coupling,
  children,
  hint,
}: {
  label: string
  coupling: Coupling
  children: React.ReactNode
  hint?: string
}) {
  return (
    <label className="block py-2">
      <span className="mb-1 flex items-center justify-between gap-2">
        <span className="text-2xs text-ink-faint">{label}</span>
        <span className={cn('badge shrink-0', COUPLING_STYLE[coupling])}>
          {COUPLING_LABEL[coupling]}
        </span>
      </span>
      {children}
      {hint && <span className="mt-1 block text-2xs text-ink-faint">{hint}</span>}
    </label>
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

/** Wheel over a focused number input silently changes the value. */
const blurOnWheel = (event: React.WheelEvent<HTMLInputElement>) =>
  event.currentTarget.blur()

export function LabVariables({
  draft,
  scenarios,
  presets,
  scenario,
  preset,
  onChange,
  renderModes,
  colourModes,
  renderMode,
  colourMode,
  onRenderMode,
  onColourMode,
  highlightCount,
}: {
  draft: ExperimentDraft
  scenarios: Scenario[]
  presets: SimulationPreset[] | undefined
  scenario: Scenario | undefined
  preset: SimulationPreset | undefined
  onChange: (patch: Partial<ExperimentDraft>) => void
  renderModes: { value: RenderMode; label: string }[]
  colourModes: { value: ColourMode; label: string }[]
  renderMode: RenderMode
  colourMode: ColourMode
  onRenderMode: (value: RenderMode) => void
  onColourMode: (value: ColourMode) => void
  highlightCount: number
}) {
  return (
    <>
      {/*
        The render and colour toggles live above the viewport in the workspace,
        which puts them behind this overlay in full screen -- exactly where a
        large structure makes them most useful.
      */}
      <Group icon={Eye} title="View">
        <div className="space-y-2 py-2">
          <ControlGroup
            icon={Eye}
            label="Render mode"
            options={renderModes}
            value={renderMode}
            onChange={onRenderMode}
            className="w-full justify-start"
          />
          <ControlGroup
            icon={Palette}
            label="Colour mode"
            options={colourModes}
            value={colourMode}
            onChange={onColourMode}
            className="w-full justify-start"
          />
          {highlightCount > 0 && (
            <span className="badge border-accent/35 bg-accent/[0.08] text-accent">
              <Layers className="h-3 w-3" aria-hidden />
              {highlightCount} candidate residues
            </span>
          )}
        </div>
      </Group>

      <Group icon={Waves} title="Environment">
        <Field label="Scenario" coupling="ml">
          <select
            className="input !text-xs"
            value={draft.scenarioId}
            onChange={(event) => onChange({ scenarioId: event.target.value })}
          >
            {scenarios.map((item) => (
              <option key={item.scenario_id} value={item.scenario_id}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label={`Dose (${draft.doseUnit})`}
          coupling="provenance"
          hint={scenario ? undefined : 'Recorded with the run; it enters no calculation.'}
        >
          <input
            type="number"
            className="input tabular font-mono !text-xs"
            min={0}
            step={0.1}
            value={draft.dose}
            onWheel={blurOnWheel}
            onChange={(event) => onChange({ dose: Number(event.target.value) })}
          />
        </Field>

        <Field label="Exposure (days)" coupling="provenance">
          <input
            type="number"
            className="input tabular font-mono !text-xs"
            min={0}
            step={1}
            value={draft.exposureDurationDays}
            onWheel={blurOnWheel}
            onChange={(event) =>
              onChange({ exposureDurationDays: Number(event.target.value) })
            }
          />
        </Field>
      </Group>

      <Group icon={Thermometer} title="Conditions">
        <Field label="Temperature (K)" coupling="physics">
          <input
            type="number"
            className="input tabular font-mono !text-xs"
            min={0}
            step={5}
            value={draft.temperatureKelvin}
            onWheel={blurOnWheel}
            onChange={(event) =>
              onChange({ temperatureKelvin: Number(event.target.value) })
            }
          />
        </Field>

        <Field
          label="Random seed"
          coupling="physics"
          hint="Same seed and preset reproduce the trajectory exactly on CPU."
        >
          <input
            type="number"
            className="input tabular font-mono !text-xs"
            min={0}
            step={1}
            value={draft.randomSeed}
            onWheel={blurOnWheel}
            onChange={(event) => onChange({ randomSeed: Number(event.target.value) })}
          />
        </Field>
      </Group>

      <Group icon={FlaskConical} title="Protocol">
        <Field label="Preset" coupling="physics">
          <select
            className="input !text-xs"
            value={draft.presetId}
            onChange={(event) => onChange({ presetId: event.target.value })}
          >
            {(presets ?? []).map((item) => (
              <option key={item.preset_id} value={item.preset_id}>
                {item.label} — {item.simulated_time_ps} ps
              </option>
            ))}
          </select>
        </Field>

        {/*
          Not an input. The load is a property of the preset, and offering a
          box here would imply otherwise -- which is the misreading the
          coupling badges exist to prevent.
        */}
        <div className="py-2">
          <p className="mb-1 flex items-center justify-between gap-2">
            <span className="text-2xs text-ink-faint">Mechanical load</span>
            <span
              className={cn(
                'badge shrink-0',
                COUPLING_STYLE[preset?.pulling ? 'physics' : 'provenance'],
              )}
            >
              {COUPLING_LABEL[preset?.pulling ? 'physics' : 'provenance']}
            </span>
          </p>
          <p className="tabular font-mono text-xs text-ink">
            {preset?.pulling
              ? `${preset.pulling.spring_constant_kj_mol_nm2} kJ/mol/nm² @ ${preset.pulling.pull_velocity_nm_per_ps} nm/ps`
              : 'none for this preset'}
          </p>
          <p className="mt-1 text-2xs text-ink-faint">
            Set by the preset, not by hand. Choose Mechanical Pull to apply a
            real load.
          </p>
        </div>
      </Group>

      <p className="border-t border-hairline pt-3 text-2xs leading-relaxed text-ink-faint">
        Changes apply to the run you are about to start and are shared with the
        workspace behind this view. Press{' '}
        <kbd className="font-mono text-ink-muted">Esc</kbd> to return.
      </p>
    </>
  )
}
