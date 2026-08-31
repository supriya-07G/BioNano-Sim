import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ScenarioForm } from '../ScenarioForm'
import type { ExperimentDraft } from '@/stores/experimentStore'
import type { DoseUnitOption, Scenario } from '@/types/prediction'
import type { ChainSummary, ProteinSummary } from '@/types/protein'
import type { SimulationPreset } from '@/types/simulation'

const MOCK_DRAFT: ExperimentDraft = {
  pdbId: '1UBQ',
  uploadId: null,
  uploadFilename: null,
  chainId: 'A',
  scenarioId: 'SPE_REFERENCE_EVENT',
  presetId: 'STEERED_PULLING_DEFAULT',
  dose: 1000,
  doseUnit: 'Gy',
  exposureDurationDays: 30,
  temperatureKelvin: 300,
  mechanicalForcePn: 15,
  randomSeed: 42,
  topNResidues: 10,
}

const MOCK_PROTEINS: ProteinSummary[] = [
  {
    pdb_id: '1UBQ',
    name: 'Ubiquitin',
    uniprot: 'P62988',
    proposed_role: 'Compact switch',
    chain_id: 'A',
    protein_length: 76,
    molecular_weight: 8560,
    experiment_method: 'X-ray',
    resolution_angstrom: 1.8,
    ml_dataset_split: 'validation',
    is_rapid_demo_default: true,
  },
]

const MOCK_SCENARIOS: Scenario[] = [
  {
    scenario_id: 'SPE_REFERENCE_EVENT',
    label: 'Solar Particle Event',
    summary: 'Proton-dominated flux event',
    notes: 'Reference scenario for testing',
    radiation_class: 'SPE',
    environment: 'LEO',
    particle_group: 'Proton',
    ml_supported: true,
    defaults: {
      dose: 1000,
      dose_unit: 'Gy',
      exposure_duration_days: 30,
      temperature_kelvin: 300,
      mechanical_force_pn: 15,
    },
  },
]

const MOCK_DOSE_UNITS: DoseUnitOption[] = [
  { unit: 'Gy', label: 'Gy (Gray)', to_gray: 1 },
]

const MOCK_PRESETS: SimulationPreset[] = [
  {
    preset_id: 'STEERED_PULLING_DEFAULT',
    label: 'Steered Pulling Default',
    summary: 'Constant velocity pulling along vector',
    platform: 'CPU',
    solvent: 'vacuum',
    forcefield: ['amber14-all.xml'],
    constraints: null,
    nonbonded_cutoff_nm: 1.0,
    production_steps: 10000,
    equilibration_steps: 500,
    minimisation_steps: 500,
    timestep_fs: 2,
    report_interval: 50,
    friction_per_ps: 1,
    simulated_time_ps: 20,
    estimated_runtime_note: '~15s',
    is_default: true,
    scientific_label: 'Steered MD',
    limitations: [],
  },
]

const MOCK_CHAINS: ChainSummary[] = [
  { chain_id: 'A', n_residues: 76, n_atoms: 602, first_residue: 1, last_residue: 76, is_default: true },
]

describe('ScenarioForm Component', () => {
  it('renders protein selector and scenario choices', () => {
    render(
      <ScenarioForm
        draft={MOCK_DRAFT}
        proteins={MOCK_PROTEINS}
        proteinsLoading={false}
        proteinsError={null}
        scenarios={MOCK_SCENARIOS}
        doseUnits={MOCK_DOSE_UNITS}
        presets={MOCK_PRESETS}
        chains={MOCK_CHAINS}
        onDraftChange={vi.fn()}
        onSelectApproved={vi.fn()}
        onSelectUpload={vi.fn()}
        onClearUpload={vi.fn()}
        onReset={vi.fn()}
      />,
    )

    expect(screen.getByText('Radiation environment')).toBeInTheDocument()
    expect(screen.getByText('Solar Particle Event')).toBeInTheDocument()
  })

  it('triggers onDraftChange when scenario selection changes', () => {
    const onDraftChange = vi.fn()
    render(
      <ScenarioForm
        draft={MOCK_DRAFT}
        proteins={MOCK_PROTEINS}
        proteinsLoading={false}
        proteinsError={null}
        scenarios={MOCK_SCENARIOS}
        doseUnits={MOCK_DOSE_UNITS}
        presets={MOCK_PRESETS}
        chains={MOCK_CHAINS}
        onDraftChange={onDraftChange}
        onSelectApproved={vi.fn()}
        onSelectUpload={vi.fn()}
        onClearUpload={vi.fn()}
        onReset={vi.fn()}
      />,
    )

    const selects = screen.getAllByRole('combobox')
    expect(selects.length).toBeGreaterThan(0)
    fireEvent.change(selects[0], { target: { value: 'SPE_REFERENCE_EVENT' } })
    expect(onDraftChange).toHaveBeenCalled()
  })
})
