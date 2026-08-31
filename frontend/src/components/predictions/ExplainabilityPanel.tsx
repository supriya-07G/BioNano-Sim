import {
  AlertCircle,
  AlertTriangle,
  ArrowRightLeft,
  HelpCircle,
  Layers,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from 'lucide-react'

import { cn } from '@/components/ui/cn'

/**
 * What the model used, and how confident that makes anyone.
 *
 * Every figure rendered here is computed by the backend from the fitted
 * pipeline or the measured dataset. The panel's job is to keep the labels
 * honest about which is which: an exact SHAP contribution and an observed
 * spread of predictions are different kinds of number, and only one of them is
 * an uncertainty.
 */

export interface PredictionDispersion {
  available: boolean
  note: string
  basis?: string
  sd?: number
  min_pct?: number
  max_pct?: number
  mean_pct?: number
  n_residues?: number
}

export interface ApplicabilityDomain {
  classification: 'IN_VOCABULARY' | 'CAUTION' | 'OUT_OF_DOMAIN' | string
  basis: string
  reasons: string[]
  note: string
}

export interface MeasuredNeighbor {
  pdb_id: string
  distance: number
  baseline_stiffness_pnnm: number
  resolved: boolean
}

export interface FeatureAttribution {
  feature: string
  value: string | number | null
  contribution: number
  direction: 'increase' | 'decrease'
}

interface ExplainabilityPanelProps {
  dispersion?: PredictionDispersion
  applicabilityDomain?: ApplicabilityDomain
  nearestNeighbors?: MeasuredNeighbor[]
  localAttributions?: FeatureAttribution[]
  globalImportance?: Record<string, number>
  attributionDisclaimer?: string
  degradationPercent?: number
  className?: string
}

export function ExplainabilityPanel({
  dispersion,
  applicabilityDomain,
  nearestNeighbors = [],
  localAttributions = [],
  globalImportance = {},
  attributionDisclaimer,
  degradationPercent = 0.0,
  className,
}: ExplainabilityPanelProps) {
  const isDomainOk = applicabilityDomain?.classification === 'IN_VOCABULARY'
  const isCaution = applicabilityDomain?.classification === 'CAUTION'

  // Contributions are on the target's own scale (percentage points of
  // degradation), so the bars are sized against the largest one present rather
  // than against 100.
  const maxContribution = localAttributions.reduce(
    (peak, attr) => Math.max(peak, Math.abs(attr.contribution)),
    0,
  )

  return (
    <section className={cn('card space-y-6 p-5', className)}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Sparkles className="h-4 w-4" aria-hidden />
          </div>
          <div>
            <h3 className="text-sm font-bold text-ink">Explainability and applicability</h3>
            <p className="text-2xs text-ink-muted">
              Exact SHAP contributions, prediction spread, and proximity to measured proteins
            </p>
          </div>
        </div>

        {applicabilityDomain && (
          <div
            className={cn(
              'flex items-center gap-1.5 rounded-full border px-3 py-1 text-2xs font-extrabold shadow-2xs',
              isDomainOk
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500'
                : isCaution
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-500'
                  : 'border-danger/40 bg-danger/10 text-danger',
            )}
            title={applicabilityDomain.note}
          >
            {isDomainOk && <ShieldCheck className="h-3.5 w-3.5" aria-hidden />}
            {isCaution && <AlertTriangle className="h-3.5 w-3.5" aria-hidden />}
            {!isDomainOk && !isCaution && <AlertCircle className="h-3.5 w-3.5" aria-hidden />}
            <span>{applicabilityDomain.classification.replace(/_/g, ' ')}</span>
          </div>
        )}
      </div>

      {/*
        Spread, not an interval. The old version drew a +/- 1.96 sigma band and
        called it 95% confidence; the model carries no calibrated uncertainty,
        so there is no coverage to claim. What is shown is the observed range of
        the per-residue predictions that were averaged.
      */}
      {dispersion?.available && dispersion.sd !== undefined && (
        <div className="rounded-xl border border-hairline/80 bg-elevated/50 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-ink-muted">
              <TrendingUp className="h-3.5 w-3.5 text-accent" aria-hidden />
              Spread across {dispersion.n_residues} candidate residues
            </span>
            <span className="tabular font-mono text-xs font-bold text-accent">
              {degradationPercent.toFixed(1)}% (SD {dispersion.sd.toFixed(1)})
            </span>
          </div>
          <p className="mb-3 text-2xs text-ink-muted">
            Observed range {dispersion.min_pct?.toFixed(1)}% to {dispersion.max_pct?.toFixed(1)}%.
            This is how much the per-residue predictions differ from one another, not a
            confidence interval.
          </p>
          {dispersion.min_pct !== undefined && dispersion.max_pct !== undefined && (
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-void/60">
              <div
                className="absolute h-full rounded-full bg-accent/30"
                style={{
                  left: `${Math.max(0, Math.min(100, dispersion.min_pct))}%`,
                  width: `${Math.max(0, Math.min(100, dispersion.max_pct - dispersion.min_pct))}%`,
                }}
              />
              <div
                className="absolute h-full w-1.5 -translate-x-1/2 rounded-full bg-accent"
                style={{ left: `${Math.min(100, Math.max(0, degradationPercent))}%` }}
              />
            </div>
          )}
        </div>
      )}

      {dispersion && !dispersion.available && (
        <p className="rounded-lg border border-hairline/80 bg-void/40 p-3 text-2xs leading-relaxed text-ink-faint">
          {dispersion.note}
        </p>
      )}

      {localAttributions.length > 0 && (
        <div>
          <h4 className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase text-ink">
            <Layers className="h-3.5 w-3.5 text-accent" aria-hidden />
            Feature contributions for this prediction
          </h4>
          <p className="mb-3 text-2xs text-ink-faint">
            Exact tree SHAP values for the top-ranked candidate residue, in percentage
            points of predicted degradation.
          </p>
          <div className="space-y-2">
            {localAttributions.map((attr) => {
              const isPos = attr.direction === 'increase'
              const width = maxContribution
                ? (Math.abs(attr.contribution) / maxContribution) * 100
                : 0
              return (
                <div
                  key={attr.feature}
                  className="rounded-lg border border-hairline/60 bg-void/20 px-3 py-2 text-2xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 flex-1 truncate font-mono font-bold text-ink">
                      {attr.feature}
                      {attr.value !== null && attr.value !== undefined && (
                        <span className="ml-2 font-normal text-ink-muted">
                          = {typeof attr.value === 'number' ? attr.value.toFixed(3) : attr.value}
                        </span>
                      )}
                    </span>
                    <span
                      className={cn(
                        'tabular shrink-0 font-mono font-bold',
                        isPos ? 'text-amber-500' : 'text-emerald-500',
                      )}
                    >
                      {isPos ? '+' : ''}
                      {attr.contribution.toFixed(2)}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-void/60">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        isPos ? 'bg-amber-500/50' : 'bg-emerald-500/50',
                      )}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {Object.keys(globalImportance).length > 0 && (
        <div>
          <h4 className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase text-ink">
            <Layers className="h-3.5 w-3.5 text-accent" aria-hidden />
            Global model feature importance
          </h4>
          <p className="mb-3 text-2xs text-ink-faint">
            The fitted estimator&rsquo;s own importances, across all training data.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.entries(globalImportance).map(([feat, imp]) => (
              <div
                key={feat}
                className="rounded-lg border border-hairline/60 bg-void/20 p-2 text-2xs"
              >
                <span className="block truncate font-mono font-semibold text-ink" title={feat}>
                  {feat}
                </span>
                <span className="tabular font-mono font-bold text-accent">
                  {(imp * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/*
        Distance, not similarity. The scaled descriptor distance has no
        principled mapping onto a percentage, and the invented one used to
        report titin as 86% similar to itself.
      */}
      {nearestNeighbors.length > 0 && (
        <div>
          <h4 className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase text-ink">
            <ArrowRightLeft className="h-3.5 w-3.5 text-accent" aria-hidden />
            Nearest measured proteins
          </h4>
          <p className="mb-3 text-2xs text-ink-faint">
            Closest domains in the measured dataset by scaled sequence-descriptor distance.
            Smaller is nearer. This is proximity in the model&rsquo;s input space, not
            structural or evolutionary similarity.
          </p>
          <div className="overflow-x-auto rounded-xl border border-hairline/60">
            <table className="w-full text-left text-2xs">
              <thead className="border-b border-hairline/60 bg-elevated/60 text-ink-muted">
                <tr>
                  <th className="px-3 py-2 font-semibold">PDB ID</th>
                  <th className="px-3 py-2 font-semibold">Distance</th>
                  <th className="px-3 py-2 font-semibold">Measured stiffness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline/40">
                {nearestNeighbors.map((n) => (
                  <tr key={n.pdb_id} className="transition-colors hover:bg-raised/50">
                    <td className="px-3 py-2 font-mono font-bold text-accent">{n.pdb_id}</td>
                    <td className="tabular px-3 py-2 font-mono text-ink-muted">
                      {n.distance.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 font-mono text-ink">
                      {n.resolved ? (
                        `${n.baseline_stiffness_pnnm.toFixed(0)} pN/nm`
                      ) : (
                        <span className="text-ink-faint">not resolved</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {attributionDisclaimer && (
        <div className="flex items-start gap-2 rounded-lg border border-hairline/80 bg-void/40 p-3 text-3xs text-ink-faint">
          <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-muted" aria-hidden />
          <p className="leading-relaxed">{attributionDisclaimer}</p>
        </div>
      )}
    </section>
  )
}
