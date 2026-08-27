import { request } from './api'
import type {
  ModelInfo,
  PredictionRequest,
  PredictionResponse,
  ScenariosResponse,
} from '@/types/prediction'

export const predictionKeys = {
  model: ['model'] as const,
  scenarios: ['scenarios'] as const,
}

export function getModelInfo(signal?: AbortSignal) {
  return request<ModelInfo>('/model', { signal })
}

export function getScenarios(signal?: AbortSignal) {
  return request<ScenariosResponse>('/scenarios', { signal })
}

export function createPrediction(body: PredictionRequest) {
  return request<PredictionResponse>('/predictions', { method: 'POST', body })
}
