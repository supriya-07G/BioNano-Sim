import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Columns2,
  History as HistoryIcon,
  Loader2,
  RefreshCw,
  Trash2,
} from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { SkeletonRows } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { PageHeader } from '@/components/layout/PageHeader'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { useDeleteJob, useJobs } from '@/hooks/useSimulation'
import { useExperimentStore } from '@/stores/experimentStore'
import { isTerminal, type JobStatus } from '@/types/simulation'
import { fmtDateTime, fmtDuration, fmtPercent, shortId } from '@/utils/formatters'

const FILTERS: { value: JobStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'completed', label: 'Completed' },
  { value: 'running', label: 'Running' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
]

export function HistoryPage() {
  const navigate = useNavigate()
  const jobs = useJobs(200, { refetchInterval: 6000 })
  const deleteJob = useDeleteJob()
  const { compareSelection, toggleCompare } = useExperimentStore()

  const [filter, setFilter] = useState<JobStatus | 'all'>('all')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const rows =
    filter === 'all'
      ? (jobs.data ?? [])
      : (jobs.data ?? []).filter((job) => job.status === filter)

  return (
    <div className="space-y-4 p-4">
      <PageHeader
        title="Experiment history"
        description="Read directly from the job directories under runtime/jobs, so records survive a backend restart."
        actions={
          <>
            {compareSelection.length === 2 && (
              <button
                type="button"
                className="btn-primary !text-xs"
                onClick={() =>
                  navigate(`/compare/${compareSelection[0]}/${compareSelection[1]}`)
                }
              >
                <Columns2 className="h-3.5 w-3.5" aria-hidden />
                Compare selected
              </button>
            )}
            <button
              type="button"
              className="btn-ghost !text-xs"
              onClick={() => void jobs.refetch()}
            >
              <RefreshCw
                className={cn('h-3.5 w-3.5', jobs.isFetching && 'animate-spin')}
                aria-hidden
              />
              Refresh
            </button>
          </>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-1 rounded-lg border border-hairline bg-elevated p-0.5">
        {FILTERS.map((option) => {
          const count =
            option.value === 'all'
              ? (jobs.data?.length ?? 0)
              : (jobs.data?.filter((job) => job.status === option.value).length ?? 0)
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setFilter(option.value)}
              className={cn(
                'rounded-md px-2.5 py-1 text-2xs transition-colors',
                filter === option.value
                  ? 'bg-accent/15 text-accent'
                  : 'text-ink-muted hover:bg-raised hover:text-ink',
              )}
            >
              {option.label}
              <span className="ml-1.5 tabular font-mono text-ink-faint">{count}</span>
            </button>
          )
        })}
      </div>

      {jobs.isLoading && <SkeletonRows rows={6} />}

      {Boolean(jobs.error) && (
        <ErrorState
          error={jobs.error}
          title="Could not load history"
          onRetry={() => void jobs.refetch()}
        />
      )}

      {jobs.data && rows.length === 0 && (
        <EmptyState
          icon={HistoryIcon}
          title={filter === 'all' ? 'No experiments recorded' : `No ${filter} experiments`}
          description={
            filter === 'all'
              ? 'Run a simulation from the experiment workspace to start building a history.'
              : 'Try a different filter.'
          }
          action={
            filter === 'all' && (
              <button
                type="button"
                className="btn-primary !text-xs"
                onClick={() => navigate('/experiment')}
              >
                New experiment
              </button>
            )
          }
        />
      )}

      {rows.length > 0 && (
        <div className="card scroll-x">
          <table className="w-full min-w-[900px] border-collapse text-left">
            <thead>
              <tr className="border-b border-hairline">
                <Th className="w-10">
                  <Tooltip
                    width="md"
                    content="Select exactly two completed runs to compare them side by side."
                  />
                </Th>
                <Th>Experiment</Th>
                <Th>Protein</Th>
                <Th>Scenario</Th>
                <Th>Preset</Th>
                <Th className="text-right">ML estimate</Th>
                <Th className="text-right">Sim proxy</Th>
                <Th>Status</Th>
                <Th>Created</Th>
                <Th className="text-right">Duration</Th>
                <Th className="text-right">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((job) => {
                const selected = compareSelection.includes(job.job_id)
                const comparable = job.status === 'completed'
                return (
                  <tr
                    key={job.job_id}
                    className={cn(
                      'border-b border-hairline/50 transition-colors hover:bg-raised/50',
                      selected && 'bg-accent/[0.06]',
                    )}
                  >
                    <Td>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={!comparable}
                        onChange={() => toggleCompare(job.job_id)}
                        aria-label={`Select ${shortId(job.job_id)} for comparison`}
                        className="h-3.5 w-3.5 cursor-pointer accent-accent disabled:cursor-not-allowed disabled:opacity-30"
                      />
                    </Td>
                    <Td>
                      <span className="font-mono text-2xs text-ink" title={job.job_id}>
                        {shortId(job.job_id, 10)}
                      </span>
                    </Td>
                    <Td>
                      <span className="font-mono text-2xs text-ink">
                        {job.pdb_id ?? 'upload'}
                      </span>
                      <span className="ml-1 text-2xs text-ink-faint">
                        {job.chain_id}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-2xs text-ink-muted">{job.scenario_id}</span>
                    </Td>
                    <Td>
                      <span className="text-2xs text-ink-muted">{job.preset_id}</span>
                    </Td>
                    <Td className="tabular text-right font-mono text-2xs text-accent">
                      {fmtPercent(job.ml_degradation_percent, 1)}
                    </Td>
                    <Td className="tabular text-right font-mono text-2xs text-violet">
                      {fmtPercent(job.simulation_degradation_proxy_percent, 1)}
                    </Td>
                    <Td>
                      <StatusBadge status={job.status} />
                    </Td>
                    <Td>
                      <span className="whitespace-nowrap text-2xs text-ink-faint">
                        {fmtDateTime(job.created_at)}
                      </span>
                    </Td>
                    <Td className="tabular text-right font-mono text-2xs text-ink-muted">
                      {fmtDuration(job.duration_seconds)}
                    </Td>
                    <Td>
                      <div className="flex items-center justify-end gap-1">
                        {job.status === 'completed' && (
                          <button
                            type="button"
                            className="btn-ghost !p-1"
                            title="View results"
                            aria-label="View results"
                            onClick={() => navigate(`/results/${job.job_id}`)}
                          >
                            <BarChart3 className="h-3.5 w-3.5" aria-hidden />
                          </button>
                        )}
                        {!isTerminal(job.status) && (
                          <button
                            type="button"
                            className="btn-ghost !p-1"
                            title="Monitor"
                            aria-label="Monitor this run"
                            onClick={() => navigate(`/simulation/${job.job_id}`)}
                          >
                            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                          </button>
                        )}
                        {isTerminal(job.status) &&
                          (confirmDelete === job.job_id ? (
                            <span className="flex items-center gap-1">
                              <button
                                type="button"
                                className="btn-danger !px-1.5 !py-0.5 !text-2xs"
                                onClick={() => {
                                  deleteJob.mutate(job.job_id)
                                  setConfirmDelete(null)
                                }}
                              >
                                Delete
                              </button>
                              <button
                                type="button"
                                className="btn-ghost !px-1.5 !py-0.5 !text-2xs"
                                onClick={() => setConfirmDelete(null)}
                              >
                                Keep
                              </button>
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="btn-ghost !p-1 hover:text-danger"
                              title="Delete this job and its artifacts"
                              aria-label="Delete this job"
                              onClick={() => setConfirmDelete(job.job_id)}
                            >
                              <Trash2 className="h-3.5 w-3.5" aria-hidden />
                            </button>
                          ))}
                      </div>
                    </Td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {Boolean(deleteJob.error) && (
        <ErrorState error={deleteJob.error} title="Delete failed" compact />
      )}

      {compareSelection.length === 1 && (
        <p className="text-2xs text-ink-faint">
          One run selected. Choose a second completed run to compare.
        </p>
      )}
    </div>
  )
}

function Th({
  children,
  className,
}: {
  children?: React.ReactNode
  className?: string
}) {
  return (
    <th
      className={cn(
        'whitespace-nowrap px-2.5 py-2 text-2xs font-medium text-ink-faint',
        className,
      )}
    >
      {children}
    </th>
  )
}

function Td({
  children,
  className,
}: {
  children?: React.ReactNode
  className?: string
}) {
  return <td className={cn('px-2.5 py-2', className)}>{children}</td>
}
