import { request } from './api'

export interface RankingWeights {
  stiffness_retention: number
  baseline_strength: number
  structural_stability: number
  uncertainty_penalty: number
  out_of_domain_penalty: number
}

export interface CandidateObjectiveScore {
  rank: number
  pdb_id: string
  name: string
  uniprot: string
  baseline_stiffness_pnnm: number
  damaged_stiffness_pnnm: number
  stiffness_retained_pct: number
  uncertainty_sigma: number
  sasa_preservation_pct: number
  ood_distance: number
  subscores: {
    stiffness_retention: number
    baseline_strength: number
    structural_stability: number
  }
  penalties: {
    uncertainty: number
    out_of_domain: number
  }
  composite_score: number
  is_pareto_optimal: boolean
  explanation: string
  provenance: Record<string, unknown>
}

export interface RankingResponse {
  mode: 'REAL_EMPIRICAL_PARETO' | 'MOCK_DEMO_RANKING'
  total_candidates: number
  pareto_frontier_ids: string[]
  weights_used: RankingWeights
  candidates: CandidateObjectiveScore[]
}

export async function fetchRankings(
  weights?: RankingWeights,
  allowMock = false,
  signal?: AbortSignal,
): Promise<RankingResponse> {
  const query = allowMock ? '?allow_mock=true' : '?allow_mock=false'
  if (weights) {
    return request<RankingResponse>(`/candidates/rank${query}`, {
      method: 'POST',
      body: weights,
      signal,
    })
  }
  return request<RankingResponse>(`/candidates/rank${query}`, {
    method: 'GET',
    signal,
  })
}
