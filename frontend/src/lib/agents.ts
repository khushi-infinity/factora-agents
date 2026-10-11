/**
 * Typed client for the agent API (N3). Same rules as factory.ts: typed,
 * time-boxed, and it never invents data — the backend decides whether a run
 * used the real OpenRouter model or the deterministic stand-in.
 */
import { getJson, postJson } from './api'

export type RunStatus =
  | 'DETECTED'
  | 'INVESTIGATING'
  | 'PLANNING'
  | 'ACTION_PENDING'
  | 'ACTING'
  | 'VERIFYING'
  | 'RECOVERING'
  | 'VERIFIED'
  | 'FAILED'
  | 'ESCALATED'

export interface AgentStatus {
  model_provider: string
  model_name: string
  /** 'REAL LLM' or 'DETERMINISTIC TEST MODEL' — shown verbatim in the UI. */
  mode: string
  detail: string
  observability: string
  autonomous_actions: string[]
  failure_injection_available: boolean
}

export interface AgentRun {
  run_id: string
  incident_id: string
  machine_id: string
  goal: string
  status: RunStatus
  active_agent: string | null
  model_provider: string
  model_name: string
  outcome: string | null
  started_at: string
  completed_at: string | null
  fail_first_work_order: boolean
}

export interface AgentStep {
  sequence: number
  agent: string
  type: string
  summary: string
  tool_name: string | null
  input: unknown
  output: unknown
  status: string
  timestamp: string
}

export interface AgentRunDetail extends AgentRun {
  steps: AgentStep[]
}

export function fetchAgentStatus(): Promise<AgentStatus> {
  return getJson<AgentStatus>('/api/agents/status')
}

export function fetchAgentRuns(incidentId?: string): Promise<AgentRun[]> {
  const query = incidentId ? `?incident_id=${encodeURIComponent(incidentId)}` : ''
  return getJson<AgentRun[]>(`/api/agents/runs${query}`)
}

export function fetchAgentRun(runId: string): Promise<AgentRunDetail> {
  return getJson<AgentRunDetail>(`/api/agents/runs/${encodeURIComponent(runId)}`)
}

/** Manual/debug trigger. The flagship demo uses advanceSimulation instead. */
export function requestAgentRun(): Promise<{ escalations: number; runs: AgentRun[] }> {
  return postJson('/api/agents/run', {})
}

/** Design tokens from index.css (`--state-*`), used via inline style. */
export const RUN_TONE: Record<RunStatus, string> = {
  DETECTED: 'var(--state-warning)',
  INVESTIGATING: 'var(--state-maintenance)',
  PLANNING: 'var(--state-maintenance)',
  ACTION_PENDING: 'var(--state-maintenance)',
  ACTING: 'var(--state-maintenance)',
  VERIFYING: 'var(--state-maintenance)',
  RECOVERING: 'var(--state-warning)',
  VERIFIED: 'var(--state-healthy)',
  FAILED: 'var(--state-critical)',
  ESCALATED: 'var(--state-critical)',
}

export const RUN_LABEL: Record<RunStatus, string> = {
  VERIFIED: 'VERIFIED',
  ESCALATED: 'ESCALATED TO HUMAN',
  FAILED: 'FAILED',
  DETECTED: 'DETECTED',
  INVESTIGATING: 'INVESTIGATING',
  PLANNING: 'PLANNING',
  ACTION_PENDING: 'ACTION PENDING',
  ACTING: 'ACTING',
  VERIFYING: 'VERIFYING',
  RECOVERING: 'RECOVERING',
}

/** Which steps deserve a visible marker in the activity timeline. */
export const STEP_TONE: Record<string, string> = {
  HANDOFF: 'var(--state-warning)',
  STATUS: 'var(--state-maintenance)',
  DECISION: 'var(--state-maintenance)',
  TOOL: 'var(--state-maintenance)',
  ACTION: 'var(--state-maintenance)',
  POLICY: 'var(--state-maintenance)',
  VERIFICATION: 'var(--state-healthy)',
  RECOVERY: 'var(--state-warning)',
  ERROR: 'var(--state-critical)',
}

export function stepTone(step: Pick<AgentStep, 'type' | 'status'>): string {
  if (['FAILED', 'ESCALATED', 'FAIL'].includes(step.status)) return 'var(--state-critical)'
  if (['REPAIR', 'BLOCKED', 'NONE'].includes(step.status)) return 'var(--state-warning)'
  return STEP_TONE[step.type] ?? 'var(--state-maintenance)'
}
