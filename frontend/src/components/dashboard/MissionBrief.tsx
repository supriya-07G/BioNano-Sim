import { ArrowRight, Orbit } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { cn } from '@/components/ui/cn'

/**
 * The dashboard's opening panel: why the project exists, and what the
 * platform measures instead of what it cannot.
 */
export function MissionBrief({ className }: { className?: string }) {
  const navigate = useNavigate()

  return (
    <section className={cn('card p-4', className)}>
      <h2 className="flex items-center gap-1.5 text-xs font-medium text-ink">
        <Orbit className="h-3.5 w-3.5 text-accent" aria-hidden />
        The problem
      </h2>

      <p className="mt-2 text-xs leading-relaxed text-ink-muted">
        Deep-space radiation damages protein-based molecular components,
        reducing their structural stability and mechanical performance. That
        threatens the reliability of bioengineered systems on long-duration
        missions, where <strong className="text-ink">repair, replacement
        and resupply are extremely limited</strong>.
      </p>

      <p className="mt-2 text-xs leading-relaxed text-ink-muted">
        A component that loses load-bearing capacity in transit cannot be
        swapped out. The engineering question is therefore not{' '}
        <em>whether</em> damage occurs, but{' '}
        <strong className="text-ink">which domains still carry load once
        it has</strong> — and that has to be known before launch.
      </p>

      <div className="hairline-divider my-3" />

      <h3 className="text-xs font-medium text-ink">What COSMORA measures</h3>
      <p className="mt-2 text-xs leading-relaxed text-ink-muted">
        Radiation chemistry is not simulated — molecular dynamics cannot
        compute it honestly. What it can compute is the{' '}
        <strong className="text-ink">mechanical consequence</strong> of the
        damage: a residue is removed, the domain is pulled apart under a
        calibrated force, and the change in stiffness is measured in pN/nm.
      </p>
      <p className="mt-2 text-xs leading-relaxed text-ink-muted">
        Residues are chosen by literature radiosensitivity, so the damage is
        placed where radiation would place it. The measurement that follows
        is real physics on real coordinates.
      </p>

      <dl className="mt-3 grid grid-cols-3 gap-2">
        {[
          ['520', 'paired simulations'],
          ['13', 'domains screened'],
          ['4', 'load-bearing found'],
        ].map(([value, label]) => (
          <div key={label} className="rounded-lg border border-hairline bg-raised p-2">
            <dt className="tabular font-mono text-sm text-ink">{value}</dt>
            <dd className="text-2xs leading-tight text-ink-faint">{label}</dd>
          </div>
        ))}
      </dl>

      <button
        type="button"
        className="btn-ghost mt-3 !text-2xs"
        onClick={() => navigate('/methodology')}
      >
        How it works
        <ArrowRight className="h-3 w-3" aria-hidden />
      </button>
    </section>
  )
}
