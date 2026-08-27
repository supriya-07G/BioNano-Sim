/// <reference types="vite/client" />

/**
 * Typed environment variables.
 *
 * Declaring these explicitly (rather than relying on the loose index signature)
 * means a typo in an env var name is a compile error instead of `undefined` at
 * runtime.
 */
interface ImportMetaEnv {
  /** Base URL for the API. Empty means same-origin via the Vite dev proxy. */
  readonly VITE_API_BASE_URL?: string
  /** Where the dev proxy forwards /api. Used by vite.config.ts only. */
  readonly VITE_PROXY_TARGET?: string
  /** Job poll interval in ms; clamped to [500, 10000] at use site. */
  readonly VITE_JOB_POLL_INTERVAL_MS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
