import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Atom, Columns2, Layers, TrendingUp } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ScientificNotice } from '@/components/common/ScientificNotice'
import { ResultLabel } from '@/components/common/StatusBadge'
import { resultKindFromLabel } from '@/utils/resultLabels'
import { PageHeader } from '@/components/layout/PageHeader'
import { ProteinViewer } from '@/components/proteins/ProteinViewer'
import { ComparisonPanel } from '@/components/results/ComparisonPanel'
import { EnergyChart, TemperatureChart } from '@/components/results/EnergyChart'
import { ExportPanel } from '@/components/results/ExportPanel'
import { MetricsGrid } from '@/components/results/MetricsGrid'
import { RadiusGyrationChart } from '@/components/results/RadiusGyrationChart'
import { RMSDChart } from '@/components/results/RMSDChart'
import { RMSFChart } from '@/components/results/RMSFChart'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { useStructure } from '@/hooks/useStructure'
import { useResults } from '@/hooks/useSimulation'
import { getPrecomputedResults, simulationKeys } from '@/services/simulations'
import { useExperimentStore } from '@/stores/experimentStore'
import { fmtDateTime, fmtDuration, fmtNm, shortId } from '@/utils/formatters'

type ViewMode = 'side_by_side' | 'overlay' | 'final_only'

