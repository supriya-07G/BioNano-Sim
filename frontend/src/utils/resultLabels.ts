/**
 * Provenance labels for results.
 *
 * These exact phrases are required by the project's scientific-integrity rules,
 * so they live in one place: an ML estimate, a live run and a precomputed result
 * must never share a label.
 */

export type ResultKind =
  | 'ml_prediction'
  | 'rapid_openmm'
  | 'precomputed'
  | 'minimisation_only'
  | 'visualization'
  | 'production_future'
  | 'proxy'

export const RESULT_LABELS: Record<ResultKind, string> = {
  ml_prediction: 'ML Prediction',
  rapid_openmm: 'Rapid OpenMM Simulation',
  precomputed: 'Precomputed OpenMM Result',
  minimisation_only: 'Energy Minimisation Only',
  visualization: 'Visualization Estimate',
  production_future: 'Production Simulation — Future Scope',
  proxy: 'Simulation-derived proxy',
}

/** Map a backend `result_label` string onto a badge kind. */
export function resultKindFromLabel(label: string | null | undefined): ResultKind {
  const value = (label ?? '').toLowerCase()
  if (value.includes('precomputed')) return 'precomputed'
  if (value.includes('minimisation') || value.includes('minimization')) {
    return 'minimisation_only'
  }
  if (value.includes('rapid openmm')) return 'rapid_openmm'
  if (value.includes('ml prediction')) return 'ml_prediction'
  if (value.includes('visualization')) return 'visualization'
  if (value.includes('future scope')) return 'production_future'
  return 'rapid_openmm'
}
