import { Clock, Cpu, Gauge, Thermometer, Zap } from 'lucide-react'

import { Progress } from '@/components/ui/Progress'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { SimulationJobDetail } from '@/types/simulation'
import { fmtDuration, fmtEnergy, fmtKelvin, humanise } from '@/utils/formatters'

/**
 * Live progress readout.
 *
 * Every value here originates in the backend job record: `steps_completed` comes
 * from the integrator's own counter, and temperature/energy are read from the
 * OpenMM context after each step chunk. There is no client-side interpolation,
 * so a stalled run shows a stalled bar.
 */
export function SimulationProgress({
  job,
  className,
}: {
  job: SimulationJobDetail
  className?: string
}) {
  const stepPercent =
    job.steps_total > 0 ? (job.steps_completed / job.steps_total) * 100 : null

  const tone =
    job.status === 'failed'
      ? 'danger'
      : job.status === 'cancelled'
        ? 'warn'
        : job.status === 'completed'
          ? 'ok'
          : 'accent'

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={job.status} />
          {job.current_stage && (
            <span className="text-xs text-ink-muted">
              {humanise(job.current_stage)}
            </span>
          )}
        </div>
        <span className="tabular font-mono text-xs text-ink">
          {(job.progress * 100).toFixed(0)}%
        </span>
      </div>

      <Progress
        value={job.progress}
        tone={tone}
        label={`Simulation ${job.status}, ${(job.progress * 100).toFixed(0)} percent`}
      />

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat
          icon={Cpu}
          label="Steps"
          value={
            job.steps_total > 0
              ? `${job.steps_completed.toLocaleString()} / ${job.steps_total.toLocaleString()}`
              : 'n/a'
          }
          sub={stepPercent !== null ? `${stepPercent.toFixed(1)}%` : undefined}
          help="Integration steps completed, read from the OpenMM integrator. This is the ground truth for progress."
        />
        <Stat
          icon={Clock}
          label="Elapsed"
          value={fmtDuration(job.elapsed_seconds)}
          sub={
            job.duration_seconds !== null
              ? `total ${fmtDuration(job.duration_seconds)}`
              : undefined
          }
          help="Wall-clock time since the worker picked up the job."
        />
        <Stat
          icon={Thermometer}
          label="Temperature"
          value={fmtKelvin(job.temperature_kelvin)}
          help="Instantaneous temperature computed from the system's kinetic energy. It rises during equilibration then fluctuates around the thermostat setpoint."
        />
        <Stat
          icon={Zap}
          label="Potential energy"
          value={fmtEnergy(job.potential_energy_kj_mol)}
          help="Potential energy of the current configuration. It drops sharply during minimisation, then rises and plateaus once dynamics start."
          className="col-span-2 sm:col-span-1"
        />
        <Stat
          icon={Gauge}
          label="Preset"
          value={job.preset_id}
          sub={job.engine}
          help="The preset determines trajectory length; the engine is 'openmm' for a live run."
        />
      </dl>
    </div>
  )
}

function Stat({
  icon: Icon,
  label,
  value,
  sub,
  help,
  className,
}: {
  icon: typeof Cpu
  label: string
  value: string
  sub?: string
  help: string
  className?: string
}) {
  return (
    <div className={cn('rounded-lg border border-hairline bg-void/50 p-2', className)}>
      <dt className="flex items-center gap-1 text-2xs text-ink-faint">
        <Icon className="h-3 w-3" aria-hidden />
        {label}
        <Tooltip width="md" content={help} />
      </dt>
      <dd className="tabular mt-0.5 truncate font-mono text-xs text-ink">{value}</dd>
      {sub && <p className="tabular font-mono text-2xs text-ink-faint">{sub}</p>}
    </div>
  )
}
