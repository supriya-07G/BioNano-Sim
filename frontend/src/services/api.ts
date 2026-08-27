/**
 * HTTP layer.
 *
 * The backend always answers errors with the same envelope
 * (`{ error: { code, message, details, request_id } }`), so we unwrap it once
 * here into a typed `ApiError`. Every component can then branch on `code`
 * rather than parsing strings.
 */

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').trim()

/** Empty base means same-origin, which the Vite dev proxy forwards to the API. */
export const API_BASE = RAW_BASE.replace(/\/+$/, '')
export const API_PREFIX = `${API_BASE}/api/v1`

export interface ApiErrorPayload {
  code: string
  message: string
  details: unknown[]
  request_id: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown[]
  readonly requestId: string

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code
    this.details = payload.details ?? []
    this.requestId = payload.request_id ?? 'unknown'
  }

  /** True when the failure is a missing dependency rather than bad input. */
  get isUnavailable(): boolean {
    return (
      this.status === 503 ||
      this.code === 'MODEL_UNAVAILABLE' ||
      this.code === 'SIMULATION_ENGINE_UNAVAILABLE'
    )
  }

  /** True when another job holds the single worker slot. */
  get isConflict(): boolean {
    return this.status === 409
  }

  /** Human-readable extra lines, for an error panel. */
  get detailLines(): string[] {
    return this.details.flatMap((detail) => {
      if (typeof detail === 'string') return [detail]
      if (detail && typeof detail === 'object') {
        const record = detail as Record<string, unknown>
        if (typeof record.field === 'string' && typeof record.message === 'string') {
          return [`${record.field}: ${record.message}`]
        }
        return [JSON.stringify(record)]
      }
      return []
    })
  }
}

/** Thrown when the backend cannot be reached at all. */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super(
      'Could not reach the BioNano-Sim API. Confirm the backend is running: ' +
        'uvicorn app.main:app --reload --port 8000',
    )
    this.name = 'NetworkError'
    this.cause = cause
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  /** Send FormData verbatim; the browser sets the multipart boundary. */
  formData?: FormData
}

async function toApiError(response: Response): Promise<ApiError> {
  let payload: ApiErrorPayload = {
    code: `HTTP_${response.status}`,
    message: `${response.status} ${response.statusText}`,
    details: [],
    request_id: response.headers.get('X-Request-ID') ?? 'unknown',
  }
  try {
    const body = await response.json()
    if (body && typeof body === 'object' && 'error' in body) {
      payload = { ...payload, ...(body as { error: ApiErrorPayload }).error }
    }
  } catch {
    // A non-JSON error body (e.g. a proxy failure page) keeps the default.
  }
  return new ApiError(response.status, payload)
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, formData } = options

  const init: RequestInit = { method, signal }
  if (formData) {
    init.body = formData
  } else if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(`${API_PREFIX}${path}`, init)
  } catch (cause) {
    // An aborted request is expected on unmount and must not surface as an error.
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new NetworkError(cause)
  }

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Fetch a text document (PDB coordinates, logs). */
export async function requestText(path: string, signal?: AbortSignal): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_PREFIX}${path}`, { signal })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new NetworkError(cause)
  }
  if (!response.ok) throw await toApiError(response)
  return response.text()
}

/** Absolute URL for a download the browser should handle itself. */
export function downloadUrl(path: string): string {
  return `${API_PREFIX}${path}`
}

/** Trigger a browser download without navigating away from the app. */
export function triggerDownload(path: string, filename: string): void {
  const anchor = document.createElement('a')
  anchor.href = downloadUrl(path)
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}
