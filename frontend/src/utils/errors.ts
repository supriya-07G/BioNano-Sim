/**
 * Turn any thrown value into something worth showing a user.
 *
 * Kept out of the component file so it can be reused (and so React Fast Refresh
 * still works for the components that render it).
 */

import type { LucideIcon } from 'lucide-react'
import { AlertCircle, ServerCrash, WifiOff } from 'lucide-react'

import { ApiError, NetworkError } from '@/services/api'

export interface DescribedError {
  title: string
  message: string
  /** Concrete next step, when we can name one. */
  hint: string | null
  details: string[]
  icon: LucideIcon
  requestId: string | null
}

/** Actionable remediation per backend error code. */
const HINTS: Record<string, string> = {
  MODEL_UNAVAILABLE:
    'The ML bundle could not be loaded. Run: python scripts/validate_model.py',
  SIMULATION_ENGINE_UNAVAILABLE:
    'OpenMM is unavailable in the backend environment. Install it with: pip install openmm==8.6.0',
  SCENARIO_NOT_ML_SUPPORTED:
    'Pick one of the three trained scenarios for an ML estimate, or run the simulation without one.',
  JOB_CONFLICT:
    'This local MVP runs one simulation at a time. Wait for the current job or cancel it.',
  CONCURRENCY_LIMIT:
    'This local MVP runs one simulation at a time. Wait for the current job or cancel it.',
  CHAIN_TOO_LARGE: 'Choose a smaller chain, or use the Minimisation-only preset.',
  CHAIN_TOO_SHORT: 'This chain has too few residues to build a meaningful system.',
  HYDROGEN_ADDITION_FAILED:
    'A residue does not match an amber14 template. Try the Minimisation-only preset, or a different chain.',
  SYSTEM_CONSTRUCTION_FAILED:
    'Usually a missing atom or unsupported residue. Try the Minimisation-only preset, or a different chain.',
  TEMPERATURE_OUT_OF_RANGE: 'Choose a temperature between 100 K and 500 K.',
  FILE_TOO_LARGE: 'Upload a file under 8 MB.',
  INVALID_FILE_TYPE: 'Upload a .pdb file. mmCIF is not supported in this MVP.',
  NO_PROTEIN_CHAIN:
    'The file has no chain of standard amino acids with Cα atoms. Nucleic-acid-only files are not supported.',
  INVALID_PDB_ID: 'Use a four-character PDB identifier from the approved list.',
}

export function describeError(error: unknown, fallbackTitle?: string): DescribedError {
  if (error instanceof NetworkError) {
    return {
      title: 'Cannot reach the backend',
      message: error.message,
      hint:
        'Start it with: cd backend && uvicorn app.main:app --reload --port 8000 ' +
        '(activate the virtual environment first).',
      details: [],
      icon: WifiOff,
      requestId: null,
    }
  }

  if (error instanceof ApiError) {
    return {
      title:
        fallbackTitle ??
        (error.isUnavailable ? 'Component unavailable' : 'Request failed'),
      message: error.message,
      hint: HINTS[error.code] ?? null,
      details: error.detailLines,
      icon: error.isUnavailable ? ServerCrash : AlertCircle,
      requestId: error.requestId,
    }
  }

  return {
    title: fallbackTitle ?? 'Something went wrong',
    message: error instanceof Error ? error.message : String(error),
    hint: null,
    details: [],
    icon: AlertCircle,
    requestId: null,
  }
}
