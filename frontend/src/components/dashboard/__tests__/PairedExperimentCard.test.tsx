import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ExperimentSummary, PairedForceExtension } from '@/types/experiment'

import { PairedExperimentCard } from '../PairedExperimentCard'

/**
 * The card used to render an eleven-point array written into its own source,
 * and these tests asserted those constants back ("142.5", "-37.4%"). They
 * therefore passed while the displayed stiffness was a quarter of the measured
 * value. What is checked now is that the card renders whatever the API returns
 * and nothing else.
 */

vi.mock('@/services/experiments', async () => {
  const actual = await vi.importActual<typeof import('@/services/experiments')>(
    '@/services/experiments',
  )
  return {
    ...actual,
    listExperiments: vi.fn(),
    getForceExtension: vi.fn(),
  }
})

const { listExperiments, getForceExtension } = await import('@/services/experiments')

const RUN: ExperimentSummary = {
  experiment_id: '1UBQ_GCR_MILD_A74_seed1',
  protein_id: '1UBQ',
  pdb_id: '1UBQ',
  chain_id: 'A',
  scenario_id: 'GCR_DEEP_SPACE_REFERENCE',
  status: 'COMPLETED',
  severity_label: 'MILD',
  damage_residue_id: 'A:74',
  residue_type: 'ARG',
  baseline_stiffness: 662.1,
  damaged_stiffness: 593.4,
  stiffness_unit: 'pN/nm',
  mechanical_degradation_pct: 10.4,
  random_seed: 1,
  is_synthetic: false,
  qc_failures: [],
}

const CURVE: PairedForceExtension = {
  experiment_id: RUN.experiment_id,
  stiffness_unit: 'pN/nm',
  baseline: [
    { time_ps: 0.04, restraint_center_nm: 3.7, end_to_end_nm: 3.7, extension_nm: 0.0, force_pn: 4, work_kj_mol: 0, potential_energy_kj_mol: -11500 },
    { time_ps: 0.08, restraint_center_nm: 3.8, end_to_end_nm: 3.75, extension_nm: 0.1, force_pn: 62, work_kj_mol: 0, potential_energy_kj_mol: -11500 },
  ],
  damaged: [
    { time_ps: 0.04, restraint_center_nm: 3.7, end_to_end_nm: 3.7, extension_nm: 0.0, force_pn: -3, work_kj_mol: 0, potential_energy_kj_mol: -11400 },
    { time_ps: 0.08, restraint_center_nm: 3.8, end_to_end_nm: 3.76, extension_nm: 0.1, force_pn: 55, work_kj_mol: 0, potential_energy_kj_mol: -11400 },
  ],
}

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PairedExperimentCard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(listExperiments).mockResolvedValue([RUN])
  vi.mocked(getForceExtension).mockResolvedValue(CURVE)
})

describe('PairedExperimentCard (#5)', () => {
  it('renders the stiffness the API reports, not a built-in constant', async () => {
    renderCard()

    expect(await screen.findByText(/Paired mechanical experiment: 1UBQ/i)).toBeInTheDocument()
    expect(await screen.findByText(/662\.1/)).toBeInTheDocument()
    expect(await screen.findByText(/593\.4/)).toBeInTheDocument()
  })

  it('shows the run identity so a reader can trace the numbers', async () => {
    renderCard()
    expect(await screen.findByText(/1UBQ_GCR_MILD_A74_seed1/)).toBeInTheDocument()
    expect(await screen.findByText(/COMPLETED/)).toBeInTheDocument()
  })

  it('reports a stiffness increase as an increase rather than a loss', async () => {
    vi.mocked(listExperiments).mockResolvedValue([
      { ...RUN, baseline_stiffness: 600, damaged_stiffness: 640 },
    ])
    renderCard()
    // Damage does not reliably reduce stiffness in this dataset; the card must
    // read the sign from the data instead of assuming degradation.
    expect(await screen.findByText(/no loss measured/i)).toBeInTheDocument()
  })

  it('flags a run that failed QC instead of badging it as validated', async () => {
    vi.mocked(listExperiments).mockResolvedValue([
      {
        ...RUN,
        status: 'QC_FAILED',
        qc_failures: ['r2 0.02 below 0.5'],
        baseline_stiffness: null,
        damaged_stiffness: null,
      },
    ])
    renderCard()
    expect(await screen.findByText(/QC_FAILED/)).toBeInTheDocument()
    expect(await screen.findByText(/did not pass QC/i)).toBeInTheDocument()
  })

  it('explains itself when no experiments exist', async () => {
    vi.mocked(listExperiments).mockResolvedValue([])
    renderCard()
    await waitFor(() =>
      expect(screen.getByText(/No experiments are present/i)).toBeInTheDocument(),
    )
  })

  it('offers JSON and CSV of the fetched run', async () => {
    renderCard()
    expect(await screen.findByRole('button', { name: /json/i })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /csv/i })).toBeInTheDocument()
  })
})
