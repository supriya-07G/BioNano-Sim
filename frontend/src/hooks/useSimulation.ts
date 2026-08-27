/** Simulation submission, presets, readiness and history. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  cancelJob,
  deleteJob,
  getEngineHealth,
  getPresets,
  getReadiness,
  getResults,
  listJobs,
  listPrecomputed,
  simulationKeys,
  submitSimulation,
} from '@/services/simulations'
import { isTerminal, type SimulationJobDetail, type SimulationRequest } from '@/types/simulation'

export function usePresets() {
  return useQuery({
    queryKey: simulationKeys.presets,
    queryFn: ({ signal }) => getPresets(signal),
    staleTime: Infinity,
    retry: 1,
  })
}

export function useEngineHealth() {
  return useQuery({
    queryKey: simulationKeys.engine,
    queryFn: ({ signal }) => getEngineHealth(signal),
    staleTime: 30_000,
    retry: 1,
  })
}

export function useReadiness(options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: simulationKeys.readiness,
    queryFn: ({ signal }) => getReadiness(signal),
    staleTime: 15_000,
    refetchInterval: options.refetchInterval,
    retry: 1,
  })
}

/** History, read from the job directories on disk. */
export function useJobs(limit = 100, options: { refetchInterval?: number } = {}) {
  return useQuery({
    queryKey: [...simulationKeys.jobs, limit],
    queryFn: ({ signal }) => listJobs(limit, signal),
    staleTime: 5_000,
    refetchInterval: options.refetchInterval,
    retry: 1,
  })
}

export function useResults(jobId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: simulationKeys.results(jobId ?? 'none'),
    queryFn: ({ signal }) => getResults(jobId as string, signal),
    enabled: Boolean(jobId) && enabled,
    // A completed job's results never change, so cache them hard.
    staleTime: Infinity,
    retry: (failureCount, error) => {
      const status = (error as { status?: number })?.status
      if (status === 404) return false
      return failureCount < 2
    },
  })
}

export function usePrecomputedList() {
  return useQuery({
    queryKey: simulationKeys.precomputed,
    queryFn: ({ signal }) => listPrecomputed(signal),
    staleTime: Infinity,
    retry: 1,
  })
}

export function useSubmitSimulation() {
  const queryClient = useQueryClient()
  return useMutation<SimulationJobDetail, unknown, SimulationRequest>({
    mutationFn: submitSimulation,
    retry: false,
    onSuccess: (job) => {
      // Seed the job cache so the monitor renders immediately, then let history
      // refresh in the background.
      queryClient.setQueryData(simulationKeys.job(job.job_id), job)
      void queryClient.invalidateQueries({ queryKey: simulationKeys.jobs })
      void queryClient.invalidateQueries({ queryKey: simulationKeys.readiness })
    },
  })
}

export function useCancelJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cancelJob,
    retry: false,
    onSuccess: (job) => {
      queryClient.setQueryData(simulationKeys.job(job.job_id), job)
      void queryClient.invalidateQueries({ queryKey: simulationKeys.jobs })
    },
  })
}

export function useDeleteJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteJob,
    retry: false,
    onSuccess: (_data, jobId) => {
      queryClient.removeQueries({ queryKey: simulationKeys.job(jobId) })
      queryClient.removeQueries({ queryKey: simulationKeys.results(jobId) })
      void queryClient.invalidateQueries({ queryKey: simulationKeys.jobs })
      void queryClient.invalidateQueries({ queryKey: simulationKeys.readiness })
    },
  })
}

/** True when any job on the server is still running: blocks a second submit. */
export function useHasActiveJob(): { active: boolean; jobId: string | null } {
  const { data } = useJobs(50, { refetchInterval: 4000 })
  const running = data?.find((job) => !isTerminal(job.status))
  return { active: Boolean(running), jobId: running?.job_id ?? null }
}
