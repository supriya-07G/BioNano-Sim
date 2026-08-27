import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Columns2, Download, Medal } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ScientificNotice } from '@/components/common/ScientificNotice'
import { PageHeader } from '@/components/layout/PageHeader'
import { ChartShell, DualSeriesChart } from '@/components/results/ChartShell'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { useJobs } from '@/hooks/useSimulation'
import { downloadUrl } from '@/services/api'
import { compareJobs, simulationKeys } from '@/services/simulations'
import { fmtDelta, fmtDuration, fmtNumber, shortId } from '@/utils/formatters'
import type { CompareBrief } from '@/types/simulation'
import { blurOnWheel } from '@/utils/inputGuards'

export function ComparePage() {
  const { jobIdA, jobIdB } = useParams<{ jobIdA?: string; jobIdB?: string }>()
  const navigate = useNavigate()
  const jobs = useJobs(200)

  const completed = (jobs.data ?? []).filter((job) => job.status === 'completed')
  const [selectedA, setSelectedA] = useState<string>(jobIdA ?? '')
  const [selectedB, setSelectedB] = useState<string>(jobIdB ?? '')

  useEffect(() => {
    if (jobIdA) setSelectedA(jobIdA)
    if (jobIdB) setSelectedB(jobIdB)
  }, [jobIdA, jobIdB])

  const ready = Boolean(selectedA && selectedB && selectedA !== selectedB)

  const comparison = useQuery({
    queryKey: simulationKeys.compare(selectedA, selectedB),
    queryFn: ({ signal }) => compareJobs(selectedA, selectedB, signal),
    enabled: ready,
    staleTime: Infinity,
  })

  if (jobs.isLoading) {
    return (
      <div className="p-4">
        <LoadingState label="Loading completed runs…" />
      </div>
    )
  }

  if (completed.length < 2) {
    return (
      <div className="p-4">
        <PageHeader title="Compare experiments" />
        <EmptyState
          className="mt-6"
          icon={Columns2}
          title="Two completed runs are needed"
          description={`You currently have ${completed.length} completed run${
            completed.length === 1 ? '' : 's'
          }. Run at least two — for example the same protein under different scenarios, or two proteins under the same scenario — and they will appear here.`}
          action={
            <button
              type="button"
              className="btn-primary !text-xs"
              onClick={() => navigate('/experiment')}
            >
              New experiment
            </button>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-4 p-4">
      <PageHeader
        title="Compare experiments"
        description="Put two completed runs side by side to isolate a protein or scenario effect."
        actions={
          comparison.data && (
            <div className="flex items-center gap-2">
              <a
                href={downloadUrl(`/reports/${selectedA}.json`)}
                download={`bionano-${shortId(selectedA)}.json`}
                className="btn-ghost !text-xs"
              >
                <Download className="h-3.5 w-3.5" aria-hidden />
                Report A
              </a>
              <a
                href={downloadUrl(`/reports/${selectedB}.json`)}
                download={`bionano-${shortId(selectedB)}.json`}
                className="btn-ghost !text-xs"
              >
                <Download className="h-3.5 w-3.5" aria-hidden />
                Report B
              </a>
            </div>
          )
        }
      />

      {/* Selectors */}
      <div className="card grid gap-3 p-4 sm:grid-cols-2">
        <JobPicker
          label="Experiment A"
          value={selectedA}
          exclude={selectedB}
          options={completed}
          onChange={(value) => {
            setSelectedA(value)
            if (value && selectedB) navigate(`/compare/${value}/${selectedB}`)
          }}
        />
        <JobPicker
          label="Experiment B"
          value={selectedB}
          exclude={selectedA}
          options={completed}
          onChange={(value) => {
            setSelectedB(value)
            if (selectedA && value) navigate(`/compare/${selectedA}/${value}`)
          }}
        />
      </div>

      {!ready && (
        <EmptyState
          compact
          title="Select two different experiments"
          description="Pick one run in each selector above."
        />
      )}

      {comparison.isLoading && ready && <LoadingState label="Comparing runs…" />}

      {Boolean(comparison.error) && (
        <ErrorState
          error={comparison.error}
          title="Comparison failed"
          onRetry={() => void comparison.refetch()}
        />
      )}

      {comparison.data && (
        <>
          {/* Like-for-like warning comes before any ranking. */}
          {!comparison.data.comparable && (
            <div className="flex items-start gap-2.5 rounded-lg border border-warn/35 bg-warn/[0.07] p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
              <div>
                <p className="text-xs font-medium text-warn">
                  Not a like-for-like comparison
                </p>
                {comparison.data.notes.map((note, index) => (
                  <p key={index} className="mt-1 text-2xs leading-relaxed text-ink-muted">
                    {note}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Run headers */}
          <div className="grid gap-3 sm:grid-cols-2">
            <RunCard brief={comparison.data.a} tone="accent" label="A" />
            <RunCard brief={comparison.data.b} tone="violet" label="B" />
          </div>

          {/* Difference table */}
          <section className="card p-4">
            <h2 className="mb-3 text-sm font-medium text-ink">Metric differences</h2>
            <div className="scroll-x">
              <table className="w-full min-w-[560px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-hairline">
                    <th className="px-2 py-1.5 text-2xs font-medium text-ink-faint">
                      Metric
                    </th>
                    <th className="px-2 py-1.5 text-right text-2xs font-medium text-accent">
                      A
                    </th>
                    <th className="px-2 py-1.5 text-right text-2xs font-medium text-violet">
                      B
                    </th>
                    <th className="px-2 py-1.5 text-right text-2xs font-medium text-ink-faint">
                      B − A
                    </th>
                    <th className="px-2 py-1.5 text-right text-2xs font-medium text-ink-faint">
                      More stable
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.data.differences.map((row) => (
                    <tr key={row.metric} className="border-b border-hairline/50">
                      <td className="px-2 py-1.5 text-2xs text-ink-muted">
                        {row.label}
                        <span className="ml-1 font-mono text-ink-faint">
                          ({row.unit})
                        </span>
                      </td>
                      <td className="tabular px-2 py-1.5 text-right font-mono text-2xs text-ink">
                        {fmtNumber(row.a, row.unit === '%' ? 1 : 4)}
                      </td>
                      <td className="tabular px-2 py-1.5 text-right font-mono text-2xs text-ink">
                        {fmtNumber(row.b, row.unit === '%' ? 1 : 4)}
                      </td>
                      <td className="tabular px-2 py-1.5 text-right font-mono text-2xs text-ink-muted">
                        {fmtDelta(row.delta_b_minus_a, row.unit === '%' ? 1 : 4, '')}
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        {row.more_stable_job_id ? (
                          <span
                            className={cn(
                              'badge',
                              row.more_stable_job_id === comparison.data.a.job_id
                                ? 'border-accent/40 bg-accent/10 text-accent'
                                : 'border-violet/40 bg-violet/10 text-violet',
                            )}
                          >
                            {row.more_stable_job_id === comparison.data.a.job_id
                              ? 'A'
                              : 'B'}
                          </span>
                        ) : (
                          <span className="text-2xs text-ink-faint">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Stability ranking */}
          {comparison.data.stability_ranking.length > 0 && (
            <section className="card p-4">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink">
                <Medal className="h-4 w-4 text-accent" aria-hidden />
                Stability ranking
                <Tooltip
                  width="lg"
                  content="Ranked by final Cα RMSD: lower means the fold moved less over the run. This says which run drifted less under these exact settings — not which protein is genuinely more radiation-tolerant."
                />
              </h2>
              <ol className="space-y-1.5">
                {comparison.data.stability_ranking.map((entry) => (
                  <li
                    key={entry.job_id}
                    className="flex items-center gap-3 rounded-lg border border-hairline bg-elevated px-3 py-2"
                  >
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md border border-accent/25 bg-accent/10 font-mono text-2xs text-accent">
                      {entry.rank}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">
                      {entry.label}
                    </span>
                    <span className="tabular shrink-0 font-mono text-2xs text-ink-muted">
                      {fmtNumber(entry.final_rmsd_nm, 4)} nm
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* Synchronised charts */}
          <section>
            <h2 className="label mb-2">Synchronised trajectories</h2>
            <div className="grid gap-3 lg:grid-cols-2">
              <ChartShell
                title="Backbone RMSD"
                unit="nm"
                help="Both runs on shared axes. Curves are only directly comparable when the two runs used the same preset, since RMSD grows with simulated time."
                isEmpty={
                  !comparison.data.a.series.rmsd?.length &&
                  !comparison.data.b.series.rmsd?.length
                }
              >
                <DualSeriesChart
                  seriesA={comparison.data.a.series.rmsd ?? []}
                  seriesB={comparison.data.b.series.rmsd ?? []}
                  labelA={`A · ${comparison.data.a.pdb_id ?? 'upload'}`}
                  labelB={`B · ${comparison.data.b.pdb_id ?? 'upload'}`}
                  unit="nm"
                />
              </ChartShell>

              <ChartShell
                title="Radius of gyration"
                unit="nm"
                help="Absolute Rg scales with chain length, so compare the shape of the curves rather than their separation when the two proteins differ in size."
                isEmpty={
                  !comparison.data.a.series.radius_of_gyration?.length &&
                  !comparison.data.b.series.radius_of_gyration?.length
                }
              >
                <DualSeriesChart
                  seriesA={comparison.data.a.series.radius_of_gyration ?? []}
                  seriesB={comparison.data.b.series.radius_of_gyration ?? []}
                  labelA={`A · ${comparison.data.a.pdb_id ?? 'upload'}`}
                  labelB={`B · ${comparison.data.b.pdb_id ?? 'upload'}`}
                  unit="nm"
                />
              </ChartShell>
            </div>
            <div className="mt-3 flex items-center gap-4">
              <LegendSwatch colour="#38BDF8" label="Experiment A" />
              <LegendSwatch colour="#8B5CF6" label="Experiment B" />
            </div>
          </section>

          <ScientificNotice
            title="How to read this comparison"
            variant="caution"
            items={[
              ...comparison.data.notes,
              ...comparison.data.interpretation_limits,
            ]}
          />
        </>
      )}
    </div>
  )
}

function JobPicker({
  label,
  value,
  exclude,
  options,
  onChange,
}: {
  label: string
  value: string
  exclude: string
  options: { job_id: string; pdb_id: string | null; scenario_id: string; preset_id: string; created_at: string }[]
  onChange: (value: string) => void
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-2xs text-ink-faint">{label}</span>
      <select
        className="select"
        onWheel={blurOnWheel}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Select a completed run…</option>
        {options
          .filter((option) => option.job_id !== exclude)
          .map((option) => (
            <option key={option.job_id} value={option.job_id}>
              {option.pdb_id ?? 'upload'} · {option.scenario_id} · {option.preset_id} ·{' '}
              {shortId(option.job_id)}
            </option>
          ))}
      </select>
    </label>
  )
}

function RunCard({
  brief,
  tone,
  label,
}: {
  brief: CompareBrief
  tone: 'accent' | 'violet'
  label: string
}) {
  const tones = {
    accent: 'border-accent/35 bg-accent/[0.06] text-accent',
    violet: 'border-violet/35 bg-violet/[0.06] text-violet',
  } as const

  return (
    <div className="card p-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className={cn('badge', tones[tone])}>{label}</span>
        <span className="font-mono text-2xs text-ink-faint" title={brief.job_id}>
          {shortId(brief.job_id, 10)}
        </span>
      </div>
      <p className="mt-2 font-mono text-sm text-ink">
        {brief.pdb_id ?? 'upload'} · {brief.chain_id}
      </p>
      <p className="mt-0.5 text-2xs text-ink-muted">{brief.scenario_label}</p>
      <dl className="tabular mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-2xs">
        <Row label="Preset" value={brief.preset_label ?? '—'} />
        <Row label="Simulated" value={`${brief.simulated_time_ps ?? '—'} ps`} />
        <Row label="Frames" value={String(brief.n_frames ?? '—')} />
        <Row label="Wall clock" value={fmtDuration(brief.duration_seconds)} />
        <Row label="Stability" value={brief.stability_verdict?.replace(/_/g, ' ') ?? '—'} />
        <Row label="Final RMSD" value={`${fmtNumber(brief.final_rmsd_nm, 4)} nm`} />
      </dl>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-ink-faint">{label}</dt>
      <dd className="truncate text-ink" title={value}>
        {value}
      </dd>
    </div>
  )
}

function LegendSwatch({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-2xs text-ink-muted">
      <span
        className="h-0.5 w-4 rounded"
        style={{ backgroundColor: colour }}
        aria-hidden
      />
      {label}
    </span>
  )
}
