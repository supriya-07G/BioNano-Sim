import { Gauge, Thermometer } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import type { SimulationPreset } from '@/types/simulation'
import { TEMPERATURE_MAX, TEMPERATURE_MIN } from '@/utils/validators'
import { blurOnWheel } from '@/utils/inputGuards'

interface MechanicalControlsProps {
  temperatureKelvin: number
  mechanicalForcePn: number
  randomSeed: number
  presetId: string
  presets: SimulationPreset[] | undefined
  onChange: (patch: {
    temperatureKelvin?: number
    mechanicalForcePn?: number
    randomSeed?: number
    presetId?: string
  }) => void
  disabled?: boolean
}

export function MechanicalControls({
  temperatureKelvin,
  mechanicalForcePn,
  randomSeed,
  presetId,
  presets,
  onChange,
  disabled = false,
}: MechanicalControlsProps) {
  const preset = presets?.find((p) => p.preset_id === presetId)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Gauge className="h-3 w-3" aria-hidden />
          Mechanical &amp; thermal
        </span>
      </div>

      {/* Temperature: the one numeric input that genuinely reaches the engine. */}
      <label className="block">
        <span className="mb-1 flex items-center gap-1.5 text-2xs text-ink-faint">
          <Thermometer className="h-3 w-3" aria-hidden />
          Temperature (K)
          <span className="badge border-ok/40 bg-ok/10 text-ok">drives simulation</span>
          <Tooltip
            width="lg"
            content={
              <span>
                Sets the Langevin thermostat temperature, so this genuinely changes the
                trajectory. Limited to {TEMPERATURE_MIN}&ndash;{TEMPERATURE_MAX} K:
                below ~{TEMPERATURE_MIN} K the implicit-solvent model and hydrogen-bond
                constraints stop being meaningful, and above ~{TEMPERATURE_MAX} K the
                integrator goes unstable at a 2 fs timestep. It is <em>not</em> an ML
                model input.
              </span>
            }
          />
        </span>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={TEMPERATURE_MIN}
            max={TEMPERATURE_MAX}
            step={5}
            value={temperatureKelvin}
            disabled={disabled}
            onChange={(event) =>
              onChange({ temperatureKelvin: Number(event.target.value) })
            }
            className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-void accent-accent disabled:cursor-not-allowed"
            onWheel={blurOnWheel}
          />
          <input
            type="number"
            className="input tabular w-20 font-mono !py-1.5"
            onWheel={blurOnWheel}
            min={TEMPERATURE_MIN}
            max={TEMPERATURE_MAX}
            value={temperatureKelvin}
            disabled={disabled}
            onChange={(event) =>
              onChange({ temperatureKelvin: Number(event.target.value) })
            }
          />
        </div>
      </label>

      {/* Mechanical force: recorded but not applied by this engine. */}
      <label className="block">
        <span className="mb-1 flex items-center gap-1.5 text-2xs text-ink-faint">
          Mechanical force (pN)
          <span className="badge border-danger/30 bg-danger/[0.07] text-danger">
            inactive · pulling unavailable
          </span>
          <Tooltip
            width="lg"
            content={
              <span>
                Recorded for provenance. The Rapid Demo engine applies{' '}
                <strong>no external pulling force</strong> — steered molecular dynamics
                is future scope. Any non-zero value here is reported in the job
                warnings so it cannot be mistaken for an applied load.
              </span>
            }
          />
        </span>
        <input
          type="number"
          className="input tabular font-mono"
          onWheel={blurOnWheel}
          min={0}
          step={10}
          value={mechanicalForcePn}
          disabled
          aria-describedby="force-coupling-note"
          onChange={(event) =>
            onChange({ mechanicalForcePn: Number(event.target.value) })
          }
        />
        <p id="force-coupling-note" className="mt-1 text-2xs leading-relaxed text-ink-faint">
          No external pulling force is enabled in this MVP. The value is fixed at
          zero and cannot affect the trajectory until pulling MD is implemented.
        </p>
      </label>

      {/* Preset */}
      <label className="block">
        <span className="mb-1 flex items-center gap-1.5 text-2xs text-ink-faint">
          Simulation preset
          <span className="badge border-ok/40 bg-ok/10 text-ok">drives simulation</span>
          <Tooltip
            width="lg"
            content="Controls trajectory length and therefore runtime. Every preset is a real OpenMM run; none is production-scale molecular dynamics."
          />
        </span>
        <select
          className="select"
          onWheel={blurOnWheel}
          value={presetId}
          disabled={disabled}
          onChange={(event) => onChange({ presetId: event.target.value })}
        >
          {presets?.map((option) => (
            <option key={option.preset_id} value={option.preset_id}>
              {option.label} — {option.simulated_time_ps} ps
            </option>
          ))}
        </select>
      </label>

      {preset && (
        <div className="rounded-lg border border-hairline bg-void/50 p-2.5">
          <p className="text-2xs leading-relaxed text-ink-muted">{preset.summary}</p>
          <dl className="tabular mt-2 grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-2xs">
            <Row label="Solvent" value={preset.solvent} />
            <Row label="Cutoff" value={`${preset.nonbonded_cutoff_nm} nm`} />
            <Row label="Timestep" value={`${preset.timestep_fs} fs`} />
            <Row label="Equilibration" value={`${preset.equilibration_steps} steps`} />
            <Row label="Production" value={`${preset.production_steps} steps`} />
            <Row label="Simulated time" value={`${preset.simulated_time_ps} ps`} />
          </dl>
          <p className="mt-2 text-2xs text-ink-faint">{preset.estimated_runtime_note}</p>
        </div>
      )}

      {/* Seed */}
      <label className="block">
        <span className="mb-1 flex items-center gap-1.5 text-2xs text-ink-faint">
          Random seed
          <span className="badge border-ok/40 bg-ok/10 text-ok">reproducibility</span>
          <Tooltip
            width="lg"
            content="Seeds both the integrator and the initial velocities. On the CPU platform the same seed reproduces the trajectory exactly; GPU platforms are faster but not bit-reproducible. The platform actually used is recorded in the job's reproducibility block."
          />
        </span>
        <input
          type="number"
          className="input tabular font-mono"
          onWheel={blurOnWheel}
          min={0}
          step={1}
          value={randomSeed}
          disabled={disabled}
          onChange={(event) => onChange({ randomSeed: Number(event.target.value) })}
        />
      </label>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="truncate text-ink">{value}</dd>
    </div>
  )
}
