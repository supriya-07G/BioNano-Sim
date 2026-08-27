import { Layers, Loader2, Play, Sparkles } from 'lucide-react'

import { ConfidencePanel } from './ConfidencePanel'
import { FeatureSummary } from './FeatureSummary'
import { RiskGauge } from './RiskGauge'
import { ErrorState } from '@/components/common/ErrorState'
import { ScientificNotice } from '@/components/common/ScientificNotice'
import { ResultLabel } from '@/components/common/StatusBadge'
import { Tooltip } from '@/components/ui/Tooltip'
import type { ModelInfo, PredictionResponse } from '@/types/prediction'
import { fmtNumber, fmtPercent, shortId } from '@/utils/formatters'

interface PredictionCardProps {
  prediction: PredictionResponse | undefined
  model: ModelInfo | undefined
  isPending: boolean
  error: unknown
  onPredict: () => void
  onRunSimulation: () => void
  canPredict: boolean
  canSimulate: boolean
  simulationBlockedReason?: string | null
  predictBlockedReason?: string | null
}

export function PredictionCard({
  prediction,
  model,
  isPending,
  error,
  onPredict,
  onRunSimulation,
  canPredict,
  canSimulate,
  simulationBlockedReason,
  predictBlockedReason,
}: PredictionCardProps) {
  return (
    <div className="space-y-4">
      {/* Header: the honest label comes first, before any number. */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ResultLabel kind="ml_prediction" />
          <span className="badge border-warn/40 bg-warn/10 text-warn">MVP model</span>
        </div>
        {model && (
          <span className="font-mono text-2xs text-ink-faint">
            v{model.model_version}
          </span>
        )}
      </div>

      {!prediction && !isPending && !error && (
        <div className="rounded-lg border border-dashed border-hairline p-4 text-center">
          <p className="text-xs text-ink-muted">
            No estimate yet. Run the prediction to get a degradation estimate before
            starting a simulation.
          </p>
          <button
            type="button"
            className="btn-primary mt-3 !text-xs"
            onClick={onPredict}
            disabled={!canPredict}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            Estimate degradation
          </button>
          {predictBlockedReason && (
            <p className="mt-2 text-2xs text-warn">{predictBlockedReason}</p>
          )}
        </div>
      )}

      {isPending && (
        <div className="flex items-center justify-center gap-2 rounded-lg border border-hairline bg-void/50 p-6">
          <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden />
          <span className="text-xs text-ink-muted">Running inference&hellip;</span>
        </div>
      )}

      {Boolean(error) && (
        <ErrorState error={error} title="Prediction failed" onRetry={onPredict} />
      )}

      {prediction && !isPending && (
        <>
          <RiskGauge
            percent={prediction.degradation_percent}
            level={prediction.risk_level}
          />

          {/* Aggregation: the headline number is derived, and says so. */}
          <div className="rounded-lg border border-hairline bg-void/50 p-2.5">
            <div className="mb-1.5 flex items-center gap-1.5">
              <Layers className="h-3 w-3 text-ink-faint" aria-hidden />
              <span className="text-2xs font-medium text-ink-muted">
                How this number was built
              </span>
              <Tooltip width="lg" content={prediction.aggregation.explanation} />
            </div>
            <dl className="tabular grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-2xs">
              <Row
                label="Residues scored"
                value={`${prediction.aggregation.n_residues_predicted}`}
              />
              <Row
                label="Used in mean"
                value={`${prediction.aggregation.n_residues_used_in_mean}`}
              />
              <Row
                label="Per-residue range"
                value={`${fmtNumber(prediction.aggregation.per_residue_min, 1)}–${fmtNumber(
                  prediction.aggregation.per_residue_max,
                  1,
                )}%`}
              />
              <Row
                label="Spread (σ)"
                value={`${fmtNumber(prediction.aggregation.per_residue_std, 2)} pp`}
              />
            </dl>
            <p className="mt-2 text-2xs leading-relaxed text-ink-faint">
              The model&rsquo;s target is <strong>per residue</strong>. This figure is
              the mean over the highest-susceptibility candidates, so it leans high
              relative to the whole chain.
            </p>
            {prediction.aggregation.exclusion_note && (
              <p className="mt-1.5 text-2xs leading-relaxed text-warn">
                {prediction.aggregation.exclusion_note}
              </p>
            )}
          </div>

          <ConfidencePanel
            confidence={prediction.confidence}
            note={prediction.held_out_error.note}
            validation={prediction.held_out_error.validation}
            test={prediction.held_out_error.test}
          />

          {model && model.top_feature_importances.length > 0 && (
            <>
              <div className="hairline-divider" />
              <FeatureSummary importances={model.top_feature_importances.slice(0, 6)} />
            </>
          )}

          <div className="hairline-divider" />

          <ScientificNotice
            title="Limitations of this estimate"
            variant="caution"
            collapsible
            defaultOpen={false}
            items={prediction.warnings}
            compact
          />

          <div className="flex items-center justify-between gap-2 text-2xs text-ink-faint">
            <span className="font-mono">
              prediction {shortId(prediction.prediction_id)}
            </span>
            <span className="font-mono">{prediction.model_status}</span>
          </div>

          <button
            type="button"
            className="btn-primary w-full"
            onClick={onRunSimulation}
            disabled={!canSimulate}
          >
            <Play className="h-4 w-4" aria-hidden />
            Run rapid simulation
          </button>
          {simulationBlockedReason && (
            <p className="text-center text-2xs text-warn">{simulationBlockedReason}</p>
          )}

          <button
            type="button"
            className="btn-ghost w-full !text-xs"
            onClick={onPredict}
            disabled={!canPredict}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            Re-run estimate
          </button>
        </>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="truncate text-ink">{value}</dd>
    </div>
  )
}

/** Compact variant used on the dashboard's comparison cards. */
export function PredictionMini({
  percent,
  level,
  label,
}: {
  percent: number | null
  level: 'low' | 'moderate' | 'elevated' | 'high' | null
  label: string
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="truncate text-2xs text-ink-faint">{label}</span>
      <span className="tabular shrink-0 font-mono text-xs text-ink">
        {fmtPercent(percent, 1)}
        {level && <span className="ml-1.5 text-2xs text-ink-faint">{level}</span>}
      </span>
    </div>
  )
}
