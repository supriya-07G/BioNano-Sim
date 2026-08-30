import { useState } from 'react'
import { Orbit } from 'lucide-react'

import { ProteinViewer } from '@/components/proteins/ProteinViewer'
import { cn } from '@/components/ui/cn'
import { useStructure } from '@/hooks/useStructure'

/**
 * A real, rotatable structure beside the hero copy.
 *
 * Live rather than a screenshot on purpose: the platform's claim is that it
 * operates on real coordinates, and a still image of a protein is the one
 * thing a visitor has no reason to believe. This one is fetched from the same
 * endpoint the Simulation Lab uses.
 */

const FEATURED = [
  {
    pdbId: '1TIT',
    name: 'Titin I27',
    stiffness: '713 pN/nm',
    note: 'The AFM benchmark for mechanical stability. Measured as the stiffest of thirteen domains.',
  },
  {
    pdbId: '1UBQ',
    name: 'Ubiquitin',
    stiffness: '661 pN/nm',
    note: 'A compact β-grasp fold, and the second stiffest in the run.',
  },
  {
    pdbId: '1TEN',
    name: 'Fibronectin III',
    stiffness: 'not resolved',
    note: 'Experimentally load-bearing, but this protocol did not register it — a known false negative, reported rather than hidden.',
  },
] as const

export function HeroStructure({ className }: { className?: string }) {
  const [selected, setSelected] = useState<(typeof FEATURED)[number]>(FEATURED[0])
  // Off until asked. A rotation running from page load is a render loop
  // that never idles, which is what made this page block its own thread.
  const [spinning, setSpinning] = useState(false)
  const structure = useStructure({ kind: 'approved', pdbId: selected.pdbId })

  return (
    <div className={cn('relative', className)}>
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
        <button
          type="button"
          onClick={() => setSpinning((value) => !value)}
          aria-pressed={spinning}
          title={spinning ? 'Stop rotation' : 'Rotate automatically'}
          className={cn(
            'ml-auto flex items-center gap-1 rounded-md border px-2 py-1 text-2xs transition-colors',
            spinning
              ? 'border-accent/50 bg-accent/10 text-accent'
              : 'border-hairline bg-raised text-ink-faint hover:border-accent/30 hover:text-ink-muted',
          )}
        >
          <Orbit className="h-3 w-3" aria-hidden />
          {spinning ? 'Rotating' : 'Rotate'}
        </button>
      </div>

      {/*
        No border and no background: the transparent canvas lets the starfield
        and orbit lines behind the hero show through, so the structure sits in
        the page rather than on top of it. The radial mask fades the canvas
        edges out instead of ending them on a hard rectangle.
      */}
      <div
        className="h-64 sm:h-80"
        style={{
          maskImage:
            'radial-gradient(ellipse 72% 72% at 50% 50%, #000 55%, transparent 100%)',
          WebkitMaskImage:
            'radial-gradient(ellipse 72% 72% at 50% 50%, #000 55%, transparent 100%)',
        }}
      >
        <ProteinViewer
          data={structure.data}
          isLoading={structure.isLoading}
          error={structure.error}
          mode="cartoon"
          colourMode="chain"
          autoSpin={spinning}
          transparent
          showControls={false}
          screenshotName={`COSMORA-${selected.pdbId}`}
          onRetry={() => void structure.refetch()}
        />
      </div>

      <div className="mt-2 flex items-baseline justify-between gap-2">
        <p className="text-xs font-medium text-ink">{selected.name}</p>
        <p className="tabular font-mono text-2xs text-accent">{selected.stiffness}</p>
      </div>
      <p className="mt-1 text-2xs leading-relaxed text-ink-faint">{selected.note}</p>
    </div>
  )
}
