import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Boxes, Eye, Layers, Palette } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ScientificNotice } from '@/components/common/ScientificNotice'
import { PageHeader } from '@/components/layout/PageHeader'
import { ExperimentSummary } from '@/components/experiment/ExperimentSummary'
import { LabVariables } from '@/components/experiment/LabVariables'
import { ScenarioForm } from '@/components/experiment/ScenarioForm'
import { PredictionCard } from '@/components/prediction/PredictionCard'
import { ProteinSummary } from '@/components/proteins/ProteinSummary'
import { ProteinViewer, type ColourMode, type RenderMode } from '@/components/proteins/ProteinViewer'
import { ResidueInspector } from '@/components/proteins/ResidueInspector'
import { cn } from '@/components/ui/cn'
import { usePrediction, useModelInfo, useScenarios } from '@/hooks/usePrediction'
import { useStructure } from '@/hooks/useStructure'
import { useHasActiveJob, usePresets, useSubmitSimulation } from '@/hooks/useSimulation'
import { getProtein, listProteins, proteinKeys } from '@/services/proteins'
import { useExperimentStore } from '@/stores/experimentStore'
import type { ResiduePrediction } from '@/types/prediction'
import type { UploadedProtein } from '@/types/protein'

const RENDER_MODES: { value: RenderMode; label: string }[] = [
  { value: 'cartoon', label: 'Cartoon' },
  { value: 'surface', label: 'Surface' },
  { value: 'stick', label: 'Stick' },
  { value: 'sphere', label: 'Sphere' },
]

const COLOUR_MODES: { value: ColourMode; label: string }[] = [
  { value: 'chain', label: 'Chain' },
  { value: 'spectrum', label: 'Spectrum' },
  { value: 'element', label: 'Element' },
]

/**
 * The experiment workspace: configuration, molecular viewport, prediction.
 *
 * Laid out as three columns that fill the viewport height so the 3D viewer needs
 * no page scrolling at 1366x768 — the left and right panels scroll
 * independently instead.
 */
