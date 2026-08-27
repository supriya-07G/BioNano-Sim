import { request, requestText } from './api'
import type {
  CompareResponse,
  EngineHealth,
  ReadinessResponse,
  SimulationJobDetail,
  SimulationJobSummary,
  SimulationPreset,
  SimulationRequest,
  SimulationResults,
} from '@/types/simulation'

export const simulationKeys = {
  presets: ['simulation', 'presets'] as const,
  engine: ['simulation', 'engine'] as const,
  readiness: ['system', 'readiness'] as const,
  jobs: ['simulations'] as const,
  job: (jobId: string) => ['simulations', jobId] as const,
  results: (jobId: string) => ['simulations', jobId, 'results'] as const,
  compare: (a: string, b: string) => ['simulations', 'compare', a, b] as const,
  precomputed: ['precomputed'] as const,
  precomputedResults: (pdbId: string) => ['precomputed', pdbId, 'results'] as const,
}

export function getPresets(signal?: AbortSignal) {
  return request<SimulationPreset[]>('/simulation/presets', { signal })
}

export function getEngineHealth(signal?: AbortSignal) {
  return request<EngineHealth>('/simulation/engine', { signal })
}

export function getReadiness(signal?: AbortSignal) {
  return request<ReadinessResponse>('/system/readiness', { signal })
}

export function submitSimulation(body: SimulationRequest) {
  return request<SimulationJobDetail>('/simulations', { method: 'POST', body })
}

export function listJobs(limit = 100, signal?: AbortSignal) {
  return request<SimulationJobSummary[]>(`/simulations?limit=${limit}`, { signal })
}

export function getJob(jobId: string, signal?: AbortSignal) {
  return request<SimulationJobDetail>(`/simulations/${jobId}`, { signal })
}

export function cancelJob(jobId: string) {
  return request<SimulationJobDetail>(`/simulations/${jobId}/cancel`, {
    method: 'POST',
  })
}

export function deleteJob(jobId: string) {
  return request<void>(`/simulations/${jobId}`, { method: 'DELETE' })
}

export function getResults(jobId: string, signal?: AbortSignal) {
  return request<SimulationResults>(`/simulations/${jobId}/results`, { signal })
}

export function getJobStructure(
  jobId: string,
  which: 'final' | 'prepared' | 'topology' | 'input' = 'final',
  signal?: AbortSignal,
) {
  return requestText(`/simulations/${jobId}/structure?which=${which}`, signal)
}

export function compareJobs(jobIdA: string, jobIdB: string, signal?: AbortSignal) {
  return request<CompareResponse>(
    `/simulations/compare/${jobIdA}/${jobIdB}`,
    { signal },
  )
}

// --- Precomputed fallback --------------------------------------------------
export function listPrecomputed(signal?: AbortSignal) {
  return request<{ available: string[]; notice: string }>('/precomputed', { signal })
}

export function getPrecomputedResults(pdbId: string, signal?: AbortSignal) {
  return request<SimulationResults>(`/precomputed/${pdbId}/results`, { signal })
}

export function getPrecomputedStructure(
  pdbId: string,
  which: 'final' | 'input' = 'final',
  signal?: AbortSignal,
) {
  return requestText(`/precomputed/${pdbId}/structure?which=${which}`, signal)
}
