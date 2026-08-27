import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { FlaskConical, Radiation } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ScientificNotice } from '@/components/common/ScientificNotice'
import { ResultLabel } from '@/components/common/StatusBadge'
import { resultKindFromLabel } from '@/utils/resultLabels'
import { PageHeader } from '@/components/layout/PageHeader'
import { SimulationConsole } from '@/components/simulation/SimulationConsole'
import { SimulationControls } from '@/components/simulation/SimulationControls'
import { SimulationProgress } from '@/components/simulation/SimulationProgress'
import { StageTimeline } from '@/components/simulation/StageTimeline'
import { JOB_POLL_INTERVAL_MS, useJobPolling } from '@/hooks/useJobPolling'
import {
  useCancelJob,
  usePrecomputedList,
  useSubmitSimulation,
} from '@/hooks/useSimulation'
import { useExperimentStore } from '@/stores/experimentStore'
import { fmtDateTime, shortId } from '@/utils/formatters'

export function SimulationPage() {
  const { jobId: routeJobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { lastJobId, setLastJobId, draft } = useExperimentStore()

  const jobId = routeJobId ?? lastJobId
  const { job, isLoading, isPolling, error, refetch } = useJobPolling(jobId)

  const cancelJob = useCancelJob()
  const resubmit = useSubmitSimulation()
  const precomputed = usePrecomputedList()

  // Remember the job so returning to /simulation without an id resumes it.
  useEffect(() => {
    if (routeJobId && routeJobId !== lastJobId) setLastJobId(routeJobId)
  }, [routeJobId, lastJobId, setLastJobId])

  if (!jobId) {
    return (
      <div className="p-4">
        <PageHeader
          title="Simulation monitor"
          description="Live job state, read from the backend."
        />
        <EmptyState
          className="mt-6"
          icon={Radiation}
          title="No simulation to monitor"
          description="Configure an experiment and start a run. Progress here is driven entirely by backend job state, never by a client-side timer."
          action={
            <button
              type="button"
              className="btn-primary !text-xs"
              onClick={() => navigate('/experiment')}
            >
              <FlaskConical className="h-3.5 w-3.5" aria-hidden />
              Open the experiment workspace
            </button>
          }
        />
      </div>
    )
  }

  if (isLoading && !job) {
    return (
      <div className="p-4">
        <LoadingState label="Loading job state…" />
      </div>
    )
  }

  if (error && !job) {
    return (
      <div className="p-4">
        <ErrorState error={error} title="Could not load this job" onRetry={refetch} />
      </div>
    )
  }

  if (!job) return null

  const retrySafe = (presetId: string) => {
    const request = job.request as Record<string, unknown>
    resubmit.mutate(
      {
        pdb_id: (request.pdb_id as string) ?? undefined,
        upload_id: (request.upload_id as string) ?? undefined,
        chain_id: (request.chain_id as string) ?? draft.chainId,
        scenario_id: (request.scenario_id as string) ?? draft.scenarioId,
        preset_id: presetId,
        temperature_kelvin:
          (request.temperature_kelvin as number) ?? draft.temperatureKelvin,
        dose: (request.dose as number) ?? draft.dose,
        dose_unit: (request.dose_unit as string) ?? draft.doseUnit,
        exposure_duration_days:
          (request.exposure_duration_days as number) ?? draft.exposureDurationDays,
        mechanical_force_pn:
          (request.mechanical_force_pn as number) ?? draft.mechanicalForcePn,
        random_seed: (request.random_seed as number) ?? draft.randomSeed,
        prediction_id: (request.prediction_id as string) ?? null,
        ml_degradation_percent: job.ml_degradation_percent,
      },
      {
        onSuccess: (next) => {
          setLastJobId(next.job_id)
          navigate(`/simulation/${next.job_id}`)
        },
      },
    )
  }

  const precomputedForThisProtein =
    job.pdb_id && precomputed.data?.available.includes(job.pdb_id)

  return (
    <div className="space-y-4 p-4">
      <PageHeader
        title="Simulation monitor"
        description={
          isPolling
            ? `Polling the backend every ${(JOB_POLL_INTERVAL_MS / 1000).toFixed(1)} s. Progress comes from the integrator's own step counter.`
            : 'This job has finished. Polling has stopped automatically.'
        }
        badges={
          <>
            <ResultLabel
              kind={resultKindFromLabel(
                (job.request?.preset as { scientific_label?: string })?.scientific_label,
              )}
            />
            <span className="font-mono text-2xs text-ink-faint">
              {shortId(job.job_id, 12)}
            </span>
          </>
        }
        actions={
          <button
            type="button"
            className="btn-ghost !text-xs"
            onClick={() => navigate('/history')}
          >
            All jobs
          </button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        {/* Main column */}
        <div className="space-y-4">
          <section className="card p-4">
            <SimulationProgress job={job} />
          </section>

          <section className="card flex min-h-0 flex-col p-4">
            <SimulationConsole
              lines={job.log_tail}
              jobId={job.job_id}
              maxHeight="20rem"
            />
          </section>

          {job.warnings.length > 0 && (
            <ScientificNotice
              title="Run warnings and limitations"
              variant="caution"
              collapsible
              defaultOpen={false}
              items={job.warnings}
            />
          )}
        </div>

        {/* Side column */}
        <div className="space-y-4">
          <section className="card p-4">
            <h2 className="label mb-3">Stages</h2>
            <StageTimeline stages={job.stages} />
          </section>

          <section className="card p-4">
            <SimulationControls
              job={job}
              onCancel={() => cancelJob.mutate(job.job_id)}
              onRetrySafe={retrySafe}
              onViewResults={() => navigate(`/results/${job.job_id}`)}
              onOpenPrecomputed={
                precomputedForThisProtein
                  ? () => navigate(`/results/precomputed/${job.pdb_id}`)
                  : undefined
              }
              cancelPending={cancelJob.isPending}
              retryPending={resubmit.isPending}
              precomputedAvailable={Boolean(precomputedForThisProtein)}
            />
            {Boolean(cancelJob.error) && (
              <ErrorState
                error={cancelJob.error}
                title="Cancellation failed"
                compact
                className="mt-3"
              />
            )}
            {Boolean(resubmit.error) && (
              <ErrorState
                error={resubmit.error}
                title="Retry failed"
                compact
                className="mt-3"
              />
            )}
          </section>

          <section className="card p-4">
            <h2 className="label mb-2">Reproducibility</h2>
            <dl className="tabular space-y-1 font-mono text-2xs">
              <Row label="Created" value={fmtDateTime(job.created_at)} />
              <Row label="Started" value={fmtDateTime(job.started_at)} />
              <Row label="Finished" value={fmtDateTime(job.finished_at)} />
              {Object.entries(job.reproducibility)
                .filter(([, value]) => typeof value !== 'object' || value === null)
                .map(([key, value]) => (
                  <Row
                    key={key}
                    label={key.replace(/_/g, ' ')}
                    value={String(value ?? '—')}
                  />
                ))}
            </dl>
            {typeof job.reproducibility.software === 'object' &&
              job.reproducibility.software !== null && (
                <>
                  <p className="label mt-3 mb-1">Software</p>
                  <dl className="tabular space-y-1 font-mono text-2xs">
                    {Object.entries(
                      job.reproducibility.software as Record<string, unknown>,
                    ).map(([key, value]) => (
                      <Row key={key} label={key} value={String(value ?? '—')} />
                    ))}
                  </dl>
                </>
              )}
          </section>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-ink-faint">{label}</dt>
      <dd className="min-w-0 truncate text-right text-ink" title={value}>
        {value}
      </dd>
    </div>
  )
}
