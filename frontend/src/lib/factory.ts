/**
 * Typed client for the N1 FactoryWorld API. Same rules as api.ts: typed,
 * time-boxed, no data fabrication. Fresh implementation.
 */
import { getJson, postJson } from './api'

export interface Incident {
  incident_id: string
  machine_id: string
  type: string
  severity: string
  status: string
  opened_at: string
  resolved_at: string | null
  summary: string
  current_owner: string | null
  recommended_action: string | null
}

export interface FactorySnapshot {
  clock: string
  machine_count: number
  state_distribution: Record<string, number>
  open_incidents: Incident[]
}

export interface AdvanceResult {
  clock: string
  emitted_readings: number
  cnc03_state: string | null
  open_incidents: number
}

export interface ResetResult {
  status: 'reset'
  clock: string
  machines: number
  telemetry_rows: number
}

export function fetchFactorySnapshot(): Promise<FactorySnapshot> {
  return getJson<FactorySnapshot>('/api/factory')
}

export function advanceSimulation(minutes: number): Promise<AdvanceResult> {
  return postJson<AdvanceResult>('/api/demo/advance', { minutes })
}

export function resetSimulation(): Promise<ResetResult> {
  return postJson<ResetResult>('/api/demo/reset', {})
}
