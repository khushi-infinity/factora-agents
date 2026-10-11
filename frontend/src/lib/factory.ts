/**
 * Typed client for the FactoryWorld API (N1 reads + N2 context). Same rules as
 * api.ts: typed, time-boxed, no data fabrication. Fresh implementation.
 */
import { getJson, postJson } from './api'
import type { AgentRun, AgentStep } from './agents'
export type { AgentStep }

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
  output_per_hour: number | null
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

// ── Spare Parts ───────────────────────────────────────────────────────────

export interface SparePart {
  part_id: string
  name: string
  category: string
  compatible_types: string
  stock_qty: number
  reorder_point: number
  unit_cost_usd: number
  lead_time_days: number
  supplier: string | null
  stock_status: 'IN_STOCK' | 'LOW_STOCK' | 'CRITICAL_STOCK'
}

export function fetchSpareParts(): Promise<SparePart[]> {
  return getJson<SparePart[]>('/api/spare-parts')
}

export function fetchSparePart(partId: string): Promise<SparePart> {
  return getJson<SparePart>(`/api/spare-parts/${encodeURIComponent(partId)}`)
}

// ── Work Orders ───────────────────────────────────────────────────────────

export interface WorkOrderCreate {
  machine_id: string
  issue: string
  proposed_action: string
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  estimated_cost_usd?: number
}

export interface WorkOrderUpdate {
  status?: 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'
  priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  estimated_cost_usd?: number
}

export function fetchWorkOrders(openOnly?: boolean): Promise<WorkOrder[]> {
  const query = openOnly ? '?open_only=true' : ''
  return getJson<WorkOrder[]>(`/api/work-orders${query}`)
}

export function fetchWorkOrder(workOrderId: string): Promise<WorkOrder> {
  return getJson<WorkOrder>(`/api/work-orders/${encodeURIComponent(workOrderId)}`)
}

export function createWorkOrder(payload: WorkOrderCreate): Promise<WorkOrder> {
  return postJson<WorkOrder>('/api/work-orders', payload)
}

export function updateWorkOrder(workOrderId: string, payload: WorkOrderUpdate): Promise<WorkOrder> {
  return postJson<WorkOrder>(`/api/work-orders/${encodeURIComponent(workOrderId)}`, payload)
}

// ── OEE ────────────────────────────────────────────────────────────────────

export interface OEEBreakdown {
  availability: number
  performance: number
  quality: number
  oee: number
  downtime_hours: number
  planned_downtime_hours: number
  unplanned_downtime_hours: number
  lost_speed_units: number
  scrap_units: number
  total_produced: number
  good_units: number
}

export interface OEELine {
  line: string
  oee: number
  availability: number
  performance: number
  quality: number
  machines: number
}

export interface OEEMachine {
  machine_id: string
  line: string
  oee: number
  availability: number
  performance: number
  quality: number
  target_units: number
  actual_units: number
  good_units: number
  scrap_units: number
  unplanned_downtime_hours: number
}

export interface OEEFactory {
  factory_oee: number
  lines: OEELine[]
  machines: OEEMachine[]
  loss_breakdown: Record<string, number>
}

export function fetchOEEFactory(): Promise<OEEFactory> {
  return getJson<OEEFactory>('/api/oee')
}

export function fetchOEELines(): Promise<OEELine[]> {
  return getJson<OEELine[]>('/api/oee/lines')
}

export function fetchOEEMachines(): Promise<OEEMachine[]> {
  return getJson<OEEMachine[]>('/api/oee/machines')
}

// ── Predictive Maintenance ────────────────────────────────────────────────

export interface PredictiveRisk {
  machine_id: string
  name: string
  line: string
  machine_type: string
  risk_score: number
  trend: 'improving' | 'stable' | 'degrading'
  likely_issue: string | null
  evidence: string[]
  urgency: 'high' | 'medium' | 'low'
  spare_part_id: string | null
  open_work_orders: number
  risk_category: 'HIGH' | 'MEDIUM' | 'LOW'
}

export function fetchPredictiveMaintenance(): Promise<PredictiveRisk[]> {
  return getJson<PredictiveRisk[]>('/api/predictive-maintenance')
}

// ── Planner ────────────────────────────────────────────────────────────────

export interface PlannerItem {
  work_order_id: string
  machine_id: string
  machine_name: string
  machine_type: string
  line: string
  issue: string
  priority: string
  status: string
  scheduled_for: string | null
  estimated_cost_usd: number | null
  required_parts: string[]
  parts_available: boolean
  estimated_downtime_hours: number
  planned_cost_usd: number
  production_impact_usd: number
  source: string
}

export function fetchPlanner(): Promise<PlannerItem[]> {
  return getJson<PlannerItem[]>('/api/planner')
}

// ── Agent Runs ─────────────────────────────────────────────────────────────

export interface AgentRunSummary {
  run_id: string
  incident_id: string
  machine_id: string
  goal: string
  status: string
  active_agent: string | null
  model_provider: string
  model_name: string
  outcome: string | null
  started_at: string
  completed_at: string | null
  fail_first_work_order: boolean
}

export function fetchAgentRunSummaries(incidentId?: string): Promise<AgentRunSummary[]> {
  const query = incidentId ? `?incident_id=${encodeURIComponent(incidentId)}` : ''
  return getJson<AgentRunSummary[]>(`/api/agent-runs${query}`)
}

export function fetchAgentRunDetail(runId: string): Promise<{ run: AgentRun; steps: AgentStep[] }> {
  return getJson<{ run: AgentRun; steps: AgentStep[] }>(`/api/agent-runs/${encodeURIComponent(runId)}/detail`)
}

// ── Optimisation ───────────────────────────────────────────────────────────

export interface Optimisation {
  paused_job_id: string
  source_machine_id: string
  target_machine_id: string | null
  candidates: Array<{
    machine_id: string
    compatible: boolean
    machine_state: string
    queue_behind_units: number
    queue_hours: number
    est_run_hours: number
    incremental_cost_usd: number
    delay_hours: number
  }>
  recommended_candidate: string | null
  do_nothing_cost_usd: number
  reroute_cost_usd: number
  loss_avoided_usd: number
  net_benefit_usd: number
  finance_recommendation: 'REROUTE' | 'WAIT'
  action_taken: 'REROUTE' | 'WAIT'
  verification: {
    checks_passed: number
    total_checks: number
  } | null
}

export function fetchOptimisation(incidentId: string): Promise<Optimisation> {
  return getJson<Optimisation>(`/api/optimisation/${encodeURIComponent(incidentId)}`)
}
