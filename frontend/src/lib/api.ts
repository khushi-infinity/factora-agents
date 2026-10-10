/**
 * The single HTTP boundary between the SPA and the FastAPI backend.
 * Fresh N0 implementation: typed, time-boxed fetch; no data fabrication —
 * an error surfaces as an error.
 */

export type ObservabilityStatus = 'disabled' | 'active' | 'error'

export interface HealthPayload {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  time_utc: string
  uptime_s: number
  observability: {
    provider: string
    status: ObservabilityStatus
    detail: string | null
  }
}

export class ApiError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function getJson<T>(path: string, timeoutMs = 5000): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(path, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new ApiError(`Request failed: ${response.status} ${response.statusText}`, response.status)
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(`Request to ${path} timed out after ${timeoutMs} ms`)
    }
    throw new ApiError(error instanceof Error ? error.message : `Unknown error calling ${path}`)
  } finally {
    clearTimeout(timer)
  }
}

export function fetchHealth(): Promise<HealthPayload> {
  return getJson<HealthPayload>('/api/health')
}

export async function postJson<T>(path: string, body: unknown, timeoutMs = 10000): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new ApiError(`Request failed: ${response.status} ${response.statusText}`, response.status)
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(`Request to ${path} timed out after ${timeoutMs} ms`)
    }
    throw new ApiError(error instanceof Error ? error.message : `Unknown error calling ${path}`)
  } finally {
    clearTimeout(timer)
  }
}
