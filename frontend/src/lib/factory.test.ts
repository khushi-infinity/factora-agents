import { describe, expect, it } from 'vitest'

import type { AdvanceResult, FactorySnapshot } from './factory'

describe('factory client types', () => {
  it('models a snapshot shape', () => {
    const snapshot: FactorySnapshot = {
      clock: '2026-10-05 06:00:00',
      machine_count: 23,
      state_distribution: { HEALTHY: 19, WARNING: 2, CRITICAL: 1, MAINTENANCE: 1, OFFLINE: 1 },
      open_incidents: [],
    }
    expect(snapshot.machine_count).toBe(23)
  })

  it('models an advance result', () => {
    const result: AdvanceResult = {
      clock: '2026-10-05 07:00:00',
      emitted_readings: 132,
      cnc03_state: 'CRITICAL',
      open_incidents: 1,
    }
    expect(result.emitted_readings).toBeGreaterThan(0)
  })
})
