import { useState } from 'react'
import { BarChart3, Loader2, RefreshCw, ShieldAlert, StopCircle } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { ScientificNotice } from '@/components/common/ScientificNotice'
import { cn } from '@/components/ui/cn'
import type { SimulationJobDetail } from '@/types/simulation'
import { isTerminal } from '@/types/simulation'

interface SimulationControlsProps {
  job: SimulationJobDetail
  onCancel: () => void
  onRetrySafe: (presetId: string) => void
  onViewResults: () => void
  onOpenPrecomputed?: () => void
  cancelPending: boolean
  retryPending: boolean
  precomputedAvailable?: boolean
  className?: string
}

export function SimulationControls({
  job,
  onCancel,
  onRetrySafe,
  onViewResults,
  onOpenPrecomputed,
  cancelPending,
  retryPending,
  precomputedAvailable = false,
  className,
}: SimulationControlsProps) {
  const [confirmCancel, setConfirmCancel] = useState(false)
  const running = !isTerminal(job.status)

  return (
    <div className={cn('space-y-3', className)}>
      {running && (
        <>
          {confirmCancel ? (
            <div className="rounded-lg border border-warn/35 bg-warn/[0.07] p-2.5">
              <p className="text-2xs leading-relaxed text-ink-muted">
                Cancel this run? The worker stops at its next step boundary, usually
                within a second. Partial artifacts are kept but the job will be marked
                cancelled, not completed.
              </p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className="btn-danger flex-1 !py-1.5 !text-xs"
                  onClick={() => {
                    setConfirmCancel(false)
                    onCancel()
                  }}
                  disabled={cancelPending}
                >
                  {cancelPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                  ) : (
                    <StopCircle className="h-3.5 w-3.5" aria-hidden />
                  )}
                  Confirm cancel
                </button>
                <button
                  type="button"
                  className="btn-ghost !py-1.5 !text-xs"
                  onClick={() => setConfirmCancel(false)}
                >
                  Keep running
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="btn-secondary w-full !text-xs"
              onClick={() => setConfirmCancel(true)}
            >
              <StopCircle className="h-3.5 w-3.5" aria-hidden />
              Cancel simulation
            </button>
          )}

          <p className="text-2xs leading-relaxed text-ink-faint">
            The run continues in the backend if you navigate away. Come back to this
            page, or open it from History, to keep watching.
          </p>
        </>
      )}

      {job.status === 'completed' && (
        <button type="button" className="btn-primary w-full" onClick={onViewResults}>
          <BarChart3 className="h-4 w-4" aria-hidden />
          Open results
        </button>
      )}

      {job.status === 'failed' && (
        <div className="space-y-3">
          <ErrorState
            error={
              new Error(job.error_message ?? 'The simulation failed without a message.')
            }
            title={`Simulation failed (${job.error_code ?? 'unknown'})`}
          />

          {job.retry_hint && (
            <div className="rounded-lg border border-accent/25 bg-accent/[0.06] p-2.5">
              <p className="flex items-center gap-1.5 text-2xs font-medium text-accent">
                <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
                {job.retry_hint.label}
              </p>
              <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
                {job.retry_hint.reason}
              </p>
              <button
                type="button"
                className="btn-secondary mt-2 w-full !py-1.5 !text-xs"
                onClick={() => onRetrySafe(job.retry_hint!.preset_id)}
                disabled={retryPending}
              >
                {retryPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                )}
                Retry with safe preset
              </button>
            </div>
          )}

          {precomputedAvailable && onOpenPrecomputed && (
            <ScientificNotice title="Precomputed fallback available" variant="caution" compact>
              <p className="mb-2">
                A real OpenMM result shipped with the repository can be opened instead,
                so the results interface stays demonstrable. It is labelled{' '}
                <strong>Precomputed OpenMM Result</strong> and is not a run performed on
                this machine.
              </p>
              <button
                type="button"
                className="btn-secondary w-full !py-1.5 !text-xs"
                onClick={onOpenPrecomputed}
              >
                Open precomputed result
              </button>
            </ScientificNotice>
          )}
        </div>
      )}

      {job.status === 'cancelled' && (
        <ScientificNotice title="Run cancelled" variant="caution" compact>
          This job was cancelled before finishing, so no results were produced. It is
          recorded as cancelled, never as completed.
        </ScientificNotice>
      )}
    </div>
  )
}
