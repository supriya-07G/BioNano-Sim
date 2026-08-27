/** Prediction mutation plus the model/scenario metadata queries. */

import { useMutation, useQuery } from '@tanstack/react-query'

import {
  createPrediction,
  getModelInfo,
  getScenarios,
  predictionKeys,
} from '@/services/predictions'
import type { PredictionRequest, PredictionResponse } from '@/types/prediction'

/** Model status. Cached for the session; it only changes on a backend restart. */
export function useModelInfo() {
  return useQuery({
    queryKey: predictionKeys.model,
    queryFn: ({ signal }) => getModelInfo(signal),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}

/** Scenario registry. Static data shipped with the repo. */
export function useScenarios() {
  return useQuery({
    queryKey: predictionKeys.scenarios,
    queryFn: ({ signal }) => getScenarios(signal),
    staleTime: Infinity,
    retry: 1,
  })
}

export function usePrediction() {
  return useMutation<PredictionResponse, unknown, PredictionRequest>({
    mutationFn: createPrediction,
    // A rejected prediction (unsupported scenario, unavailable model) is a
    // normal outcome to display, not something to retry.
    retry: false,
  })
}
