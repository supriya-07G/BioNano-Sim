/**
 * Zod schemas for the experiment form.
 *
 * Bounds mirror the backend's Pydantic models so the user gets immediate
 * feedback, but the backend remains the authority — these are a convenience,
 * never the only check.
 */

import { z } from 'zod'

export const DOSE_UNITS = ['Gy', 'mGy', 'kGy', 'rad'] as const

/**
 * Temperature is limited to 100-500 K for the same reason the backend limits
 * it: below ~100 K the implicit-solvent model and HBonds constraints stop being
 * meaningful, and above ~500 K a 2 fs timestep goes unstable.
 */
export const TEMPERATURE_MIN = 100
export const TEMPERATURE_MAX = 500

export const experimentSchema = z.object({
  scenarioId: z.string().min(1, 'Choose a radiation scenario.'),
  presetId: z.string().min(1, 'Choose a simulation preset.'),
  chainId: z
    .string()
    .min(1, 'Choose a chain.')
    .max(4, 'A chain identifier is at most 4 characters.'),
  dose: z
    .number({ invalid_type_error: 'Dose must be a number.' })
    .min(0, 'Dose cannot be negative.')
    .max(1_000_000, 'Dose is implausibly large.'),
  doseUnit: z.enum(DOSE_UNITS),
  exposureDurationDays: z
    .number({ invalid_type_error: 'Duration must be a number.' })
    .min(0, 'Duration cannot be negative.')
    .max(100_000, 'Duration is implausibly long.'),
  temperatureKelvin: z
    .number({ invalid_type_error: 'Temperature must be a number.' })
    .min(TEMPERATURE_MIN, `Below ${TEMPERATURE_MIN} K the solvent model is not meaningful.`)
    .max(TEMPERATURE_MAX, `Above ${TEMPERATURE_MAX} K the integrator is unstable at 2 fs.`),
  mechanicalForcePn: z
    .number({ invalid_type_error: 'Force must be a number.' })
    .min(0, 'Force cannot be negative.')
    .max(10_000, 'Force is implausibly large.'),
  randomSeed: z
    .number({ invalid_type_error: 'Seed must be a whole number.' })
    .int('Seed must be a whole number.')
    .min(0, 'Seed cannot be negative.')
    .max(2_147_483_647, 'Seed exceeds the 32-bit limit.'),
  topNResidues: z
    .number({ invalid_type_error: 'Residue count must be a whole number.' })
    .int()
    .min(1, 'Score at least one residue.')
    .max(50, 'At most 50 residues.'),
})

export type ExperimentFormValues = z.infer<typeof experimentSchema>

/** Client-side pre-check mirroring the backend's upload rules. */
export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024

export function validatePdbFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!name.endsWith('.pdb') && !name.endsWith('.ent')) {
    return 'Only .pdb (or .ent) files are accepted. mmCIF is not supported in this MVP.'
  }
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_UPLOAD_BYTES) {
    return `The file is ${(file.size / 1e6).toFixed(1)} MB, above the 8 MB limit.`
  }
  return null
}
