import { AlertTriangle } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { ResiduePrediction } from '@/types/prediction'
import type { CandidateResidue } from '@/types/protein'
import { fmtNumber, fmtPercent } from '@/utils/formatters'

interface ResidueInspectorProps {
  candidates: CandidateResidue[]
  /** Present once a prediction has run, keyed by residue_id. */
  predictions?: Map<string, ResiduePrediction>
  selectedResidueId?: string | null
  onSelect?: (residueId: string) => void
  className?: string
}

const SUSCEPTIBILITY_TONE: Record<string, string> = {
  high: 'text-danger',
  medium: 'text-warn',
  low: 'text-ok',
}

/**
 * The ranked candidate residues, with their per-residue ML estimate when one
 * exists. Residues whose type is outside the model's 14-value vocabulary are
 * marked, because their estimate came from an all-zero one-hot block.
 */
export function ResidueInspector({
  candidates,
  predictions,
  selectedResidueId,
  onSelect,
  className,
}: ResidueInspectorProps) {
  if (candidates.length === 0) {
    return (
      <EmptyState
        compact
        title="No candidate residues"
        description="Select a protein to see its ranked candidate residues."
        className={className}
      />
    )
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between">
        <span className="label">Candidate residues</span>
        <Tooltip
          width="lg"
          content={
            <span>
              The model scores individual residues, not whole proteins. These are the
              top-ranked candidates by{' '}
              <code>0.45·SASA + 0.30·(1 − packing) + 0.25·susceptibility</code> — the
              exact formula recovered from the training data. Rank 1 is the most
              exposed, least packed, most chemically susceptible residue.
            </span>
          }
        />
      </div>

      <div className="scroll-x -mx-1">
        <table className="w-full min-w-[420px] border-collapse text-left">
          <thead>
            <tr className="border-b border-hairline">
              <th className="px-1.5 py-1.5 text-2xs font-medium text-ink-faint">#</th>
              <th className="px-1.5 py-1.5 text-2xs font-medium text-ink-faint">
                Residue
              </th>
              <th className="px-1.5 py-1.5 text-2xs font-medium text-ink-faint">
                <span className="inline-flex items-center gap-1">
                  SASA
                  <Tooltip
                    width="md"
                    content="Normalised solvent-accessible surface area (0 = buried, 1 = most exposed in this chain). Exposed residues are more chemically reachable."
                  />
                </span>
              </th>
              <th className="px-1.5 py-1.5 text-2xs font-medium text-ink-faint">
                <span className="inline-flex items-center gap-1">
                  Contacts
                  <Tooltip
                    width="md"
                    content="Number of other Cα atoms within 8 Å. Fewer contacts means a less tightly packed, more mobile residue."
                  />
                </span>
              </th>
              <th className="px-1.5 py-1.5 text-2xs font-medium text-ink-faint">
                <span className="inline-flex items-center gap-1">
                  Susceptibility
                  <Tooltip
                    width="md"
                    content="Qualitative chemical susceptibility by residue type: high for C, H, M, W, Y; medium for R, N, Q, K, F, P, S, T; low for A, D, E, G, I, L, V."
                  />
                </span>
              </th>
              {predictions && (
                <th className="px-1.5 py-1.5 text-right text-2xs font-medium text-ink-faint">
                  <span className="inline-flex items-center gap-1">
                    ML estimate
                    <Tooltip
                      width="lg"
                      content="Predicted side-chain-loss degradation for this residue under the selected scenario. MVP model; not experimentally validated."
                    />
                  </span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => {
              const prediction = predictions?.get(candidate.residue_id)
              const oov = prediction?.residue_type_in_model_vocabulary === false
              const selected = selectedResidueId === candidate.residue_id
              return (
                <tr
                  key={candidate.residue_id}
                  onClick={() => onSelect?.(candidate.residue_id)}
                  className={cn(
                    'border-b border-hairline/50 transition-colors',
                    onSelect && 'cursor-pointer hover:bg-raised',
                    selected && 'bg-accent/[0.08]',
                  )}
                >
                  <td className="tabular px-1.5 py-1.5 font-mono text-2xs text-ink-faint">
                    {candidate.proxy_rank}
                  </td>
                  <td className="px-1.5 py-1.5">
                    <span className="font-mono text-2xs text-ink">
                      {candidate.residue_id}
                    </span>
                    <span className="ml-1.5 text-2xs text-ink-muted">
                      {candidate.residue_type}
                    </span>
                    {oov && (
                      <Tooltip
                        width="lg"
                        content={
                          <span>
                            <strong className="text-warn">
                              Outside the model vocabulary.
                            </strong>{' '}
                            The encoder only saw 14 of 20 amino acids, so{' '}
                            {candidate.residue_type} is encoded as an all-zero block.
                            The model still returns a number, but it carries no
                            information about this residue type. Excluded from the
                            protein-level mean.
                          </span>
                        }
                      >
                        <AlertTriangle
                          className="ml-1 inline h-3 w-3 text-warn"
                          aria-label="Outside model vocabulary"
                        />
                      </Tooltip>
                    )}
                  </td>
                  <td className="tabular px-1.5 py-1.5 font-mono text-2xs text-ink-muted">
                    {fmtNumber(candidate.residue_sasa_norm, 2)}
                  </td>
                  <td className="tabular px-1.5 py-1.5 font-mono text-2xs text-ink-muted">
                    {candidate.residue_contact_count}
                  </td>
                  <td
                    className={cn(
                      'px-1.5 py-1.5 text-2xs capitalize',
                      SUSCEPTIBILITY_TONE[candidate.qualitative_susceptibility] ??
                        'text-ink-muted',
                    )}
                  >
                    {candidate.qualitative_susceptibility}
                  </td>
                  {predictions && (
                    <td className="tabular px-1.5 py-1.5 text-right font-mono text-2xs">
                      {prediction ? (
                        <span className={oov ? 'text-warn' : 'text-ink'}>
                          {fmtPercent(prediction.degradation_percent, 1)}
                        </span>
                      ) : (
                        <span className="text-ink-faint">—</span>
                      )}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {candidates[0]?.ranking_source === 'recomputed' && (
        <p className="text-2xs leading-relaxed text-warn">
          Ranking recomputed from the uploaded structure rather than read from the
          training reference table.
        </p>
      )}
    </div>
  )
}