export function ExperimentPage() {
  const navigate = useNavigate()
  const { draft, setDraft, selectApprovedProtein, selectUpload, resetDraft, setLastJobId } =
    useExperimentStore()

  const [renderMode, setRenderMode] = useState<RenderMode>('cartoon')
  const [colourMode, setColourMode] = useState<ColourMode>('chain')
  const [selectedResidue, setSelectedResidue] = useState<string | null>(null)

  // --- data ------------------------------------------------------------
  const proteinsQuery = useQuery({
    queryKey: proteinKeys.all,
    queryFn: ({ signal }) => listProteins(signal),
    staleTime: Infinity,
  })

  const detailQuery = useQuery({
    queryKey: proteinKeys.detail(draft.pdbId ?? 'none', draft.topNResidues),
    queryFn: ({ signal }) => getProtein(draft.pdbId as string, draft.topNResidues, signal),
    enabled: Boolean(draft.pdbId),
    staleTime: Infinity,
  })

  const scenariosQuery = useScenarios()
  const presetsQuery = usePresets()
  const modelQuery = useModelInfo()

  const structureQuery = useStructure(
    draft.uploadId
      ? { kind: 'upload', uploadId: draft.uploadId }
      : draft.pdbId
        ? { kind: 'approved', pdbId: draft.pdbId }
        : null,
  )

  const prediction = usePrediction()
  const submitSimulation = useSubmitSimulation()
  const { active: jobRunning, jobId: runningJobId } = useHasActiveJob()

  // --- derived ---------------------------------------------------------
  const scenario = scenariosQuery.data?.scenarios.find(
    (item) => item.scenario_id === draft.scenarioId,
  )
  const preset = presetsQuery.data?.find((item) => item.preset_id === draft.presetId)
  const chains = detailQuery.data?.chains ?? []
  // Memoised because `highlights` depends on it; a fresh [] each render would
  // invalidate that memo on every pass.
  const candidates = useMemo(
    () => detailQuery.data?.candidate_residues ?? [],
    [detailQuery.data],
  )

  const residuePredictions = useMemo(() => {
    const map = new Map<string, ResiduePrediction>()
    for (const item of prediction.data?.residue_predictions ?? []) {
      map.set(item.residue_id, item)
    }
    return map
  }, [prediction.data])

  // Highlight candidate residues, weighted by their predicted degradation so
  // the viewport shows where the model thinks the damage concentrates.
  const highlights = useMemo(() => {
    const values = [...residuePredictions.values()].map((r) => r.degradation_percent)
    const min = values.length ? Math.min(...values) : 0
    const max = values.length ? Math.max(...values) : 1
    const span = max - min || 1

    return candidates.map((candidate) => {
      const predicted = residuePredictions.get(candidate.residue_id)
      return {
        chainId: candidate.chain_id,
        seqNum: candidate.seq_num,
        weight: predicted ? (predicted.degradation_percent - min) / span : 0.5,
        label: candidate.residue_id,
      }
    })
  }, [candidates, residuePredictions])

  const structureSelected = Boolean(draft.pdbId || draft.uploadId)
  const mlSupported = scenario?.ml_supported ?? false
  const modelReady = modelQuery.data?.available ?? false

  const canPredict = structureSelected && mlSupported && modelReady && !prediction.isPending
  const predictBlockedReason = !structureSelected
    ? 'Select a protein first.'
    : !mlSupported
      ? 'This scenario has no ML estimate. You can still run the simulation.'
      : !modelReady
        ? 'The ML model is unavailable. Simulation still works.'
        : null

  // The prediction must complete before the simulation starts, except for
  // scenarios the model cannot score at all.
  const canSimulate =
    structureSelected &&
    !jobRunning &&
    !submitSimulation.isPending &&
    (Boolean(prediction.data) || !mlSupported)

  const simulationBlockedReason = jobRunning
    ? `A simulation is already running (${runningJobId?.slice(0, 8)}). This MVP runs one at a time.`
    : !prediction.data && mlSupported
      ? 'Run the ML estimate first so the results page can compare the two.'
      : null

  // --- actions ---------------------------------------------------------
  const runPrediction = () => {
    setSelectedResidue(null)
    prediction.mutate({
      pdb_id: draft.pdbId ?? undefined,
      upload_id: draft.uploadId ?? undefined,
      chain_id: draft.chainId,
      scenario_id: draft.scenarioId,
      dose: draft.dose,
      dose_unit: draft.doseUnit,
      exposure_duration_days: draft.exposureDurationDays,
      temperature_kelvin: draft.temperatureKelvin,
      mechanical_force_pn: 0,
      random_seed: draft.randomSeed,
      top_n_residues: draft.topNResidues,
    })
  }

  const runSimulation = () => {
    submitSimulation.mutate(
      {
        pdb_id: draft.pdbId ?? undefined,
        upload_id: draft.uploadId ?? undefined,
        chain_id: draft.chainId,
        scenario_id: draft.scenarioId,
        preset_id: draft.presetId,
        temperature_kelvin: draft.temperatureKelvin,
        dose: draft.dose,
        dose_unit: draft.doseUnit,
        exposure_duration_days: draft.exposureDurationDays,
        mechanical_force_pn: 0,
        random_seed: draft.randomSeed,
        prediction_id: prediction.data?.prediction_id ?? null,
        ml_degradation_percent: prediction.data?.degradation_percent ?? null,
      },
      {
        onSuccess: (job) => {
          setLastJobId(job.job_id)
          navigate(`/simulation/${job.job_id}`)
        },
      },
    )
  }

  const handleUpload = (upload: UploadedProtein) => {
    selectUpload(upload.upload_id, upload.filename, upload.default_chain)
    prediction.reset()
  }

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-hairline px-4 py-3">
        <PageHeader
          title="Experiment workspace"
          description="Configure a scenario, estimate degradation with the MVP model, then run a real short OpenMM simulation."
          badges={
            <span className="badge border-hairline bg-elevated text-ink-faint">
              {draft.uploadId ? 'custom upload' : (draft.pdbId ?? 'no protein')}
            </span>
          }
        />
      </div>

      {/* Three-panel layout. Each panel scrolls on its own so the viewport
          never forces the page to scroll. */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[19rem_1fr_21rem] xl:grid-cols-[21rem_1fr_23rem]">
        {/* Left: configuration */}
        <section className="min-h-0 overflow-y-auto border-hairline p-3 lg:border-r">
          <ScenarioForm
            draft={draft}
            proteins={proteinsQuery.data}
            proteinsLoading={proteinsQuery.isLoading}
            proteinsError={proteinsQuery.error}
            scenarios={scenariosQuery.data?.scenarios ?? []}
            doseUnits={scenariosQuery.data?.dose_units ?? []}
            presets={presetsQuery.data}
            chains={chains}
            onDraftChange={(patch) => {
              setDraft(patch)
              // Any configuration change invalidates the previous estimate.
              if (prediction.data || prediction.error) prediction.reset()
            }}
            onSelectApproved={(pdbId, chainId) => {
              selectApprovedProtein(pdbId, chainId)
              prediction.reset()
              setSelectedResidue(null)
            }}
            onSelectUpload={handleUpload}
            onClearUpload={() => {
              selectApprovedProtein('1UBQ', 'A')
              prediction.reset()
            }}
            onReset={() => {
              resetDraft()
              prediction.reset()
              setSelectedResidue(null)
            }}
            onRetryProteins={() => void proteinsQuery.refetch()}
            disabled={submitSimulation.isPending}
          />
        </section>

        {/* Centre: viewport */}
        <section className="flex min-h-0 flex-col p-3">
          {/* Viewer controls */}
          <div className="mb-2 flex shrink-0 flex-wrap items-center gap-2">
            <ControlGroup
              icon={Eye}
              options={RENDER_MODES}
              value={renderMode}
              onChange={setRenderMode}
            />
            <ControlGroup
              icon={Palette}
              options={COLOUR_MODES}
              value={colourMode}
              onChange={setColourMode}
            />
            {highlights.length > 0 && (
              <span className="badge border-accent/35 bg-accent/[0.08] text-accent">
                <Layers className="h-3 w-3" aria-hidden />
                {highlights.length} candidate residues
              </span>
            )}
          </div>

          <div className="min-h-[18rem] flex-1">
            <ProteinViewer
              data={structureQuery.data}
              isLoading={structureQuery.isLoading}
              error={structureQuery.error}
              mode={renderMode}
              colourMode={colourMode}
              highlights={highlights}
              onResidueClick={(residue) =>
                setSelectedResidue(`${residue.chainId}:${residue.seqNum}`)
              }
              screenshotName={`COSMORA-${draft.pdbId ?? 'upload'}-${draft.chainId}`}
              onRetry={() => void structureQuery.refetch()}
              fullscreenTitle={`${draft.pdbId ?? 'upload'} · chain ${draft.chainId}`}
              fullscreenPanel={
                <LabVariables draft={draft} scenario={scenario} preset={preset} />
              }
            />
          </div>

          {/* Residue table below the viewport */}
          <div className="mt-2 max-h-[15rem] shrink-0 overflow-y-auto rounded-lg border border-hairline bg-surface p-3">
            <ResidueInspector
              candidates={candidates}
              predictions={prediction.data ? residuePredictions : undefined}
              selectedResidueId={selectedResidue}
              onSelect={setSelectedResidue}
            />
          </div>
        </section>

        {/* Right: prediction + summary */}
        <section className="min-h-0 overflow-y-auto border-hairline p-3 lg:border-l">
          <div className="space-y-4">
            <PredictionCard
              prediction={prediction.data}
              model={modelQuery.data}
              isPending={prediction.isPending}
              error={prediction.error}
              onPredict={runPrediction}
              onRunSimulation={runSimulation}
              canPredict={canPredict}
              canSimulate={canSimulate}
              predictBlockedReason={predictBlockedReason}
              simulationBlockedReason={simulationBlockedReason}
            />

            {Boolean(submitSimulation.error) && (
              <ErrorState
                error={submitSimulation.error}
                title="Could not start the simulation"
                onRetry={runSimulation}
              />
            )}

            <div className="hairline-divider" />

            <ExperimentSummary
              draft={draft}
              scenario={scenario}
              preset={preset}
              model={modelQuery.data}
            />

            <div className="hairline-divider" />

            {detailQuery.isLoading && <LoadingState compact label="Loading protein…" />}
            {detailQuery.data && <ProteinSummary protein={detailQuery.data} />}
            {draft.uploadId && (
              <div className="flex items-start gap-2 rounded-lg border border-violet/30 bg-violet/[0.06] p-2.5">
                <Boxes className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet" aria-hidden />
                <p className="text-2xs leading-relaxed text-ink-muted">
                  Custom structure <span className="font-mono">{draft.uploadFilename}</span>.
                  Features are recomputed rather than read from the training reference
                  table, so this estimate is less faithful than one for an approved
                  protein.
                </p>
              </div>
            )}

            <ScientificNotice
              title="Before you read the number above"
              variant="scientific"
              compact
              items={[
                'The ML model is a mock public-data bootstrap model. Its labels are a synthetic proxy, not experimental measurements.',
                'The model has no dose, duration, temperature or force input. Radiation reaches it only as a scenario category.',
                'A protein-level percentage is aggregated by COSMORA from per-residue predictions over the most susceptible residues.',
              ]}
            />
          </div>
        </section>
      </div>
    </div>
  )
}

function ControlGroup<T extends string>({
  icon: Icon,
  options,
  value,
  onChange,
}: {
  icon: typeof Eye
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-hairline bg-elevated p-0.5">
      <Icon className="ml-1.5 h-3 w-3 shrink-0 text-ink-faint" aria-hidden />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            'rounded-md px-2 py-1 text-2xs transition-colors',
            value === option.value
              ? 'bg-accent/15 text-accent'
              : 'text-ink-muted hover:bg-raised hover:text-ink',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
