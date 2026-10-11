import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { fetchMachineContext, type MachineContext } from '../lib/factory'
import { STATE_LABELS, STATE_COLORS, lineLabel, type MachineState } from '../lib/twin'

export default function MachineDetail() {
  const { machineId } = useParams<{ machineId: string }>()
  const [context, setContext] = useState<MachineContext | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'live' | 'maintenance' | 'production' | 'agent'>('overview')

  useEffect(() => {
    if (!machineId) return
    let cancelled = false
    setLoading(true)
    fetchMachineContext(machineId)
      .then((ctx) => {
        if (!cancelled) {
          setContext(ctx)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load machine')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [machineId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        Loading machine details…
      </div>
    )
  }
  if (error) {
    return (
      <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">
        {error}
      </div>
    )
  }
  if (!context) {
    return (
      <div className="text-sm text-slate-500">
        Machine not found
      </div>
    )
  }

  const { machine } = context
  const state = machine.state as MachineState
  const openIncidents = context.incidents.filter((i) => i.status === 'OPEN')
  const openWorkOrders = context.work_orders.filter((wo) => wo.status !== 'CLOSED')
  const runningJobs = context.production.filter((j) => j.status === 'RUNNING')
  const queuedJobs = context.production.filter((j) => j.status === 'QUEUED')
  const pausedJobs = context.production.filter((j) => j.status === 'PAUSED')

  const points = context.telemetry.map((r) => ({
    ts: r.ts.slice(11, 16),
    vibration: r.vibration_mm_s,
    temp: r.bearing_temp_c,
    rpm: r.spindle_rpm,
    current: r.motor_current_a,
    rate: r.production_rate_uph,
  }))
  const tickEvery = Math.max(1, Math.floor(points.length / 5))

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/machines" className="text-sm text-blue-600 hover:underline mb-2 inline-block">
            ← Back to Machines
          </Link>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">{machine.machine_id}</h1>
          <p className="text-xs text-slate-500">
            {machine.name} · {machine.machine_type} · {lineLabel(machine.line)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold text-white"
            style={{ backgroundColor: STATE_COLORS[state] }}
          >
            {STATE_LABELS[state]}
          </span>
          <span className="text-xs text-slate-600">
            Health <span className="font-mono font-semibold">{machine.health_score ?? '—'}</span>/100
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200">
        {(['overview', 'live', 'maintenance', 'production', 'agent'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              activeTab === tab
                ? 'border-blue-500 text-blue-600'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Panels */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {/* Incidents */}
          {openIncidents.length > 0 && (
            <section className="rounded-lg border-2 border-red-300 bg-red-50 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-red-700">
                Critical Incident · {openIncidents.length} open
              </p>
              {openIncidents.map((incident) => (
                <div key={incident.incident_id} className="mt-2 border-t border-red-200 pt-2 first:border-0 first:pt-0">
                  <p className="font-mono text-[10px] text-red-500">{incident.incident_id} · opened {incident.opened_at}</p>
                  <p className="text-xs text-red-800">{incident.summary}</p>
                  {incident.recommended_action && (
                    <p className="mt-1 text-[11px] text-red-700/80">
                      Recommended: {incident.recommended_action}
                    </p>
                  )}
                </div>
              ))}
            </section>
          )}

          {/* Latest Telemetry */}
          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Latest Telemetry</h4>
            {machine.latest_telemetry ? (
              <dl className="mt-1.5 grid grid-cols-3 gap-x-3 gap-y-1.5 text-xs">
                <Fact label="Vibration" value={`${machine.latest_telemetry.vibration_mm_s.toFixed(2)} mm/s`} />
                <Fact label="Bearing Temp" value={`${machine.latest_telemetry.bearing_temp_c.toFixed(1)} °C`} />
                <Fact label="Defect Rate" value={`${(machine.latest_telemetry.defect_rate_pct ?? 0).toFixed(2)}%`} />
                {machine.latest_telemetry.spindle_rpm != null && (
                  <Fact label="Spindle" value={`${Math.round(machine.latest_telemetry.spindle_rpm)} rpm`} />
                )}
                {machine.latest_telemetry.motor_current_a != null && (
                  <Fact label="Motor" value={`${machine.latest_telemetry.motor_current_a.toFixed(1)} A`} />
                )}
                {machine.latest_telemetry.production_rate_uph != null && (
                  <Fact label="Rate" value={`${machine.latest_telemetry.production_rate_uph.toFixed(1)} u/h`} />
                )}
              </dl>
            ) : (
              <p className="mt-1.5 text-xs text-slate-400">No telemetry available.</p>
            )}
          </section>

          {/* Economics */}
          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Economics <span className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-[9px] font-semibold text-amber-700">Synthetic demo economics</span>
            </h4>
            <dl className="mt-1.5 grid grid-cols-4 gap-x-3 gap-y-1.5 text-xs">
              <Fact label="Output" value={`${machine.output_per_hour.toFixed(1)} units/h`} />
              <Fact label="Operating Cost" value={`$${machine.cost_per_hour_usd.toFixed(2)}/h`} />
              <Fact label="Contribution" value={`$${machine.contribution_per_unit_usd.toFixed(2)}/unit`} />
              <Fact label="Scrap Cost" value={`$${machine.scrap_cost_per_unit_usd.toFixed(2)}/unit`} />
            </dl>
          </section>

          {/* Current Jobs */}
          {(runningJobs.length > 0 || queuedJobs.length > 0 || pausedJobs.length > 0) && (
            <section>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Jobs on This Machine</h4>
              <ul className="mt-1.5 space-y-1">
                {runningJobs.map((job) => (
                  <li key={job.job_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400">{job.job_id}</span>{' '}
                    {job.part_no} · {job.produced_qty}/{job.target_qty} ·
                    <span className="text-blue-700">running</span>
                    {job.scrap_qty > 0 && <span className="text-amber-700"> · scrap {job.scrap_qty}</span>}
                  </li>
                ))}
                {queuedJobs.map((job) => (
                  <li key={job.job_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400">{job.job_id}</span>{' '}
                    {job.part_no} · {job.produced_qty}/{job.target_qty} ·
                    <span className="text-slate-500">queued</span>
                  </li>
                ))}
                {pausedJobs.map((job) => (
                  <li key={job.job_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400">{job.job_id}</span>{' '}
                    {job.part_no} · {job.produced_qty}/{job.target_qty} ·
                    <span className="text-amber-700">paused</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {activeTab === 'live' && context && (
        <div className="space-y-4">
          {points.length > 2 && (
            <section>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Trend ({context.telemetry[0]?.ts.slice(0, 16)} → {context.telemetry.at(-1)?.ts.slice(11, 16)} sim)
              </h4>
              <TrendChart
                title="Vibration"
                unit="mm/s"
                color="#d97706"
                tickEvery={tickEvery}
                data={points.map((p) => ({ ts: p.ts, value: p.vibration }))}
              />
              <TrendChart
                title="Bearing Temperature"
                unit="°C"
                color="#dc2626"
                tickEvery={tickEvery}
                data={points.map((p) => ({ ts: p.ts, value: p.temp }))}
              />
              {points[0].rpm != null && (
                <TrendChart
                  title="Spindle RPM"
                  unit="rpm"
                  color="#2563eb"
                  tickEvery={tickEvery}
                  data={points.map((p) => ({ ts: p.ts, value: p.rpm ?? 0 }))}
                />
              )}
              {points[0].current != null && (
                <TrendChart
                  title="Motor Current"
                  unit="A"
                  color="#7c3aed"
                  tickEvery={tickEvery}
                  data={points.map((p) => ({ ts: p.ts, value: p.current ?? 0 }))}
                />
              )}
            </section>
          )}
          {points.length <= 2 && (
            <p className="text-sm text-slate-500">Not enough telemetry data for trend charts.</p>
          )}
        </div>
      )}

      {activeTab === 'maintenance' && context && (
        <div className="space-y-4">
          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Maintenance History</h4>
            {context.maintenance.length === 0 ? (
              <p className="mt-1.5 text-xs text-slate-400">No maintenance events recorded.</p>
            ) : (
              <ul className="mt-1.5 space-y-1">
                {context.maintenance.map((record) => (
                  <li key={record.event_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400">{record.event_date}</span> · {record.issue}
                    {record.part_id && <span className="text-slate-500"> · {record.part_id}</span>}
                    {record.cost_usd != null && <span className="text-slate-500"> · ${record.cost_usd.toFixed(0)}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Work Orders</h4>
            {openWorkOrders.length === 0 ? (
              <p className="mt-1.5 text-xs text-slate-400">No open work orders.</p>
            ) : (
              <ul className="mt-1.5 space-y-1">
                {openWorkOrders.map((wo) => (
                  <li key={wo.work_order_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400">{wo.work_order_id}</span> · {wo.issue}
                    <span className="text-slate-500"> · {wo.priority.toLowerCase()} · {wo.status.toLowerCase()}</span>
                    {wo.source === 'AGENT' && <span className="ml-1.5 text-[10px] bg-amber-100 text-amber-700 px-1 rounded">AGENT</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {activeTab === 'production' && context && (
        <div className="space-y-4">
          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">All Production Jobs</h4>
            {context.production.length === 0 ? (
              <p className="mt-1.5 text-xs text-slate-400">No production jobs recorded.</p>
            ) : (
              <ul className="mt-1.5 space-y-1">
                {context.production.map((job) => (
                  <li key={job.job_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                    <span className="font-mono text-[10px] text-slate-400">{job.job_id}</span>{' '}
                    {job.part_no} · {job.produced_qty}/{job.target_qty} ·{' '}
                    <span className={job.status === 'RUNNING' ? 'text-blue-700' : job.status === 'PAUSED' ? 'text-amber-700' : 'text-slate-500'}>
                      {job.status.toLowerCase()}
                    </span>
                    {job.scrap_qty > 0 && <span className="text-amber-700"> · scrap {job.scrap_qty}</span>}
                    {job.due_at && <span className="text-slate-500"> · due {job.due_at}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {activeTab === 'agent' && context && (
        <div className="space-y-4">
          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Agent Activity Involving This Machine</h4>
            <p className="mt-1.5 text-xs text-slate-400">
              Agent runs and decisions involving {machine.machine_id} will appear here after autonomous runs.
            </p>
          </section>
        </div>
      )}
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[9px] uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="font-mono text-[11px] text-slate-700">{value}</dd>
    </div>
  )
}

function TrendChart({
  title,
  unit,
  color,
  data,
  tickEvery,
}: {
  title: string
  unit: string
  color: string
  data: { ts: string; value: number }[]
  tickEvery: number
}) {
  return (
    <div className="mt-1.5">
      <p className="text-[10px] font-medium text-slate-500">
        {title} <span className="text-slate-400">({unit})</span>
      </p>
      <div className="mt-0.5 h-24">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -26 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="ts" stroke="#94a3b8" tick={{ fontSize: 9 }} interval={tickEvery - 1} />
            <YAxis stroke="#94a3b8" tick={{ fontSize: 9 }} domain={['auto', 'auto']} width={44} />
            <Tooltip
              contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: '#64748b', fontSize: 10 }}
            />
            <Line type="monotone" dataKey="value" name={`${title} (${unit})`} stroke={color} dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}