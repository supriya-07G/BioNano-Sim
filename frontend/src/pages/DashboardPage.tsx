import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowRight,
  Boxes,
  CheckCircle2,
  CircleSlash,
  Cpu,
  FlaskConical,
  History,
  Rocket,
  XCircle,
} from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { MissionBrief } from '@/components/dashboard/MissionBrief'
import { ErrorState } from '@/components/common/ErrorState'
import { SkeletonCard, SkeletonRows } from '@/components/common/LoadingState'
import { ScopeNotice } from '@/components/common/ScientificNotice'
import { ReadinessBadge, StatusBadge } from '@/components/common/StatusBadge'
import { PageHeader } from '@/components/layout/PageHeader'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { useModelInfo, useScenarios } from '@/hooks/usePrediction'
import { useJobs, useReadiness } from '@/hooks/useSimulation'
import { listProteins, proteinKeys } from '@/services/proteins'
import { useExperimentStore } from '@/stores/experimentStore'
import { fmtDuration, fmtPercent, fmtRelativeTime } from '@/utils/formatters'

export function DashboardPage() {
  const navigate = useNavigate()
  const { setDraft } = useExperimentStore()

  const readiness = useReadiness({ refetchInterval: 15_000 })
  const proteins = useQuery({
    queryKey: proteinKeys.all,
    queryFn: ({ signal }) => listProteins(signal),
    staleTime: Infinity,
  })
  const jobs = useJobs(20, { refetchInterval: 6000 })
  const model = useModelInfo()
  const scenarios = useScenarios()

  const counts = readiness.data?.counts
  const completed = jobs.data?.filter((job) => job.status === 'completed') ?? []

  const startScenario = (scenarioId: string) => {
    setDraft({ scenarioId })
    navigate('/experiment')
  }

  return (
    <div className="space-y-4 p-4">
      <PageHeader
        title="Mission dashboard"
        description="System state, approved proteins and recent experiments."
        badges={readiness.data && <ReadinessBadge status={readiness.data.status} />}
        actions={
          <button
            type="button"
            className="btn-primary !text-xs"
            onClick={() => navigate('/experiment')}
          >
            <FlaskConical className="h-3.5 w-3.5" aria-hidden />
            New experiment
          </button>
        }
      />

      <MissionBrief />

      {/* --- Top stats ---------------------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {readiness.isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} />)
        ) : (
          <>
            <StatCard
              icon={Boxes}
              label="Approved proteins"
              value={String(counts?.approved_proteins ?? 0)}
              sub={`${counts?.scenarios ?? 0} scenarios, ${counts?.ml_supported_scenarios ?? 0} ML-supported`}
              tone="accent"
            />
            <StatCard
              icon={CheckCircle2}
              label="Completed simulations"
              value={String(counts?.completed_jobs ?? 0)}
              sub={`${counts?.total_jobs ?? 0} total, ${counts?.failed_jobs ?? 0} failed`}
              tone="ok"
            />
            <StatCard
              icon={Activity}
              label="Model status"
              value={model.data?.available ? 'Ready' : 'Unavailable'}
              sub={
                model.data
                  ? `v${model.data.model_version} · ${model.data.scientific_status}`
                  : 'not loaded'
              }
              tone={model.data?.available ? 'ok' : 'danger'}
              help={
                model.data
                  ? `${model.data.model_name}. Integrity ${
                      model.data.sha256_verified ? 'verified' : 'UNVERIFIED'
                    } against release_manifest.json; feature schema ${
                      model.data.schema_verified ? 'verified' : 'UNVERIFIED'
                    } against the loaded pipeline.`
                  : undefined
              }
            />
            <StatCard
              icon={Cpu}
              label="Simulation engine"
              value={
                readiness.data?.components.find((c) => c.name === 'simulation_engine')
                  ?.ready
                  ? 'Ready'
                  : 'Unavailable'
              }
              sub={
                readiness.data?.components.find((c) => c.name === 'simulation_engine')
                  ?.version
                  ? `OpenMM ${readiness.data.components.find((c) => c.name === 'simulation_engine')?.version}`
                  : 'OpenMM not importable'
              }
              tone={
                readiness.data?.components.find((c) => c.name === 'simulation_engine')
                  ?.ready
                  ? 'ok'
                  : 'danger'
              }
              help={
                readiness.data?.components.find((c) => c.name === 'simulation_engine')
                  ?.detail
              }
            />
          </>
        )}
      </div>

      {Boolean(readiness.error) && (
        <ErrorState
          error={readiness.error}
          title="Cannot reach the backend"
          onRetry={() => void readiness.refetch()}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          {/* --- Quick start ------------------------------------------- */}
          <section className="card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-medium text-ink">
                <Rocket className="h-4 w-4 text-accent" aria-hidden />
                Quick-start scenarios
              </h2>
              <Tooltip
                width="lg"
                content={
                  scenarios.data?.provenance.statement ??
                  'Scenario values are configurable demonstration presets, not authoritative mission data.'
                }
              />
            </div>

            {scenarios.isLoading && <SkeletonRows rows={3} />}

            <div className="grid gap-2 sm:grid-cols-2">
              {scenarios.data?.scenarios.map((scenario) => (
                <button
                  key={scenario.scenario_id}
                  type="button"
                  onClick={() => startScenario(scenario.scenario_id)}
                  className="group rounded-lg border border-hairline bg-elevated p-3 text-left transition-colors hover:border-accent/40 hover:bg-raised"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-medium text-ink">{scenario.label}</span>
                    {scenario.ml_supported ? (
                      <span className="badge border-ok/40 bg-ok/10 text-ok">ML + sim</span>
                    ) : (
                      <span className="badge border-warn/40 bg-warn/10 text-warn">
                        sim only
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
                    {scenario.summary}
                  </p>
                  <p className="tabular mt-1.5 font-mono text-2xs text-ink-faint">
                    {scenario.defaults.dose} {scenario.defaults.dose_unit} ·{' '}
                    {scenario.defaults.temperature_kelvin} K ·{' '}
                    {scenario.defaults.exposure_duration_days} d
                  </p>
                </button>
              ))}
            </div>

            <p className="mt-3 text-2xs leading-relaxed text-ink-faint">
              {scenarios.data?.provenance.ml_coupling}
            </p>
            <div className="mt-3 rounded-lg border border-hairline bg-void/40 p-2.5">
              <p className="text-2xs font-medium text-ink-muted">Input-coupling guide</p>
              <p className="mt-1 text-2xs leading-relaxed text-ink-faint">
                Scenario category affects the ML estimate. Temperature and the selected
                preset affect the OpenMM run. Dose and exposure duration are provenance
                only; mechanical pulling is inactive in this MVP.
              </p>
            </div>
          </section>

          {/* --- Recent experiments ----------------------------------- */}
          <section className="card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-medium text-ink">
                <History className="h-4 w-4 text-accent" aria-hidden />
                Recent experiments
              </h2>
              <button
                type="button"
                className="btn-ghost !px-2 !py-1 !text-2xs"
                onClick={() => navigate('/history')}
              >
                View all
                <ArrowRight className="h-3 w-3" aria-hidden />
              </button>
            </div>

            {jobs.isLoading && <SkeletonRows rows={4} />}

            {jobs.data && jobs.data.length === 0 && (
              <EmptyState
                compact
                icon={CircleSlash}
                title="No experiments yet"
                description="Start one from the experiment workspace. Job records are read from runtime/jobs, so they survive a backend restart."
                action={
                  <button
                    type="button"
                    className="btn-secondary !text-xs"
                    onClick={() => navigate('/experiment')}
                  >
                    Configure an experiment
                  </button>
                }
              />
            )}

            {jobs.data && jobs.data.length > 0 && (
              <ul className="space-y-1.5">
                {jobs.data.slice(0, 6).map((job) => (
                  <li key={job.job_id}>
                    <button
                      type="button"
                      onClick={() =>
                        navigate(
                          job.status === 'completed'
                            ? `/results/${job.job_id}`
                            : `/simulation/${job.job_id}`,
                        )
                      }
                      className="flex w-full items-center gap-3 rounded-lg border border-hairline bg-elevated px-3 py-2 text-left transition-colors hover:border-accent/35 hover:bg-raised"
                    >
                      <StatusBadge status={job.status} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-mono text-xs text-ink">
                          {job.pdb_id ?? 'upload'} · {job.scenario_id}
                        </span>
                        <span className="block truncate text-2xs text-ink-faint">
                          {fmtRelativeTime(job.created_at)} ·{' '}
                          {fmtDuration(job.duration_seconds)} · {job.preset_id}
                        </span>
                      </span>
                      <span className="tabular shrink-0 text-right font-mono text-2xs">
                        <span className="block text-accent">
                          ML {fmtPercent(job.ml_degradation_percent, 1)}
                        </span>
                        <span className="block text-violet">
                          proxy{' '}
                          {fmtPercent(job.simulation_degradation_proxy_percent, 1)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* --- Protein comparison cards ----------------------------- */}
          <section className="card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink">
              <Boxes className="h-4 w-4 text-accent" aria-hidden />
              Approved proteins
            </h2>

            {proteins.isLoading && <SkeletonRows rows={5} />}

            {proteins.data && (
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {proteins.data.map((protein) => (
                  <button
                    key={protein.pdb_id}
                    type="button"
                    onClick={() => {
                      setDraft({ pdbId: protein.pdb_id, uploadId: null, chainId: protein.chain_id })
                      navigate('/experiment')
                    }}
                    className="rounded-lg border border-hairline bg-elevated p-2.5 text-left transition-colors hover:border-accent/40 hover:bg-raised"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-ink">
                        {protein.pdb_id}
                      </span>
                      <span
                        className={cn(
                          'badge',
                          protein.ml_dataset_split === 'train'
                            ? 'border-warn/40 bg-warn/10 text-warn'
                            : 'border-ok/40 bg-ok/10 text-ok',
                        )}
                      >
                        {protein.ml_dataset_split === 'train' ? 'train' : 'held-out'}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-2xs text-ink">{protein.name}</p>
                    <p className="mt-0.5 truncate text-2xs text-ink-faint">
                      {protein.proposed_role}
                    </p>
                    <p className="tabular mt-1 font-mono text-2xs text-ink-faint">
                      {protein.protein_length} aa · chain {protein.chain_id}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* --- Side column --------------------------------------------- */}
        <div className="space-y-4">
          <section className="card p-4">
            <h2 className="mb-3 text-sm font-medium text-ink">System readiness</h2>

            {readiness.isLoading && <SkeletonRows rows={6} />}

            {readiness.data && (
              <ul className="space-y-2">
                {readiness.data.components.map((component) => (
                  <li key={component.name} className="flex items-start gap-2">
                    {component.ready ? (
                      <CheckCircle2
                        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok"
                        aria-hidden
                      />
                    ) : (
                      <XCircle
                        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger"
                        aria-hidden
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs capitalize text-ink">
                        {component.name.replace(/_/g, ' ')}
                      </p>
                      <p className="text-2xs leading-relaxed text-ink-faint">
                        {component.detail}
                      </p>
                      {component.remediation && (
                        <p className="mt-1 rounded border border-hairline bg-void/60 p-1.5 font-mono text-2xs text-ink-muted">
                          {component.remediation}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {completed.length >= 2 && (
            <section className="card p-4">
              <h2 className="mb-2 text-sm font-medium text-ink">Compare runs</h2>
              <p className="mb-3 text-2xs leading-relaxed text-ink-muted">
                You have {completed.length} completed runs. Compare two to isolate a
                protein or scenario effect.
              </p>
              <button
                type="button"
                className="btn-secondary w-full !text-xs"
                onClick={() => navigate('/compare')}
              >
                Open comparison
                <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </button>
            </section>
          )}

          <ScopeNotice />
        </div>
      </div>
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone,
  help,
}: {
  icon: typeof Activity
  label: string
  value: string
  sub: string
  tone: 'accent' | 'ok' | 'danger'
  help?: string
}) {
  const tones = {
    accent: 'text-accent',
    ok: 'text-ok',
    danger: 'text-danger',
  } as const

  return (
    <div className="card p-3.5">
      <div className="flex items-center gap-1.5">
        <Icon className={cn('h-3.5 w-3.5 shrink-0', tones[tone])} aria-hidden />
        <span className="truncate text-2xs text-ink-faint">{label}</span>
        {help && <Tooltip width="lg" content={help} />}
      </div>
      <p className="tabular mt-1.5 font-mono text-xl text-ink">{value}</p>
      <p className="mt-0.5 truncate text-2xs text-ink-faint" title={sub}>
        {sub}
      </p>
    </div>
  )
}
