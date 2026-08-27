import { ArrowRight, GitCompare, Scale } from 'lucide-react'

import { ScientificNotice } from '@/components/common/ScientificNotice'
import { ResultLabel } from '@/components/common/StatusBadge'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { ComparisonBlock, DegradationProxy } from '@/types/simulation'
import { fmtDelta, fmtNumber, fmtPercent } from '@/utils/formatters'

const AGREEMENT_TONE = {
  close: 'border-ok/40 bg-ok/10 text-ok',
  moderate: 'border-warn/40 bg-warn/10 text-warn',
  divergent: 'border-danger/40 bg-danger/10 text-danger',
  unavailable: 'border-hairline bg-elevated text-ink-faint',
} as const

/**
 * ML prediction versus simulation proxy.
 *
 * The most important thing this panel does is refuse to present the two numbers
 * as the same quantity. They are on different scales, built from different
 * inputs, and neither is validated — so the difference measures disagreement
 * between two proxies, not accuracy.
 */
export function ComparisonPanel({
  comparison,
  proxy,
  className,
}: {
  comparison: ComparisonBlock
  proxy?: DegradationProxy
  className?: string
}) {
  const hasBoth =
    comparison.ml_degradation_percent !== null &&
    comparison.simulation_degradation_proxy_percent !== null

  return (
    <section className={cn('card p-4', className)}>
      <header className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium text-ink">
          <GitCompare className="h-4 w-4 text-accent" aria-hidden />
          ML prediction vs simulation
        </h2>
        <span className={cn('badge', AGREEMENT_TONE[comparison.agreement])}>
          {comparison.agreement}
        </span>
      </header>

      <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr]">
        <ValueBlock
          label={comparison.ml_label}
          kind="ml_prediction"
          value={comparison.ml_degradation_percent}
          caption="Mean over ranked candidate residues, from the MVP bootstrap model."
        />

        <div className="flex items-center justify-center">
          <div className="flex flex-col items-center gap-1">
            <ArrowRight className="h-4 w-4 text-ink-faint sm:rotate-0" aria-hidden />
            <span className="tabular whitespace-nowrap font-mono text-xs text-ink">
              {fmtDelta(comparison.difference_percentage_points)}
            </span>
          </div>
        </div>

        <ValueBlock
          label={comparison.simulation_label}
          kind="proxy"
          value={comparison.simulation_degradation_proxy_percent}
          caption="Structural-drift score computed by BioNano-Sim from the trajectory."
        />
      </div>

      {comparison.agreement_note && (
        <p className="mt-3 text-2xs leading-relaxed text-ink-muted">
          {comparison.agreement_note}
        </p>
      )}

      {/* Proxy breakdown: the formula and each component's contribution. */}
      {proxy && (
        <div className="mt-3 rounded-lg border border-hairline bg-void/50 p-2.5">
          <div className="mb-2 flex items-center gap-1.5">
            <Scale className="h-3 w-3 text-ink-faint" aria-hidden />
            <span className="text-2xs font-medium text-ink-muted">
              How the proxy is calculated
            </span>
            <Tooltip
              width="lg"
              content={
                <span>
                  A weighted, bounded combination of three trajectory observables, each
                  normalised against a reference scale. The reference scales are{' '}
                  <strong>engineering constants chosen for this MVP</strong>, not
                  physical constants — changing them changes the number without
                  changing the underlying physics.
                </span>
              }
            />
          </div>

          <code className="block overflow-x-auto whitespace-pre rounded border border-hairline bg-void p-2 font-mono text-2xs leading-relaxed text-ink-muted">
            {proxy.formula}
          </code>

          <table className="mt-2 w-full text-left">
            <thead>
              <tr>
                <th className="pb-1 text-2xs font-medium text-ink-faint">Term</th>
                <th className="pb-1 text-right text-2xs font-medium text-ink-faint">
                  Value
                </th>
                <th className="pb-1 text-right text-2xs font-medium text-ink-faint">
                  Weight
                </th>
                <th className="pb-1 text-right text-2xs font-medium text-ink-faint">
                  Contribution
                </th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(proxy.components).map(([name, component]) => (
                <tr key={name} className="border-t border-hairline/50">
                  <td className="py-1 font-mono text-2xs text-ink-muted">
                    {name.replace(/_/g, ' ')}
                  </td>
                  <td className="tabular py-1 text-right font-mono text-2xs text-ink-muted">
                    {fmtNumber(component.normalised, 3)}
                  </td>
                  <td className="tabular py-1 text-right font-mono text-2xs text-ink-faint">
                    {fmtNumber(component.weight, 2)}
                  </td>
                  <td className="tabular py-1 text-right font-mono text-2xs text-ink">
                    {fmtPercent(component.contribution_percent, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ScientificNotice
        title="What this comparison does and does not tell you"
        variant="caution"
        className="mt-3"
        compact
      >
        <p>{comparison.interpretation}</p>
      </ScientificNotice>

      {!hasBoth && (
        <p className="mt-2 text-2xs text-warn">
          {comparison.agreement_note ??
            'Only one of the two figures is available, so no difference can be computed.'}
        </p>
      )}
    </section>
  )
}

function ValueBlock({
  label,
  kind,
  value,
  caption,
}: {
  label: string
  kind: 'ml_prediction' | 'proxy'
  value: number | null
  caption: string
}) {
  return (
    <div className="rounded-lg border border-hairline bg-void/50 p-3">
      <ResultLabel kind={kind} override={label} />
      <p className="tabular mt-2 font-mono text-2xl text-ink">{fmtPercent(value, 1)}</p>
      <p className="mt-1 text-2xs leading-relaxed text-ink-faint">{caption}</p>
    </div>
  )
}
