/**
 * Pure presentation helpers for the health payload. Free of React and network
 * access so they unit-test cleanly. Fresh N0 implementation.
 */
import type { HealthPayload, ObservabilityStatus } from './api'

export type Tone = 'ok' | 'neutral' | 'warn' | 'error'

const OBSERVABILITY_TONES: Record<ObservabilityStatus, Tone> = {
  disabled: 'neutral',
  active: 'ok',
  error: 'warn',
}

export function observabilityLabel(status: ObservabilityStatus): string {
  switch (status) {
    case 'active':
      return 'neatlogs tracing active'
    case 'disabled':
      return 'neatlogs not configured (NEATLOGS_API_KEY missing) — app runs normally'
    case 'error':
      return 'neatlogs init failed — app continues without tracing'
  }
}

export function observabilityTone(status: ObservabilityStatus): Tone {
  return OBSERVABILITY_TONES[status] ?? 'neutral'
}

export interface HealthSummary {
  label: string
  tone: Tone
  detail: string
}

/** One sentence the operator can act on; never overstates the backend state. */
export function summariseHealth(payload: HealthPayload): HealthSummary {
  const detail = payload.observability.detail ?? ''

  if (payload.status === 'ok') {
    return { label: 'Backend reachable', tone: 'ok', detail }
  }
  return { label: 'Backend reachable · degraded', tone: 'warn', detail }
}
