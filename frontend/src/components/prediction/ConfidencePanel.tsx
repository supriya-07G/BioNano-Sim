import { HelpCircle, Target } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import type { HeldOutMetrics } from '@/types/prediction'
import { fmtNumber } from '@/utils/formatters'

interface ConfidencePanelProps {
  confidence: number | null
  note: string | null
  validation: HeldOutMetrics | null
  test: HeldOutMetrics | null
}

/**
 * Uncertainty reporting.
 *
 * The bundle exposes no calibrated uncertainty, so this panel says so plainly
 * instead of inventing a number. What it *can* offer is the model's retrospective
 * held-out error, clearly separated: those are dataset-level metrics on two
 * unseen proteins, not a per-prediction interval.
 */
export function ConfidencePanel({
  confidence,
  note,
  validation,
  test,
}: ConfidencePanelProps) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="label">Uncertainty</span>
        <Tooltip
          width="lg"
          content={
            note ??
            'The model bundle exposes no calibrated uncertainty, so no per-prediction confidence is reported.'
          }
        />
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-hairline bg-void/50 p-2.5">
        <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-faint" aria-hidden />
        <div className="min-w-0">
          <p className="text-xs text-ink">
            Per-prediction confidence:{' '}
            <span className="font-mono text-ink-muted">
              {confidence === null ? 'not available' : fmtNumber(confidence, 3)}
            </span>
          </p>
          <p className="mt-1 text-2xs leading-relaxed text-ink-faint">
            This model has no <code>predict_proba</code>, no quantile heads and no
            calibrated interval, so BioNano-Sim reports <code>null</code> rather than
            fabricating a figure.
          </p>
        </div>
      </div>

      {(validation || test) && (
        <div className="space-y-2 rounded-lg border border-hairline bg-void/50 p-2.5">
          <p className="flex items-center gap-1.5 text-2xs font-medium text-ink-muted">
            <Target className="h-3 w-3" aria-hidden />
            Held-out error (retrospective, dataset-level)
          </p>

          {validation && <MetricRow label="Validation" metrics={validation} />}
          {test && <MetricRow label="Test" metrics={test} />}

          <p className="text-2xs leading-relaxed text-ink-faint">
            Mean absolute error on proteins withheld from training, in percentage
            points. This describes how the model performed on those two proteins
            overall &mdash; it is <strong>not</strong> an error bar for the estimate
            above.
          </p>
        </div>
      )}
    </div>
  )
}

function MetricRow({ label, metrics }: { label: string; metrics: HeldOutMetrics }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-2xs text-ink-faint">
        {label}
        <span className="ml-1 font-mono">({metrics.proteins.join(', ')})</span>
      </span>
      <span className="tabular shrink-0 font-mono text-2xs text-ink">
        MAE {fmtNumber(metrics.mae, 2)} pp
        <span className="ml-2 text-ink-faint">R&sup2; {fmtNumber(metrics.r2, 3)}</span>
      </span>
    </div>
  )
}
