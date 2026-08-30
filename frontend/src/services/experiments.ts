import { request, requestText } from './api'
import type {
  ExperimentDetail,
  ExperimentImportRequest,
  ExperimentImportResponse,
  ExperimentSummary,
  PairedForceExtension,
} from '@/types/experiment'

export const experimentKeys = {
  all: ['experiments'] as const,
  list: (limit?: number) => ['experiments', 'list', limit] as const,
  detail: (id: string) => ['experiments', 'detail', id] as const,
  forceExtension: (id: string) => ['experiments', 'force-extension', id] as const,
  structure: (id: string, condition: string) =>
    ['experiments', 'structure', id, condition] as const,
  report: (id: string) => ['experiments', 'report', id] as const,
}

export function listExperiments(limit = 100, signal?: AbortSignal) {
  return request<ExperimentSummary[]>(`/experiments?limit=${limit}`, { signal })
}

export function getExperiment(experimentId: string, signal?: AbortSignal) {
  return request<ExperimentDetail>(`/experiments/${experimentId}`, { signal })
}

export function getForceExtension(experimentId: string, signal?: AbortSignal) {
  return request<PairedForceExtension>(`/experiments/${experimentId}/force-extension`, {
    signal,
  })
}

export function getExperimentStructure(
  experimentId: string,
  condition: string,
  signal?: AbortSignal,
) {
  return requestText(`/experiments/${experimentId}/structures/${condition}`, signal)
}

export function importExperiment(body: ExperimentImportRequest) {
  return request<ExperimentImportResponse>('/experiments/import', {
    method: 'POST',
    body,
  })
}
