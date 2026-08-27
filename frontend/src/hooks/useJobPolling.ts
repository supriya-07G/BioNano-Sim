/**
 * Poll one simulation job until it reaches a terminal state.
 *
 * Polling stops on its own the moment the job is completed/failed/cancelled —
 * `refetchInterval` returns `false`, which TanStack Query treats as "stop".
 * There is no `setInterval` to leak: unmounting the component removes the last
 * observer and the query goes idle, so nothing keeps firing after navigation.
 */

import { useQuery } from '@tanstack/react-query'

import { getJob, simulationKeys } from '@/services/simulations'
import { isTerminal, type SimulationJobDetail } from '@/types/simulation'

function pollInterval(): number {
  const raw = Number(import.meta.env.VITE_JOB_POLL_INTERVAL_MS)
  if (!Number.isFinite(raw)) return 1200
  // Clamp: sub-500 ms hammers the backend, above 10 s feels broken.
  return Math.min(10_000, Math.max(500, raw))
}

export const JOB_POLL_INTERVAL_MS = pollInterval()

export interface UseJobPollingResult {
  job: SimulationJobDetail | undefined
  isLoading: boolean
  isPolling: boolean
  error: unknown
  refetch: () => void
}

export function useJobPolling(
  jobId: string | null | undefined,
  options: { enabled?: boolean } = {},
): UseJobPollingResult {
  const enabled = Boolean(jobId) && options.enabled !== false

  const query = useQuery({
    queryKey: simulationKeys.job(jobId ?? 'none'),
    queryFn: ({ signal }) => getJob(jobId as string, signal),
    enabled,
    // Live job state is never fresh; always refetch on mount/focus.
    staleTime: 0,
    gcTime: 60_000,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return isTerminal(status) ? false : JOB_POLL_INTERVAL_MS
    },
    // Keep polling while the tab is in the background so a run finishing off
    // screen is still recorded; this is a local single-user app.
    refetchIntervalInBackground: true,
    // A job that 404s (deleted elsewhere) should not be retried forever.
    retry: (failureCount, error) => {
      const status = (error as { status?: number })?.status
      if (status === 404 || status === 400) return false
      return failureCount < 3
    },
  })

  return {
    job: query.data,
    isLoading: query.isLoading,
    isPolling: enabled && !isTerminal(query.data?.status),
    error: query.error,
    refetch: () => void query.refetch(),
  }
}
