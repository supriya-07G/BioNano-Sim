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

      {/*
        This field is provenance-only, but pulling itself is NOT future scope:
        the Mechanical Pull preset below runs real steered MD. Saying otherwise
        made the form contradict its own preset list two rows down, and
        understated a capability the project actually has. What is true is
        narrower: the load comes from the preset's spring constant and pulling
        velocity, not from this number.
      */}
      <label className="block">
        <span className="mb-1 flex items-center gap-1.5 text-2xs text-ink-faint">
          Mechanical force (pN)
          <span className="badge border-hairline bg-raised text-ink-faint">
            provenance only
          </span>
          <Tooltip
            width="lg"
            content={
              <span>
                Recorded for provenance; it does not set the load. Real pulling{' '}
                <strong>is</strong> available — select the{' '}
                <strong>Mechanical Pull</strong> preset below, which applies a
                moving harmonic restraint to the terminal Cα distance. The force
                the molecule actually carried is reported in the resulting
                force-extension curve.
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
          This field never sets the load. To apply a real force, choose the{' '}
          <strong className="text-ink-muted">Mechanical Pull (steered MD)</strong>{' '}
          preset below — its spring constant and pulling velocity determine the
          load, and the measured force appears in the force-extension curve.
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
