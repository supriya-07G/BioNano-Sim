import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ScopeNotice } from '../ScientificNotice'

describe('ScientificNotice Components', () => {
  it('renders ScopeNotice with scientific disclaimer statement', () => {
    render(<ScopeNotice />)
    expect(screen.getByText(/Scientific scope/i)).toBeInTheDocument()
    expect(screen.getByText(/Radiation is not simulated/i)).toBeInTheDocument()
  })
})
