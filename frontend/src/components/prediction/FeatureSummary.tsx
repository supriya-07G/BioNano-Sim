import { BarChart3 } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import type { FeatureImportance } from '@/types/prediction'
import { fmtNumber } from '@/utils/formatters'

/**
 * What the model actually keys on.
 *
 * Showing this is the clearest way to make the dose/scenario distinction
 * concrete: `radiation_class` and `scenario_id` together account for roughly
 * two thirds of the model's importance, and there is no dose feature at all.
 */
export function FeatureSummary({
  importances,
  className,
}: {
  importances: FeatureImportance[]
  className?: string
}) {
  if (importances.length === 0) return null
  const max = Math.max(...importances.map((item) => item.importance)) || 1

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <BarChart3 className="h-3 w-3" aria-hidden />
          What the model keys on
        </span>
        <Tooltip
          width="lg"
          content={
            <span>
              Gain-based feature importance from the trained gradient-boosted trees,
              over the 33 one-hot-expanded features. Note there is no dose, duration,
              temperature or force feature: radiation reaches the model only through
              the categorical scenario fields.
            </span>
          }
        />
      </div>

      <ul className="space-y-1.5">
        {importances.map((item) => (
          <li key={item.feature}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate font-mono text-2xs text-ink-muted">
                {item.feature}
              </span>
              <span className="tabular shrink-0 font-mono text-2xs text-ink-faint">
                {fmtNumber(item.importance * 100, 1)}%
              </span>
            </div>
            <div className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-void">
              <div
                className={
                  item.group === 'categorical' ? 'h-full bg-violet' : 'h-full bg-accent'
                }
                style={{ width: `${(item.importance / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-2 flex items-center gap-3">
        <span className="flex items-center gap-1 text-2xs text-ink-faint">
          <span className="h-1.5 w-3 rounded bg-violet" aria-hidden /> categorical
        </span>
        <span className="flex items-center gap-1 text-2xs text-ink-faint">
          <span className="h-1.5 w-3 rounded bg-accent" aria-hidden /> numeric
        </span>
      </div>
    </div>
  )
}
