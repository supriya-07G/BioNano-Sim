import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PairedExperimentCard } from '../PairedExperimentCard'

describe('PairedExperimentCard Component (#5)', () => {
  it('renders 1UBQ paired experiment header and quality status badge', () => {
    render(<PairedExperimentCard />)

    expect(screen.getByText(/Paired Mechanical Experiment: Ubiquitin \(1UBQ\)/i)).toBeInTheDocument()
    expect(screen.getByText('PASSED_VALIDATION')).toBeInTheDocument()
  })

  it('displays correct stiffness metrics and percentage loss', () => {
    render(<PairedExperimentCard />)

    expect(screen.getByText('142.5')).toBeInTheDocument() // Baseline
    expect(screen.getByText('89.2')).toBeInTheDocument() // Damaged
    expect(screen.getByText('-37.4% mechanical degradation')).toBeInTheDocument() // Pct loss
  })

  it('renders JSON and CSV download buttons', () => {
    render(<PairedExperimentCard />)

    const jsonBtn = screen.getByRole('button', { name: /json/i })
    const csvBtn = screen.getByRole('button', { name: /csv/i })

    expect(jsonBtn).toBeInTheDocument()
    expect(csvBtn).toBeInTheDocument()
  })
})
