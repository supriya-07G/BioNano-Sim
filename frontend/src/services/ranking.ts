import { request } from './api'

/**
 * Objectives are exactly those the measured dataset supports.
 *
 * Two earlier ones -- SASA preservation and an out-of-domain distance -- were
 * removed rather than kept and filled with constants. A slider the user can
 * move for no effect is worse than an absent control: it looks like it works.
 */
export interface RankingWeights {
  stiffness_retention: number
  baseline_strength: number
  measurement_confidence: number
  uncertainty_penalty: number
}

export interface CandidateObjectiveScore {
  /** Null for candidates with no usable measurement; those are listed, not ranked. */
  rank: number | null
  pdb_id: string
  name: string
  uniprot: string
  baseline_stiffness_pnnm: number | null
  baseline_stiffness_sd: number | null
  damaged_stiffness_pnnm: number | null
  stiffness_retained_pct: number | null
  /** Seed spread as a fraction of the mean. The uncertainty term, measured. */
  relative_sd: number | null
  mean_fit_quality: number | null
  runs_passing_qc: number
  runs_screened: number
  resolved: boolean
  unresolved_reason: string | null
  qc_failure_reasons: string[]
  subscores: Record<string, number>
  penalties: Record<string, number>
  composite_score: number | null
  is_pareto_optimal: boolean
  explanation: string
  provenance: Record<string, unknown>
}

export interface RankingResponse {
  mode: 'MEASURED_STEERED_MD' | 'NO_MEASUREMENTS_AVAILABLE'
  total_candidates: number
  ranked_candidates: number
  pareto_frontier_ids: string[]
  weights_used: RankingWeights
  dataset: {
    source_file?: string
    available?: boolean
    proteins_screened?: number
    runs_screened?: number
    runs_passing_qc?: number
    resolved_proteins?: string[]
    unresolved_proteins?: string[]
    quality_gate?: string
  }
  candidates: CandidateObjectiveScore[]
}

export async function fetchRankings(
  weights?: RankingWeights,
  signal?: AbortSignal,
): Promise<RankingResponse> {
  if (weights) {
    return request<RankingResponse>('/candidates/rank', {
      method: 'POST',
      body: weights,
      signal,
    })
  }
  return request<RankingResponse>('/candidates/rank', { method: 'GET', signal })
}
