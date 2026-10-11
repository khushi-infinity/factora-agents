import { describe, expect, it } from 'vitest'

import type { AgentRun } from './agents'
import type { AdvanceResult, FactorySnapshot } from './factory'

const agentRunFixture = (): AgentRun => ({
  run_id: 'RUN-20261005-0001',
  incident_id: 'INC-20261005-001',
  machine_id: 'CNC-03',
  goal: 'Contain CNC-03 bearing degradation',
  status: 'VERIFIED',
  active_agent: 'coordinator',
  model_provider: 'deterministic',
  model_name: 'factora-deterministic-v1',
  outcome: 'contained',
  started_at: '2026-10-05 06:30:00',
  completed_at: '2026-10-05 06:30:00',
  fail_first_work_order: false,
})

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
      cnc03_state: 'MAINTENANCE',
      open_incidents: 1,
      agent_runs: [agentRunFixture()],
      watcher: 'escalated',
    }
    expect(result.emitted_readings).toBeGreaterThan(0)
    expect(result.agent_runs[0].status).toBe('VERIFIED')
  })
})
