import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  Clock,
  Cpu,
  Layers,
  Move3d,
  Thermometer,
  Waves,
  Zap,
} from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { SimulationMetrics } from '@/types/simulation'
import { fmtEnergy, fmtKelvin, fmtNm, fmtNumber, fmtPercent } from '@/utils/formatters'

interface Metric {
  icon: LucideIcon
  label: string
  value: string
  sub?: string
  help: string
}

export function MetricsGrid({
  metrics,
  className,
}: {
  metrics: SimulationMetrics
  className?: string
}) {
  const items: Metric[] = [
    {
      icon: Move3d,
      label: 'Final RMSD',
      value: fmtNm(metrics.rmsd_nm?.final),
      sub: metrics.rmsd_nm?.max ? `peak ${fmtNm(metrics.rmsd_nm.max)}` : undefined,
      help:
        'Cα RMSD of the last frame from the first, after superposition. The single ' +
        'most useful number for "did the fold move".',
    },
    {
      icon: Waves,
      label: 'Mean RMSF',
      value: fmtNm(metrics.rmsf_nm?.mean),
      sub: metrics.rmsf_nm?.max ? `peak ${fmtNm(metrics.rmsf_nm.max)}` : undefined,
      help:
        'Average per-residue fluctuation about the mean structure. Higher means a ' +
        'more mobile chain overall.',
    },
    {
      icon: Layers,
      label: 'Rg change',
      value:
        metrics.radius_of_gyration_nm?.relative_change !== null &&
        metrics.radius_of_gyration_nm?.relative_change !== undefined
          ? fmtPercent(metrics.radius_of_gyration_nm.relative_change * 100, 2)
          : '—',
      sub:
        metrics.radius_of_gyration_nm?.initial && metrics.radius_of_gyration_nm?.final
          ? `${fmtNumber(metrics.radius_of_gyration_nm.initial, 3)} → ${fmtNumber(
              metrics.radius_of_gyration_nm.final,
              3,
            )} nm`
          : undefined,
      help:
        'Relative change in radius of gyration between the first and last frame. ' +
        'Near zero means the domain stayed compact.',
    },
    {
      icon: Zap,
      label: 'Potential energy',
      value: fmtEnergy(metrics.potential_energy_kj_mol?.final),
      sub: metrics.potential_energy_kj_mol?.mean
        ? `mean ${fmtEnergy(metrics.potential_energy_kj_mol.mean)}`
        : undefined,
      help:
        'Final potential energy of the system. Only comparable between runs on the ' +
        'same protein with the same force field.',
    },
    {
      icon: Thermometer,
      label: 'Temperature',
      value: fmtKelvin(metrics.temperature_kelvin?.mean),
      sub: metrics.temperature_kelvin?.std
        ? `σ ${fmtNumber(metrics.temperature_kelvin.std, 1)} K`
        : undefined,
      help:
        'Mean and standard deviation of the instantaneous temperature. Large σ is ' +
        'expected for a system this small.',
    },
    {
      icon: Activity,
      label: 'Minimisation Δ',
      value: fmtEnergy(metrics.minimisation?.delta_kj_mol),
      sub: `${metrics.minimisation?.max_iterations ?? 0} max iterations`,
      help:
        'Energy change during minimisation. It must be negative — minimisation ' +
        'only ever lowers the potential energy.',
    },
    {
      icon: Clock,
      label: 'Simulated time',
      value: `${fmtNumber(metrics.simulated_time_ps, 1)} ps`,
      sub: `${metrics.n_frames} frames`,
      help:
        'Total simulated time: (equilibration + production) steps × timestep. ' +
        'Picoseconds. Real degradation processes act over seconds to years, so this ' +
        'cannot be extrapolated to mission timescales.',
    },
    {
      icon: Cpu,
      label: 'System',
      value: `${metrics.n_atoms ?? 0} atoms`,
      sub: metrics.n_ca_atoms ? `${metrics.n_ca_atoms} Cα` : undefined,
      help:
        'Atom count of the built system, including the hydrogens OpenMM added. ' +
        'Metrics are computed on the Cα subset.',
    },
  ]

  return (
    <div
      className={cn(
        'grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-4',
        className,
      )}
    >
      {items.map((item) => (
        <div key={item.label} className="card p-2.5">
          <div className="flex items-center gap-1.5">
            <item.icon className="h-3 w-3 shrink-0 text-ink-faint" aria-hidden />
            <span className="truncate text-2xs text-ink-faint">{item.label}</span>
            <Tooltip width="md" content={item.help} />
          </div>
          <p className="tabular mt-1 truncate font-mono text-sm text-ink">
            {item.value}
          </p>
          {item.sub && (
            <p className="tabular truncate font-mono text-2xs text-ink-faint">
              {item.sub}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
