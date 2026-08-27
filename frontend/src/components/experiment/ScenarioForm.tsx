import { CheckCircle2, RotateCcw, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import { RadiationControls } from './RadiationControls'
import { MechanicalControls } from './MechanicalControls'
import { ProteinSelector } from '@/components/proteins/ProteinSelector'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { DoseUnitOption, Scenario } from '@/types/prediction'
import type { ChainSummary, ProteinSummary, UploadedProtein } from '@/types/protein'
import type { SimulationPreset } from '@/types/simulation'
import type { ExperimentDraft } from '@/stores/experimentStore'
import { experimentSchema } from '@/utils/validators'
import { blurOnWheel } from '@/utils/inputGuards'

interface ScenarioFormProps {
  draft: ExperimentDraft
  proteins: ProteinSummary[] | undefined
  proteinsLoading: boolean
  proteinsError: unknown
  scenarios: Scenario[]
  doseUnits: DoseUnitOption[]
  presets: SimulationPreset[] | undefined
  chains: ChainSummary[]
  onDraftChange: (patch: Partial<ExperimentDraft>) => void
  onSelectApproved: (pdbId: string, chainId: string) => void
  onSelectUpload: (upload: UploadedProtein) => void
  onClearUpload: () => void
  onReset: () => void
  onRetryProteins?: () => void
  disabled?: boolean
}

/**
 * The experiment configuration panel.
 *
 * Validation runs against the same bounds as the backend's Pydantic models, so
 * the user gets immediate feedback — but the backend stays the authority. The
 * Validate button surfaces every problem at once rather than one at a time.
 */
export function ScenarioForm({
  draft,
  proteins,
  proteinsLoading,
  proteinsError,
  scenarios,
  doseUnits,
  presets,
  chains,
  onDraftChange,
  onSelectApproved,
  onSelectUpload,
  onClearUpload,
  onReset,
  onRetryProteins,
  disabled = false,
}: ScenarioFormProps) {
  const [issues, setIssues] = useState<string[] | null>(null)

  const validate = () => {
    const result = experimentSchema.safeParse({
      scenarioId: draft.scenarioId,
      presetId: draft.presetId,
      chainId: draft.chainId,
      dose: draft.dose,
      doseUnit: draft.doseUnit,
      exposureDurationDays: draft.exposureDurationDays,
      temperatureKelvin: draft.temperatureKelvin,
      mechanicalForcePn: draft.mechanicalForcePn,
      randomSeed: draft.randomSeed,
      topNResidues: draft.topNResidues,
    })
    if (result.success) {
      setIssues([])
      return
    }
    setIssues(result.error.issues.map((issue) => issue.message))
  }

  return (
    <div className="space-y-4">
      <ProteinSelector
        proteins={proteins}
        isLoading={proteinsLoading}
        error={proteinsError}
        selectedPdbId={draft.pdbId}
        selectedUploadId={draft.uploadId}
        uploadFilename={draft.uploadFilename}
        onSelectApproved={onSelectApproved}
        onSelectUpload={onSelectUpload}
        onClearUpload={onClearUpload}
        onRetry={onRetryProteins}
        disabled={disabled}
      />

      {/* Chain selection only matters when there is a choice. */}
      {chains.length > 1 && (
        <>
          <div className="hairline-divider" />
          <label className="block">
            <span className="mb-1 flex items-center gap-1.5 text-2xs text-ink-faint">
              Chain
              <Tooltip
                width="md"
                content="This structure has more than one chain. Features and the simulation are computed on the selected chain in isolation."
              />
            </span>
            <select
              className="select"
              onWheel={blurOnWheel}
              value={draft.chainId}
              disabled={disabled}
              onChange={(event) => onDraftChange({ chainId: event.target.value })}
            >
              {chains.map((chain) => (
                <option key={chain.chain_id} value={chain.chain_id}>
                  Chain {chain.chain_id} — {chain.n_residues} residues
                </option>
              ))}
            </select>
          </label>
        </>
      )}

      <div className="hairline-divider" />

      <RadiationControls
        scenarios={scenarios}
        doseUnits={doseUnits}
        scenarioId={draft.scenarioId}
        dose={draft.dose}
        doseUnit={draft.doseUnit}
        exposureDurationDays={draft.exposureDurationDays}
        onScenarioChange={(scenario) =>
          onDraftChange({
            scenarioId: scenario.scenario_id,
            dose: scenario.defaults.dose,
            doseUnit: scenario.defaults.dose_unit,
            exposureDurationDays: scenario.defaults.exposure_duration_days,
            temperatureKelvin: scenario.defaults.temperature_kelvin,
            mechanicalForcePn: scenario.defaults.mechanical_force_pn,
          })
        }
        onChange={onDraftChange}
        disabled={disabled}
      />

      <div className="hairline-divider" />

      <MechanicalControls
        temperatureKelvin={draft.temperatureKelvin}
        mechanicalForcePn={draft.mechanicalForcePn}
        randomSeed={draft.randomSeed}
        presetId={draft.presetId}
        presets={presets}
        onChange={onDraftChange}
        disabled={disabled}
      />

      <div className="hairline-divider" />

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn-secondary flex-1 !text-xs"
          onClick={validate}
          disabled={disabled}
        >
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
          Validate
        </button>
        <button
          type="button"
          className="btn-ghost !text-xs"
          onClick={() => {
            setIssues(null)
            onReset()
          }}
          disabled={disabled}
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden />
          Reset
        </button>
      </div>

      {issues !== null && (
        <div
          className={cn(
            'rounded-lg border p-2.5',
            issues.length === 0
              ? 'border-ok/30 bg-ok/[0.07]'
              : 'border-danger/30 bg-danger/[0.07]',
          )}
          role="status"
        >
          {issues.length === 0 ? (
            <p className="flex items-center gap-1.5 text-2xs text-ok">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
              Configuration is valid. The backend re-validates on submission.
            </p>
          ) : (
            <ul className="space-y-1">
              {issues.map((issue, index) => (
                <li key={index} className="text-2xs leading-relaxed text-danger">
                  &bull; {issue}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
