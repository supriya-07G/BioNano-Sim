import { useState } from 'react'
import { ArrowRight, Orbit } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { ProteinViewer } from '@/components/proteins/ProteinViewer'
import { cn } from '@/components/ui/cn'
import { useStructure } from '@/hooks/useStructure'

/**
 * The dashboard's opening panel: why the project exists, beside a real
 * structure the user can rotate.
 *
 * The viewer is deliberately live rather than a screenshot. The whole claim of
 * the platform is that it works on real coordinates, and a still image of a
 * protein is the one thing a reader has no reason to believe.
 */

/** Load-bearing domains, so the first thing shown is one the platform ranks highly. */
const FEATURED = [
  {
    pdbId: '1TIT',
    name: 'Titin I27',
    role: 'Molecular spring',
    note: 'The standard benchmark for mechanical stability in AFM force spectroscopy. COSMORA measured it as the stiffest of thirteen domains.',
  },
  {
    pdbId: '1UBQ',
    name: 'Ubiquitin',
    role: 'Switch body',
    note: 'A compact β-grasp fold. Load-bearing, and the second stiffest domain in the run.',
  },
  {
    pdbId: '1TEN',
    name: 'Fibronectin III',
    role: 'Structural member',
    note: 'Experimentally load-bearing, but this protocol did not register it — a known false negative, recorded rather than hidden.',
  },
] as const

export function MissionBrief({ className }: { className?: string }) {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<(typeof FEATURED)[number]>(FEATURED[0])
  const structure = useStructure({ kind: 'approved', pdbId: selected.pdbId })

  return (
    <section className={cn('card overflow-hidden', className)}>
      <div className="grid gap-0 lg:grid-cols-[1.05fr_1fr]">
        {/* --- The problem ------------------------------------------------ */}
        <div className="border-hairline p-4 lg:border-r">
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
        </div>

        {/* --- A real structure ------------------------------------------- */}
        <div className="p-4">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {FEATURED.map((protein) => {
              const active = protein.pdbId === selected.pdbId
              return (
                <button
                  key={protein.pdbId}
                  type="button"
                  onClick={() => setSelected(protein)}
                  aria-pressed={active}
                  className={cn(
                    'rounded-md border px-2 py-1 font-mono text-2xs transition-colors',
                    active
                      ? 'border-accent/50 bg-accent/10 text-accent'
                      : 'border-hairline bg-raised text-ink-faint hover:border-accent/30 hover:text-ink-muted',
                  )}
                >
                  {protein.pdbId}
                </button>
              )
            })}
            <span className="ml-auto text-2xs text-ink-faint">drag to rotate</span>
          </div>

          <div className="h-64 overflow-hidden rounded-lg border border-hairline bg-void">
            <ProteinViewer
              data={structure.data}
              isLoading={structure.isLoading}
              error={structure.error}
              mode="cartoon"
              colourMode="chain"
              autoSpin
              showControls={false}
              screenshotName={`COSMORA-${selected.pdbId}`}
              onRetry={() => void structure.refetch()}
            />
          </div>

          <p className="mt-2 text-xs text-ink">
            <span className="font-medium">{selected.name}</span>{' '}
            <span className="text-ink-faint">· {selected.role}</span>
          </p>
          <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
            {selected.note}
          </p>
        </div>
      </div>
    </section>
  )
}
