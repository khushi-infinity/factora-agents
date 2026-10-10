import { describe, expect, it } from 'vitest'

import type { HealthPayload } from './api'
import { observabilityLabel, observabilityTone, summariseHealth } from './health'

const payload = (status: 'ok' | 'degraded', obsStatus: 'active' | 'disabled' | 'error'): HealthPayload => ({
  status,
  service: 'factora',
  version: '0.1.0',
  environment: 'development',
  time_utc: '2026-01-01T00:00:00Z',
  uptime_s: 1,
  observability: { provider: 'neatlogs', status: obsStatus, detail: 'some detail' },
})

describe('observability helpers', () => {
  it('labels each observability status honestly', () => {
    expect(observabilityLabel('active')).toContain('neatlogs tracing active')
    expect(observabilityLabel('disabled')).toContain('not configured')
    expect(observabilityLabel('error')).toContain('init failed')
  })

  it('maps tones', () => {
    expect(observabilityTone('active')).toBe('ok')
    expect(observabilityTone('disabled')).toBe('neutral')
    expect(observabilityTone('error')).toBe('warn')
  })

  it('summarises ok and degraded states without overstating', () => {
    const healthyApp = summariseHealth(payload('ok', 'disabled'))
    expect(healthyApp.label).toBe('Backend reachable')
    expect(healthyApp.tone).toBe('ok')

    const degraded = summariseHealth(payload('degraded', 'error'))
    expect(degraded.label).toContain('degraded')
    expect(degraded.tone).toBe('warn')
  })
})
