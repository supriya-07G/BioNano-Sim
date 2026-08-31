import { CheckCircle2, AlertTriangle, Sparkles, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CandidateObjectiveScore } from '@/services/ranking'
import { cn } from '@/components/ui/cn'

interface CandidateRankingCardProps {
  candidate: CandidateObjectiveScore
}

export function CandidateRankingCard({ candidate }: CandidateRankingCardProps) {
  const isTopRank = candidate.rank === 1
  const isTop3 = candidate.rank <= 3

  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-2xl border bg-surface p-5 transition-all hover:shadow-xl',
        candidate.is_pareto_optimal
          ? 'border-accent/50 bg-gradient-to-br from-surface via-surface to-accent/5 shadow-md'
          : 'border-hairline hover:border-hairline-bright',
      )}
    >
      {/* Top Banner / Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline/60 pb-3">
        <div className="flex items-center gap-3">
          {/* Rank Badge */}
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-mono text-base font-bold shadow-sm',
              isTopRank
                ? 'bg-amber-500 text-white ring-4 ring-amber-500/20'
                : isTop3
                  ? 'bg-accent text-white'
                  : 'bg-elevated text-ink-muted border border-hairline',
            )}
          >
            #{candidate.rank}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-ink group-hover:text-accent transition-colors">
                {candidate.name}
              </h3>
              <span className="rounded-md border border-hairline bg-elevated px-2 py-0.5 font-mono text-xs font-semibold text-ink-muted">
                {candidate.pdb_id}
              </span>
            </div>
            <p className="text-2xs text-ink-muted">UniProt: {candidate.uniprot}</p>
          </div>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2">
          {candidate.is_pareto_optimal && (
            <span className="flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-2xs font-extrabold text-amber-500 shadow-sm animate-pulse">
              <Sparkles className="h-3.5 w-3.5" />
              PARETO OPTIMAL
            </span>
          )}
          <span className="flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-2xs font-semibold text-emerald-500">
            <CheckCircle2 className="h-3 w-3" />
            {candidate.provenance.validation ?? 'EMPIRICAL'}
          </span>
        </div>
      </div>

      {/* Main Composite Score Bar */}
      <div className="my-4 rounded-xl border border-hairline/80 bg-elevated/60 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold uppercase tracking-wider text-ink-muted">
            Multi-Objective Composite Score
          </span>
          <span className="font-mono text-xl font-black text-accent">
            {candidate.composite_score.toFixed(1)} <span className="text-2xs text-ink-muted font-normal">/ 100</span>
          </span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-void/60">
          <div
            className={cn(
              'h-full transition-all duration-500 rounded-full',
              isTopRank
                ? 'bg-gradient-to-r from-amber-500 to-accent'
                : candidate.composite_score > 75
                  ? 'bg-accent'
                  : 'bg-sky-500',
            )}
            style={{ width: `${Math.min(100, candidate.composite_score)}%` }}
          />
        </div>
      </div>

      {/* Subscores Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        <div className="rounded-lg border border-hairline/60 bg-void/30 p-2.5">
          <span className="text-3xs font-semibold uppercase text-ink-faint block">Stiffness Retained</span>
          <span className="font-mono text-sm font-bold text-ink">{candidate.stiffness_retained_pct}%</span>
          <span className="text-3xs text-ink-muted block mt-0.5">Post-damage retention</span>
        </div>

        <div className="rounded-lg border border-hairline/60 bg-void/30 p-2.5">
          <span className="text-3xs font-semibold uppercase text-ink-faint block">Pristine Strength</span>
          <span className="font-mono text-sm font-bold text-ink">{candidate.baseline_stiffness_pnnm} pN/nm</span>
          <span className="text-3xs text-ink-muted block mt-0.5">Baseline load capacity</span>
        </div>

        <div className="rounded-lg border border-hairline/60 bg-void/30 p-2.5">
          <span className="text-3xs font-semibold uppercase text-ink-faint block">SASA Stability</span>
          <span className="font-mono text-sm font-bold text-ink">{candidate.sasa_preservation_pct}%</span>
          <span className="text-3xs text-ink-muted block mt-0.5">Fold compactness</span>
        </div>
      </div>

      {/* Penalty Alert Tags if applicable */}
      {(candidate.penalties.uncertainty > 10 || candidate.penalties.out_of_domain > 15) && (
        <div className="mb-4 flex flex-wrap gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 text-xs text-amber-600">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-500" />
          <div className="space-y-0.5 text-2xs">
            {candidate.penalties.uncertainty > 10 && (
              <p>Uncertainty Penalty: -{(candidate.penalties.uncertainty * 0.15).toFixed(1)} pts (σ = {candidate.uncertainty_sigma})</p>
            )}
            {candidate.penalties.out_of_domain > 15 && (
              <p>OOD Distance Penalty: -{(candidate.penalties.out_of_domain * 0.10).toFixed(1)} pts (dist = {candidate.ood_distance})</p>
            )}
          </div>
        </div>
      )}

      {/* Explanation Footer & Provenance */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline/50 pt-3 text-2xs text-ink-muted">
        <p className="flex-1 leading-relaxed">{candidate.explanation}</p>
        <Link
          to={`/results/${candidate.pdb_id}`}
          className="flex items-center gap-1 font-semibold text-accent hover:text-accent-deep transition-colors"
        >
          <span>View Experiment</span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  )
}
