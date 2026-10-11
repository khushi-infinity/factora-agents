/**
 * Typed client for the FactoryWorld API (N1 reads + N2 context). Same rules as
 * api.ts: typed, time-boxed, no data fabrication. Fresh implementation.
 */
import { getJson, postJson } from './api'
import type { AgentRun } from './agents'

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
  /** Runs the watcher started during this advance (N3). */
  agent_runs: AgentRun[]
  watcher: 'escalated' | 'quiet'
}

export interface AdvanceOptions {
  /** Run the Factory Watcher after advancing (default true, per the API). */
  triggerAgents?: boolean
  /** Demo recovery scenario: the first work-order tool call fails on purpose. */
  failFirstWorkOrder?: boolean
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

export function advanceSimulation(
  minutes: number,
  options: AdvanceOptions = {},
): Promise<AdvanceResult> {
  return postJson<AdvanceResult>('/api/demo/advance', {
    minutes,
    trigger_agents: options.triggerAgents ?? true,
    fail_first_work_order: options.failFirstWorkOrder ?? false,
  })
}

export function resetSimulation(): Promise<ResetResult> {
  return postJson<ResetResult>('/api/demo/reset', {})
}

// ── N2: machine inventory + contextual Inspector payloads ─────────────

export interface TwinMachine {
  machine_id: string
  name: string
  machine_type: string
  line: string
  state: 'HEALTHY' | 'WARNING' | 'CRITICAL' | 'MAINTENANCE' | 'OFFLINE'
  health_score: number | null
  x_m: number
  y_m: number
  z_m: number
}

export interface TelemetryPoint {
  machine_id: string
  ts: string
  vibration_mm_s: number
  bearing_temp_c: number
  spindle_rpm: number | null
  motor_current_a: number | null
  cycle_time_s: number | null
  production_rate_uph: number | null
  defect_rate_pct: number | null
}

export interface MaintenanceRecord {
  event_id: number
  machine_id: string
  event_date: string
  issue: string
  action: string
  part_id: string | null
  downtime_hours: number
  cost_usd: number | null
}

export interface WorkOrder {
  work_order_id: string
  machine_id: string
  issue: string
  proposed_action: string
  status: string
  priority: string
  scheduled_for: string | null
  estimated_cost_usd: number | null
  source: string
  created_at: string
}

export interface ProductionJob {
  job_id: string
  part_no: string
  machine_id: string
  target_qty: number
  produced_qty: number
  good_qty: number
  scrap_qty: number
  status: string
  started_at: string | null
  due_at: string | null
  priority: number
}

export interface MachineContext {
  machine: TwinMachine & {
    manufacturer: string | null
    model: string | null
    installed_year: number | null
    output_per_hour: number
    cost_per_hour_usd: number
    contribution_per_unit_usd: number
    scrap_cost_per_unit_usd: number
    latest_telemetry: TelemetryPoint | null
  }
  telemetry: TelemetryPoint[]
  maintenance: MaintenanceRecord[]
  work_orders: WorkOrder[]
  production: ProductionJob[]
  incidents: Incident[]
  economics_note: 'Synthetic demo economics'
}

export interface FactoryLine {
  line: string
  machine_ids: string[]
  machine_count: number
}

export function fetchMachines(): Promise<TwinMachine[]> {
  return getJson<TwinMachine[]>('/api/machines')
}

export function fetchMachineContext(machineId: string): Promise<MachineContext> {
  return getJson<MachineContext>(`/api/machines/${encodeURIComponent(machineId)}/context`)
}

export function fetchLines(): Promise<FactoryLine[]> {
  return getJson<FactoryLine[]>('/api/factory/lines')
}
