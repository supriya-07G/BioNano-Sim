import { AlertTriangle, Radiation } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { DoseUnit, DoseUnitOption, Scenario } from '@/types/prediction'
import { blurOnWheel } from '@/utils/inputGuards'

interface RadiationControlsProps {
  scenarios: Scenario[]
  doseUnits: DoseUnitOption[]
  scenarioId: string
  dose: number
  doseUnit: DoseUnit
  exposureDurationDays: number
  onScenarioChange: (scenario: Scenario) => void
  onChange: (patch: {
    dose?: number
    doseUnit?: DoseUnit
    exposureDurationDays?: number
  }) => void
  disabled?: boolean
}

/**
 * Radiation environment controls.
 *
 * The dose, unit and duration inputs are labelled as *simulation and provenance
 * only*, because the ML bundle has no numeric radiation feature — it sees the
 * scenario category and nothing else. Presenting these as if they drove the
 * prediction would be the single easiest way to mislead a viewer, so the panel
 * says so directly rather than in a footnote.
 */
export function RadiationControls({
  scenarios,
  doseUnits,
  scenarioId,
  dose,
  doseUnit,
  exposureDurationDays,
  onScenarioChange,
  onChange,
  disabled = false,
}: RadiationControlsProps) {
  const selected = scenarios.find((s) => s.scenario_id === scenarioId)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Radiation className="h-3 w-3" aria-hidden />
          Radiation environment
        </span>
        <Tooltip
          width="lg"
          content={
            <span>
              Scenario values are <strong>configurable demonstration presets</strong>,
              not authoritative NASA or ESA reference environments. The ML model
              consumes only the scenario category (
              <code>scenario_id</code>, <code>radiation_class</code>,{' '}
              <code>environment</code>) — never the numeric dose.
            </span>
          }
        />
      </div>

      {/* Scenario */}
      <label className="block">
        <span className="mb-1 block text-2xs text-ink-faint">Scenario</span>
        <select
          className="select"
          onWheel={blurOnWheel}
          value={scenarioId}
          disabled={disabled}
          onChange={(event) => {
            const next = scenarios.find((s) => s.scenario_id === event.target.value)
            if (next) onScenarioChange(next)
          }}
        >
          {scenarios.map((scenario) => (
            <option key={scenario.scenario_id} value={scenario.scenario_id}>
              {scenario.label}
              {scenario.ml_supported ? '' : '  (no ML estimate)'}
            </option>
          ))}
        </select>
      </label>

      {selected && (
        <div className="rounded-lg border border-hairline bg-void/50 p-2.5">
          <p className="text-2xs leading-relaxed text-ink-muted">{selected.summary}</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
            <Field label="Radiation class" value={selected.radiation_class ?? 'none'} />
            <Field label="Environment" value={selected.environment} />
            <Field
              label="Particle group"
              value={selected.particle_group ?? 'n/a'}
              className="col-span-2"
            />
          </dl>
        </div>
      )}

      {selected && !selected.ml_supported && (
        <div className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/[0.07] p-2.5">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" aria-hidden />
          <p className="text-2xs leading-relaxed text-ink-muted">
            <strong className="text-warn">No ML estimate for this scenario.</strong>{' '}
            {selected.ml_unsupported_reason}
          </p>
        </div>
      )}

      {/* Dose */}
      <div className="rounded-lg border border-hairline bg-void/30 p-2.5">
        <div className="mb-2 flex items-center gap-1.5">
          <span className="text-2xs font-medium text-ink-muted">
            Dose and exposure
          </span>
          <span className="badge border-hairline bg-elevated text-ink-faint">
            not an ML input
          </span>
          <Tooltip
            width="lg"
            content={
              <span>
                These values are recorded for provenance and set the simulation
                thermostat. The ML model has no dose, duration or temperature feature,
                so changing them will <strong>not</strong> change the ML degradation
                estimate. Standard OpenMM also does not model ionising radiation: no
                particle tracks, energy deposition or bond scission are simulated.
              </span>
            }
          />
        </div>

        <div className="grid grid-cols-[1fr_auto] gap-2">
          <label className="block">
            <span className="mb-1 block text-2xs text-ink-faint">Dose</span>
            <input
              type="number"
              className="input tabular font-mono"
              onWheel={blurOnWheel}
              value={dose}
              min={0}
              step={0.1}
              disabled={disabled}
              onChange={(event) => onChange({ dose: Number(event.target.value) })}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-2xs text-ink-faint">Unit</span>
            <select
              className="select w-24"
              onWheel={blurOnWheel}
              value={doseUnit}
              disabled={disabled}
              onChange={(event) =>
                onChange({ doseUnit: event.target.value as DoseUnit })
              }
            >
              {doseUnits.map((unit) => (
                <option key={unit.unit} value={unit.unit}>
                  {unit.unit}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="mt-2 block">
          <span className="mb-1 block text-2xs text-ink-faint">
            Exposure duration (days)
          </span>
          <input
            type="number"
            className="input tabular font-mono"
            onWheel={blurOnWheel}
            value={exposureDurationDays}
            min={0}
            step={1}
            disabled={disabled}
            onChange={(event) =>
              onChange({ exposureDurationDays: Number(event.target.value) })
            }
          />
        </label>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className={cn('min-w-0', className)}>
      <dt className="text-2xs text-ink-faint">{label}</dt>
      <dd className="truncate font-mono text-2xs text-ink">{value}</dd>
    </div>
  )
}
