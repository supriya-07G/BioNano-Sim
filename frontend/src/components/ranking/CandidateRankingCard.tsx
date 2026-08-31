import { AlertTriangle, ArrowUpRight, CheckCircle2, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/components/ui/cn'
import type { CandidateObjectiveScore } from '@/services/ranking'

/**
 * One candidate's measured mechanics and where it landed.
 *
 * A candidate with no run that passed the dataset's quality gate renders as an
 * unresolved entry, not a low score. Nine of the thirteen screened domains are
 * in that state, and the distinction matters: a fold the pulling protocol could
 * not measure is not a fold that measured badly, and scoring it 0 would assert
 * the second.
 */
export function CandidateRankingCard({
  candidate,
}: {
  candidate: CandidateObjectiveScore
}) {
  if (!candidate.resolved) {
    return <UnresolvedCandidate candidate={candidate} />
  }

  const isTopRank = candidate.rank === 1
  const isTop3 = (candidate.rank ?? 99) <= 3
  const score = candidate.composite_score ?? 0
  const spreadPct = candidate.relative_sd !== null ? candidate.relative_sd * 100 : null

  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-2xl border bg-surface p-5 transition-all hover:shadow-xl',
        candidate.is_pareto_optimal
          ? 'border-accent/50 bg-gradient-to-br from-surface via-surface to-accent/5 shadow-md'
          : 'border-hairline hover:border-hairline-bright',
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline/60 pb-3">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-mono text-base font-bold shadow-sm',
              isTopRank
                ? 'bg-amber-500 text-white ring-4 ring-amber-500/20'
                : isTop3
                  ? 'bg-accent text-white'
                  : 'border border-hairline bg-elevated text-ink-muted',
            )}
          >
            #{candidate.rank}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-bold text-ink transition-colors group-hover:text-accent">
                {candidate.name}
              </h3>
              <span className="rounded-md border border-hairline bg-elevated px-2 py-0.5 font-mono text-xs font-semibold text-ink-muted">
                {candidate.pdb_id}
              </span>
            </div>
            <p className="text-2xs text-ink-muted">UniProt: {candidate.uniprot}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {candidate.is_pareto_optimal && (
            <span className="flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-2xs font-extrabold text-amber-500 shadow-sm">
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              PARETO OPTIMAL
            </span>
          )}
          <span className="flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-2xs font-semibold text-emerald-500">
            <CheckCircle2 className="h-3 w-3" aria-hidden />
            {candidate.runs_passing_qc}/{candidate.runs_screened} runs passed QC
          </span>
        </div>
      </div>

      <div className="my-4 rounded-xl border border-hairline/80 bg-elevated/60 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-ink-muted">
            Composite score
          </span>
          <span className="tabular font-mono text-xl font-black text-accent">
            {score.toFixed(1)}{' '}
            <span className="text-2xs font-normal text-ink-muted">/ 100</span>
          </span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-void/60">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              isTopRank
                ? 'bg-gradient-to-r from-amber-500 to-accent'
                : score > 75
                  ? 'bg-accent'
                  : 'bg-sky-500',
            )}
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat
          label="Baseline stiffness"
          value={
            candidate.baseline_stiffness_pnnm !== null
              ? `${candidate.baseline_stiffness_pnnm.toFixed(0)} pN/nm`
              : '—'
          }
          note={
            candidate.baseline_stiffness_sd !== null
              ? `± ${candidate.baseline_stiffness_sd.toFixed(0)} across seeds`
              : 'pristine structure'
          }
        />
        <Stat
          label="Stiffness retained"
          value={
            candidate.stiffness_retained_pct !== null
              ? `${candidate.stiffness_retained_pct.toFixed(1)}%`
              : '—'
          }
          note={
            candidate.stiffness_retained_pct !== null &&
            candidate.stiffness_retained_pct >= 100
              ? 'no measurable loss'
              : 'after damage'
          }
        />
        <Stat
          label="Fit quality"
          value={
            candidate.mean_fit_quality !== null
              ? `R² ${candidate.mean_fit_quality.toFixed(2)}`
              : '—'
          }
          note="force-extension linearity"
        />
      </div>

      {/*
        The seed spread is the honest uncertainty here and it is large -- 15 to
        25% of the mean even for domains that resolve cleanly. It is surfaced
        whenever it is material rather than hidden behind a threshold.
      */}
      {spreadPct !== null && spreadPct >= 10 && (
        <div className="mb-4 flex flex-wrap gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 text-amber-600">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
          <p className="text-2xs leading-relaxed">
            Seed-to-seed spread is {spreadPct.toFixed(0)}% of the mean
            {candidate.penalties.seed_spread
              ? `, costing ${candidate.penalties.seed_spread.toFixed(1)} pts`
              : ''}
            . Differences between candidates smaller than this are not resolvable at{' '}
            {candidate.runs_passing_qc} runs.
          </p>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline/50 pt-3 text-2xs text-ink-muted">
        <p className="flex-1 leading-relaxed">{candidate.explanation}</p>
        <Link
          to={`/results/${candidate.pdb_id}`}
          className="flex items-center gap-1 font-semibold text-accent transition-colors hover:text-accent-deep"
        >
          <span>View experiment</span>
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </div>
    </div>
  )
}

function UnresolvedCandidate({ candidate }: { candidate: CandidateObjectiveScore }) {
  return (
    <div className="rounded-2xl border border-hairline bg-surface/60 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-hairline bg-elevated text-ink-faint">
            <AlertTriangle className="h-4 w-4" aria-hidden />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-bold text-ink-muted">{candidate.name}</h3>
              <span className="rounded-md border border-hairline bg-elevated px-2 py-0.5 font-mono text-xs font-semibold text-ink-faint">
                {candidate.pdb_id}
              </span>
            </div>
            <p className="text-2xs text-ink-faint">
              Not ranked · 0 of {candidate.runs_screened} runs passed QC
            </p>
          </div>
        </div>
        {candidate.qc_failure_reasons.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {candidate.qc_failure_reasons.map((reason) => (
              <span
                key={reason}
                className="rounded-md border border-hairline bg-raised px-2 py-0.5 text-3xs text-ink-faint"
              >
                {reason}
              </span>
            ))}
          </div>
        )}
      </div>
      {candidate.unresolved_reason && (
        <p className="mt-3 border-t border-hairline/50 pt-3 text-2xs leading-relaxed text-ink-muted">
          {candidate.unresolved_reason}
        </p>
      )}
    </div>
  )
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-lg border border-hairline/60 bg-void/30 p-2.5">
      <span className="block text-3xs font-semibold uppercase text-ink-faint">{label}</span>
      <span className="tabular font-mono text-sm font-bold text-ink">{value}</span>
      <span className="mt-0.5 block text-3xs text-ink-muted">{note}</span>
    </div>
  )
}