export function ResultsPage() {
  const { jobId: routeJobId, pdbId: precomputedPdbId } = useParams<{
    jobId?: string
    pdbId?: string
  }>()
  const navigate = useNavigate()
  const { lastJobId } = useExperimentStore()
  const [viewMode, setViewMode] = useState<ViewMode>('side_by_side')

  const isPrecomputed = Boolean(precomputedPdbId)
  const jobId = routeJobId ?? (isPrecomputed ? null : lastJobId)

  // --- results ---------------------------------------------------------
  const jobResults = useResults(jobId, !isPrecomputed)
  const precomputedResults = useQuery({
    queryKey: simulationKeys.precomputedResults(precomputedPdbId ?? 'none'),
    queryFn: ({ signal }) => getPrecomputedResults(precomputedPdbId as string, signal),
    enabled: isPrecomputed,
    staleTime: Infinity,
  })

  const query = isPrecomputed ? precomputedResults : jobResults
  const results = query.data

  // --- structures ------------------------------------------------------
  const originalStructure = useStructure(
    isPrecomputed && precomputedPdbId
      ? { kind: 'precomputed', pdbId: precomputedPdbId, which: 'input' }
      : jobId
        ? { kind: 'job', jobId, which: 'input' }
        : null,
  )
  const finalStructure = useStructure(
    isPrecomputed && precomputedPdbId
      ? { kind: 'precomputed', pdbId: precomputedPdbId, which: 'final' }
      : jobId
        ? { kind: 'job', jobId, which: 'final' }
        : null,
  )

  if (!jobId && !isPrecomputed) {
    return (
      <div className="p-4">
        <PageHeader title="Results laboratory" />
        <EmptyState
          className="mt-6"
          icon={Atom}
          title="No results selected"
          description="Complete a simulation, or open a finished run from History."
          action={
            <button
              type="button"
              className="btn-primary !text-xs"
              onClick={() => navigate('/history')}
            >
              Browse history
            </button>
          }
        />
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <div className="p-4">
        <LoadingState label="Loading results…" />
      </div>
    )
  }

  if (query.error || !results) {
    return (
      <div className="p-4">
        <ErrorState
          error={query.error ?? new Error('No results available.')}
          title="Results unavailable"
          onRetry={() => void query.refetch()}
        >
          <button
            type="button"
            className="btn-secondary !py-1.5 !text-xs"
            onClick={() => navigate('/history')}
          >
            Browse history
          </button>
        </ErrorState>
      </div>
    )
  }

  const metrics = results.metrics
  const dynamics = metrics.dynamics_run
  const scenario = results.metadata.scenario as Record<string, unknown>

  return (
    <div className="space-y-4 p-4">
      <PageHeader
        title="Results laboratory"
        description={
          dynamics
            ? 'Every metric below is computed from the real trajectory coordinates.'
            : 'This run performed energy minimisation only, so there is no trajectory and no drift proxy.'
        }
        badges={
          <>
            <ResultLabel
              kind={resultKindFromLabel(results.result_label)}
              override={results.result_label}
            />
            <span className="font-mono text-2xs text-ink-faint">
              {isPrecomputed ? precomputedPdbId : shortId(results.job_id, 12)}
            </span>
          </>
        }
        actions={
          !isPrecomputed && (
            <button
              type="button"
              className="btn-ghost !text-xs"
              onClick={() => navigate('/compare')}
            >
              <Columns2 className="h-3.5 w-3.5" aria-hidden />
              Compare runs
            </button>
          )
        }
      />

      {/* Precomputed banner must be the first thing read. */}
      {isPrecomputed && (
        <ScientificNotice title="This is a precomputed result" variant="caution">
          <p>
            {results.warnings[0] ??
              'This result was generated once and committed to the repository. It is not a simulation run on this machine now.'}
          </p>
        </ScientificNotice>
      )}

      <MetricsGrid metrics={metrics} />

      {/* --- Structures ------------------------------------------------- */}
      <section className="card p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-medium text-ink">
            <Layers className="h-4 w-4 text-accent" aria-hidden />
            Structure comparison
            <Tooltip
              width="lg"
              content="Left is the structure as submitted; right is the final frame of the run. In overlay mode the final structure is drawn translucent in violet over the original in cyan, so divergence is visible directly."
            />
          </h2>
          <div className="flex items-center gap-1 rounded-lg border border-hairline bg-elevated p-0.5">
            {(
              [
                ['side_by_side', 'Side by side'],
                ['overlay', 'Overlay'],
                ['final_only', 'Final only'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setViewMode(value)}
                className={cn(
                  'rounded-md px-2 py-1 text-2xs transition-colors',
                  viewMode === value
                    ? 'bg-accent/15 text-accent'
                    : 'text-ink-muted hover:bg-raised hover:text-ink',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div
          className={cn(
            'grid gap-3',
            viewMode === 'side_by_side' ? 'md:grid-cols-2' : 'grid-cols-1',
          )}
        >
          {viewMode === 'side_by_side' && (
            <>
              <ViewerPanel
                label="Original (as submitted)"
                data={originalStructure.data}
                isLoading={originalStructure.isLoading}
                error={originalStructure.error}
                onRetry={() => void originalStructure.refetch()}
                name="original"
              />
              <ViewerPanel
                label={dynamics ? 'Final frame' : 'Minimised structure'}
                data={finalStructure.data}
                isLoading={finalStructure.isLoading}
                error={finalStructure.error}
                onRetry={() => void finalStructure.refetch()}
                name="final"
              />
            </>
          )}

          {viewMode === 'overlay' && (
            <ViewerPanel
              label="Original with final overlaid"
              data={originalStructure.data}
              overlayData={finalStructure.data}
              overlayLabel={dynamics ? 'Final frame' : 'Minimised'}
              isLoading={originalStructure.isLoading || finalStructure.isLoading}
              error={originalStructure.error ?? finalStructure.error}
              onRetry={() => {
                void originalStructure.refetch()
                void finalStructure.refetch()
              }}
              name="overlay"
              height="h-[26rem]"
            />
          )}

          {viewMode === 'final_only' && (
            <ViewerPanel
              label={dynamics ? 'Final frame' : 'Minimised structure'}
              data={finalStructure.data}
              isLoading={finalStructure.isLoading}
              error={finalStructure.error}
              onRetry={() => void finalStructure.refetch()}
              name="final"
              height="h-[26rem]"
            />
          )}
        </div>

        <p className="mt-2 text-2xs leading-relaxed text-ink-faint">
          The visible difference between these structures is thermal motion over{' '}
          {metrics.simulated_time_ps} ps, not radiation damage. Standard OpenMM does not
          model ionising radiation.
        </p>
      </section>

      {/* --- ML vs simulation ------------------------------------------- */}
      <ComparisonPanel
        comparison={results.comparison}
        proxy={metrics.degradation_proxy}
      />

      {/* --- Charts ----------------------------------------------------- */}
      <section>
        <h2 className="label mb-2 flex items-center gap-1.5">
          <TrendingUp className="h-3 w-3" aria-hidden />
          Trajectory analysis
        </h2>
        <div className="grid gap-3 lg:grid-cols-2">
          <RMSDChart data={results.series.rmsd} />
          <RadiusGyrationChart
            data={results.series.radius_of_gyration}
            initialValue={metrics.radius_of_gyration_nm?.initial}
          />
          <RMSFChart rows={results.rmsf} meanValue={metrics.rmsf_nm?.mean} />
          <EnergyChart data={results.series.potential_energy} />
          <TemperatureChart
            data={results.series.temperature}
            setpoint={metrics.requested_temperature_kelvin}
          />

          {/* Stability + mobility */}
          <section className="card p-3">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-medium text-ink">
              Structural stability
              <Tooltip width="lg" content={results.stability_summary.threshold_note} />
            </h3>
            <p className="text-xs capitalize text-accent">
              {results.stability_summary.verdict.replace(/_/g, ' ')}
            </p>
            <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">
              {results.stability_summary.explanation}
            </p>

            {results.highest_mobility_residues.length > 0 && (
              <>
                <div className="hairline-divider my-2.5" />
                <p className="label mb-1.5">Highest-mobility residues</p>
                <ul className="space-y-0.5">
                  {results.highest_mobility_residues.slice(0, 6).map((residue) => (
                    <li
                      key={residue.residue_id}
                      className="tabular flex items-baseline justify-between gap-2 font-mono text-2xs"
                    >
                      <span className="text-ink-muted">
                        {residue.residue_id} {residue.residue_type}
                      </span>
                      <span className="text-ink">{fmtNm(residue.rmsf_nm)}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        </div>
      </section>

      {/* --- Metadata + exports ---------------------------------------- */}
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <section className="card p-4">
          <h2 className="label mb-3">Experiment metadata</h2>
          <dl className="tabular grid gap-x-6 gap-y-1 font-mono text-2xs sm:grid-cols-2">
            <Row label="Protein" value={results.metadata.pdb_id ?? 'upload'} />
            <Row label="Chain" value={results.metadata.chain_id ?? '—'} />
            <Row label="Scenario" value={String(scenario?.scenario_id ?? '—')} />
            <Row label="Radiation class" value={String(scenario?.radiation_class ?? 'none')} />
            <Row label="Environment" value={String(scenario?.environment ?? '—')} />
            <Row label="Preset" value={results.metadata.preset?.label ?? '—'} />
            <Row label="Started" value={fmtDateTime(results.metadata.started_at)} />
            <Row label="Finished" value={fmtDateTime(results.metadata.finished_at)} />
            <Row
              label="Wall-clock duration"
              value={fmtDuration(results.metadata.duration_seconds)}
            />
            <Row
              label="Prediction id"
              value={shortId(results.metadata.prediction_id, 12)}
            />
          </dl>

          {Object.keys(results.reproducibility).length > 0 && (
            <>
              <div className="hairline-divider my-3" />
              <h3 className="label mb-2">Reproducibility</h3>
              <dl className="tabular grid gap-x-6 gap-y-1 font-mono text-2xs sm:grid-cols-2">
                {Object.entries(results.reproducibility)
                  .filter(([, value]) => typeof value !== 'object' || value === null)
                  .map(([key, value]) => (
                    <Row
                      key={key}
                      label={key.replace(/_/g, ' ')}
                      value={String(value ?? '—')}
                    />
                  ))}
              </dl>
            </>
          )}
        </section>

        <ExportPanel
          jobId={isPrecomputed ? (precomputedPdbId as string) : results.job_id}
          isPrecomputed={isPrecomputed}
          artifacts={{
            final_pdb: true,
            topology_pdb: dynamics,
            trajectory_dcd: dynamics,
            simulation_log: !isPrecomputed,
          }}
        />
      </div>

      {/* --- Limitations ----------------------------------------------- */}
      <ScientificNotice
        title="Warnings and limitations for this run"
        variant="caution"
        collapsible
        defaultOpen={false}
        items={[...results.warnings, ...results.limitations]}
      />
    </div>
  )
}

function ViewerPanel({
  label,
  data,
  overlayData,
  overlayLabel,
  isLoading,
  error,
  onRetry,
  name,
  height = 'h-72',
}: {
  label: string
  data: string | undefined
  overlayData?: string | undefined
  overlayLabel?: string
  isLoading: boolean
  error: unknown
  onRetry: () => void
  name: string
  height?: string
}) {
  return (
    <div>
      <p className="label mb-1.5">{label}</p>
      <div className={height}>
        <ProteinViewer
          data={data}
          overlayData={overlayData}
          overlayLabel={overlayLabel}
          isLoading={isLoading}
          error={error}
          onRetry={onRetry}
          screenshotName={`bionano-${name}`}
          mode="cartoon"
          colourMode="chain"
        />
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
