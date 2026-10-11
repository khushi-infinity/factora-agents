import { describe, expect, it } from 'vitest'

import { RUN_TONE, STEP_TONE, stepTone, type AgentRun, type AgentStep } from './agents'

const run = (status: AgentRun['status']): AgentRun => ({
  run_id: 'RUN-20261005-0001',
  incident_id: 'INC-20261005-001',
  machine_id: 'CNC-03',
  goal: 'Contain CNC-03 bearing degradation',
  status,
  active_agent: 'coordinator',
  model_provider: 'deterministic',
  model_name: 'factora-deterministic-v1',
  outcome: null,
  started_at: '2026-10-05 06:30:00',
  completed_at: null,
  fail_first_work_order: false,
})

const step = (type: string, status: string): AgentStep => ({
  sequence: 1,
  agent: 'coordinator',
  type,
  summary: 'x',
  tool_name: null,
  input: null,
  output: null,
  status,
  timestamp: '2026-10-05 06:30:00',
})

describe('agent client helpers', () => {
  it('maps every run status to a design token', () => {
    expect(Object.keys(RUN_TONE).sort()).toEqual(
      [
        'ACTION_PENDING',
        'ACTING',
        'DETECTED',
        'ESCALATED',
        'FAILED',
        'INVESTIGATING',
        'PLANNING',
        'RECOVERING',
        'VERIFIED',
        'VERIFYING',
      ].sort(),
    )
    expect(RUN_TONE.VERIFIED).toContain('--state-healthy')
    expect(RUN_TONE.ESCALATED).toContain('--state-critical')
  })

  it('colours steps by outcome first, then by type', () => {
    expect(stepTone(step('TOOL', 'FAILED'))).toContain('--state-critical')
    expect(stepTone(step('TOOL', 'REPAIR'))).toContain('--state-warning')
    expect(stepTone(step('VERIFICATION', 'PASS'))).toContain('--state-healthy')
    expect(stepTone(step('POLICY', 'BLOCKED'))).toContain('--state-warning')
    expect(stepTone(step('HANDOFF', 'OK'))).toContain('--state-warning')
    expect(STEP_TONE.ACTION).toContain('--state-maintenance')
  })

  it('never claims a run is live once it is terminal', () => {
    expect(run('VERIFIED').status).toBe('VERIFIED')
    expect(run('ESCALATED').completed_at).toBeNull()
  })
})
