import { ShieldCheck, AlertTriangle, AlertCircle, HelpCircle, Layers, TrendingUp, Sparkles, ArrowRightLeft } from 'lucide-react'
import { cn } from '@/components/ui/cn'

export interface UncertaintyBounds {
  sigma: number
  lower_bound_pct: number
  upper_bound_pct: number
  confidence_level: string
}

export interface ApplicabilityDomain {
  classification: 'IN_DOMAIN' | 'CAUTION' | 'OUT_OF_DOMAIN' | string
  score: number
  reasons: string[]
}

export interface TrainingNeighbor {
  pdb_id: string
  name: string
  similarity_pct: number
  distance: number
}

export interface FeatureAttribution {
  feature: string
  value: string
  contribution: number
  direction: 'increase' | 'decrease'
}

interface ExplainabilityPanelProps {
  uncertaintyBounds?: UncertaintyBounds
  applicabilityDomain?: ApplicabilityDomain
  nearestNeighbors?: TrainingNeighbor[]
  localAttributions?: FeatureAttribution[]
  globalImportance?: Record<string, number>
  attributionDisclaimer?: string
  degradationPercent?: number
  className?: string
}

export function ExplainabilityPanel({
  uncertaintyBounds,
  applicabilityDomain,
  nearestNeighbors = [],
  localAttributions = [],
  globalImportance = {},
  attributionDisclaimer,
  degradationPercent = 0.0,
  className,
}: ExplainabilityPanelProps) {
  const isDomainOk = applicabilityDomain?.classification === 'IN_DOMAIN'
  const isCaution = applicabilityDomain?.classification === 'CAUTION'

  return (
    <section className={cn('card p-5 space-y-6', className)}>
      {/* Title Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-ink">Explainability & Applicability Domain</h3>
            <p className="text-2xs text-ink-muted">Uncertainty intervals, local feature attributions, and training set proximity</p>
          </div>
        </div>

        {/* Applicability Domain Badge */}
        {applicabilityDomain && (
          <div
            className={cn(
              'flex items-center gap-1.5 rounded-full px-3 py-1 text-2xs font-extrabold shadow-2xs border',
              isDomainOk
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500'
                : isCaution
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-500'
                  : 'border-danger/40 bg-danger/10 text-danger',
            )}
          >
            {isDomainOk && <ShieldCheck className="h-3.5 w-3.5" />}
            {isCaution && <AlertTriangle className="h-3.5 w-3.5" />}
            {!isDomainOk && !isCaution && <AlertCircle className="h-3.5 w-3.5" />}
            <span>DOMAIN: {applicabilityDomain.classification}</span>
          </div>
        )}
      </div>

      {/* 1. Prediction Interval & Uncertainty Bounds */}
      {uncertaintyBounds && (
        <div className="rounded-xl border border-hairline/80 bg-elevated/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
              <TrendingUp className="h-3.5 w-3.5 text-accent" />
              Prediction Interval ({uncertaintyBounds.confidence_level ?? '95%'} Confidence)
            </span>
            <span className="font-mono text-xs font-bold text-accent">
              {degradationPercent.toFixed(1)}% ± {uncertaintyBounds.sigma.toFixed(1)}%
            </span>
          </div>
          <p className="text-2xs text-ink-muted mb-3">
            Expected 95% confidence interval: [{uncertaintyBounds.lower_bound_pct.toFixed(1)}%, {uncertaintyBounds.upper_bound_pct.toFixed(1)}%]
          </p>
          <div className="relative h-2 w-full rounded-full bg-void/60 overflow-hidden">
            <div
              className="absolute h-full bg-accent/30 rounded-full"
              style={{
                left: `${Math.max(0, uncertaintyBounds.lower_bound_pct)}%`,
                width: `${Math.min(100, uncertaintyBounds.upper_bound_pct - uncertaintyBounds.lower_bound_pct)}%`,
              }}
            />
            <div
              className="absolute h-full w-1.5 bg-accent rounded-full -translate-x-1/2"
              style={{ left: `${Math.min(100, Math.max(0, degradationPercent))}%` }}
            />
          </div>
        </div>
      )}

      {/* 2. Local Feature Attributions */}
      {localAttributions.length > 0 && (
        <div>
          <h4 className="text-xs font-bold uppercase text-ink mb-3 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-accent" />
            Local Feature Contributions
          </h4>
          <div className="space-y-2">
            {localAttributions.map((attr) => {
              const isPos = attr.direction === 'increase'
              return (
                <div key={attr.feature} className="flex items-center justify-between rounded-lg border border-hairline/60 bg-void/20 px-3 py-2 text-2xs">
                  <div className="min-w-0 flex-1">
                    <span className="font-mono font-bold text-ink">{attr.feature}</span>
                    <span className="ml-2 text-ink-muted">({attr.value})</span>
                  </div>
                  <div className={cn('font-mono font-bold shrink-0', isPos ? 'text-amber-500' : 'text-emerald-500')}>
                    {isPos ? '+' : ''}{attr.contribution.toFixed(2)}%
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 3. Global Feature Importances */}
      {Object.keys(globalImportance).length > 0 && (
        <div>
          <h4 className="text-xs font-bold uppercase text-ink mb-3 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-accent" />
            Global Model Feature Importance
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(globalImportance).map(([feat, imp]) => (
              <div key={feat} className="rounded-lg border border-hairline/60 bg-void/20 p-2 text-2xs">
                <span className="font-mono text-ink font-semibold block truncate">{feat}</span>
                <span className="font-mono text-accent font-bold">{(imp * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Nearest Training Neighbors */}
      {nearestNeighbors.length > 0 && (
        <div>
          <h4 className="text-xs font-bold uppercase text-ink mb-3 flex items-center gap-1.5">
            <ArrowRightLeft className="h-3.5 w-3.5 text-accent" />
            Nearest Training Dataset Neighbors
          </h4>
          <div className="overflow-x-auto rounded-xl border border-hairline/60">
            <table className="w-full text-left text-2xs">
              <thead className="border-b border-hairline/60 bg-elevated/60 text-ink-muted">
                <tr>
                  <th className="px-3 py-2 font-semibold">PDB ID</th>
                  <th className="px-3 py-2 font-semibold">Domain Name</th>
                  <th className="px-3 py-2 font-semibold">Similarity</th>
                  <th className="px-3 py-2 font-semibold">Distance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline/40">
                {nearestNeighbors.map((n) => (
                  <tr key={n.pdb_id} className="hover:bg-raised/50 transition-colors">
                    <td className="px-3 py-2 font-mono font-bold text-accent">{n.pdb_id}</td>
                    <td className="px-3 py-2 text-ink">{n.name}</td>
                    <td className="px-3 py-2 font-mono text-emerald-500 font-semibold">{n.similarity_pct}%</td>
                    <td className="px-3 py-2 font-mono text-ink-muted">{n.distance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Attribution Disclaimer Notice */}
      {attributionDisclaimer && (
        <div className="rounded-lg border border-hairline/80 bg-void/40 p-3 text-3xs text-ink-faint flex items-start gap-2">
          <HelpCircle className="h-3.5 w-3.5 shrink-0 text-ink-muted mt-0.5" />
          <p className="leading-relaxed">{attributionDisclaimer}</p>
        </div>
      )}
    </section>
  )
}
