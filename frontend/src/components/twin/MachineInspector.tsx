import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { MachineContext } from '../../lib/factory'
import { STATE_LABELS, STATE_COLORS, lineLabel, type MachineState } from '../../lib/twin'

interface Props {
  context: MachineContext | null
  loading: boolean
  onClose: () => void
}

/** Vibration and temperature live on different scales, so each gets its own
 *  axis — one shared axis would flatten vibration to a flat line. */
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
            <YAxis
              stroke="#94a3b8"
              tick={{ fontSize: 9 }}
              domain={['auto', 'auto']}
              width={44}
            />
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

export default function MachineInspector({ context, loading, onClose }: Props) {
  if (loading) {
    return (
      <aside className="flex w-96 shrink-0 flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">Loading machine context…</p>
      </aside>
    )
  }
  if (!context) {
    return (
      <aside className="flex w-96 shrink-0 flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">Select a machine on the twin floor.</p>
      </aside>
    )
  }

  const { machine } = context
  const state = machine.state as MachineState
  const openIncidents = context.incidents.filter((incident) => incident.status === 'OPEN')
  const openWorkOrders = context.work_orders.filter((wo) => wo.status !== 'CLOSED')
  const points = context.telemetry.map((r) => ({
    ts: r.ts.slice(11, 16),
    vibration: r.vibration_mm_s,
    temp: r.bearing_temp_c,
  }))
  // Thin labels: show every ~6th tick so the X axis stays readable.
  const tickEvery = Math.max(1, Math.floor(points.length / 5))

  return (
    <aside className="flex w-96 shrink-0 flex-col gap-4 overflow-y-auto rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-800">{machine.machine_id}</h3>
          <p className="text-xs text-slate-500">
            {machine.name} · {machine.machine_type} · {lineLabel(machine.line)}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-200 px-2 py-0.5 text-xs text-slate-500 hover:border-slate-400 hover:text-slate-700"
        >
          Close
        </button>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
          style={{ backgroundColor: STATE_COLORS[state] }}
        >
          {STATE_LABELS[state]}
        </span>
        <span className="text-xs text-slate-600">
          Health <span className="font-mono font-semibold">{machine.health_score ?? '—'}</span>/100
        </span>
      </div>

      {openIncidents.length > 0 && (
        <div className="rounded-lg border-2 border-red-300 bg-red-50 p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-red-700">
            Critical incident · {openIncidents.length} open
          </p>
          {openIncidents.map((incident) => (
            <div key={incident.incident_id} className="mt-1.5 border-t border-red-200 pt-1.5 first:border-0 first:pt-0">
              <p className="font-mono text-[10px] text-red-500">{incident.incident_id} · opened {incident.opened_at}</p>
              <p className="text-xs text-red-800">{incident.summary}</p>
              {incident.recommended_action && (
                <p className="mt-1 text-[11px] text-red-700/80">
                  Recommended: {incident.recommended_action}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <section>
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Latest telemetry</h4>
        {machine.latest_telemetry ? (
          <dl className="mt-1.5 grid grid-cols-3 gap-x-3 gap-y-1.5 text-xs">
            <Fact label="Vibration" value={`${machine.latest_telemetry.vibration_mm_s.toFixed(2)} mm/s`} />
            <Fact label="Bearing temp" value={`${machine.latest_telemetry.bearing_temp_c.toFixed(1)} °C`} />
            <Fact label="Defect rate" value={`${(machine.latest_telemetry.defect_rate_pct ?? 0).toFixed(2)}%`} />
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
          <p className="mt-1.5 text-xs text-slate-400">No telemetry (offline machine).</p>
        )}
      </section>

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
            title="Bearing temperature"
            unit="°C"
            color="#dc2626"
            tickEvery={tickEvery}
            data={points.map((p) => ({ ts: p.ts, value: p.temp }))}
          />
        </section>
      )}

      <section>
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Economics <span className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-[9px] font-semibold text-amber-700">Synthetic demo economics</span>
        </h4>
        <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
          <Fact label="Output" value={`${machine.output_per_hour.toFixed(1)} units/h`} />
          <Fact label="Operating cost" value={`$${machine.cost_per_hour_usd.toFixed(2)}/h`} />
          <Fact label="Contribution" value={`$${machine.contribution_per_unit_usd.toFixed(2)}/unit`} />
          <Fact label="Scrap cost" value={`$${machine.scrap_cost_per_unit_usd.toFixed(2)}/unit`} />
        </dl>
      </section>

      {context.production.filter((j) => j.status === 'RUNNING' || j.status === 'QUEUED').length > 0 && (
        <section>
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Jobs on this machine</h4>
          <ul className="mt-1.5 space-y-1">
            {context.production
              .filter((job) => job.status === 'RUNNING' || job.status === 'QUEUED')
              .map((job) => (
                <li key={job.job_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                  <span className="font-mono text-[10px] text-slate-400">{job.job_id}</span>{' '}
                  {job.part_no} · {job.produced_qty}/{job.target_qty} ·{' '}
                  <span className={job.status === 'RUNNING' ? 'text-blue-700' : 'text-slate-500'}>
                    {job.status.toLowerCase()}
                  </span>
                  {job.scrap_qty > 0 && <span className="text-amber-700"> · scrap {job.scrap_qty}</span>}
                </li>
              ))}
          </ul>
        </section>
      )}

      <section>
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Maintenance history
        </h4>
        {context.maintenance.length === 0 ? (
          <p className="mt-1.5 text-xs text-slate-400">No maintenance events recorded.</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {context.maintenance.map((record) => (
              <li key={record.event_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                <span className="font-mono text-[10px] text-slate-400">{record.event_date}</span> · {record.issue}
                {record.part_id && (
                  <span className="text-slate-500"> · {record.part_id}</span>
                )}
                {record.cost_usd != null && (
                  <span className="text-slate-500"> · ${record.cost_usd.toFixed(0)}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Work orders
        </h4>
        {openWorkOrders.length === 0 ? (
          <p className="mt-1.5 text-xs text-slate-400">No open work orders.</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {openWorkOrders.map((wo) => (
              <li key={wo.work_order_id} className="rounded border border-slate-100 px-2 py-1 text-xs text-slate-600">
                <span className="font-mono text-[10px] text-slate-400">{wo.work_order_id}</span> · {wo.issue}
                <span className="text-slate-500"> · {wo.priority.toLowerCase()} · {wo.status.toLowerCase()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
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
