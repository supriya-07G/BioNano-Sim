import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'framer-motion'
import { RouterProvider } from 'react-router-dom'

import { router } from './routes/router'

/**
 * Query defaults.
 *
 * `retry: 1` keeps a transient blip recoverable without hammering a backend
 * that is genuinely down. 4xx responses are never retried: an unsupported
 * scenario or an invalid id will fail identically on the second attempt, and
 * retrying only delays the error the user needs to see.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        const status = (error as { status?: number })?.status
        if (status !== undefined && status >= 400 && status < 500) return false
        return failureCount < 1
      },
    },
    mutations: { retry: false },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/*
        reducedMotion="user" makes every Framer animation respect the OS
        setting. The global CSS rule in globals.css cannot do this on its own:
        Framer animates via JavaScript, so an !important transition-duration
        never applies to it.
      */}
      <MotionConfig reducedMotion="user">
        <RouterProvider router={router} />
      </MotionConfig>
    </QueryClientProvider>
  )
}
