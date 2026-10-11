import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { fetchPlanner, type PlannerItem } from '../lib/factory'

export default function Planner() {
  const [items, setItems] = useState<PlannerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPlanner()
      .then((data) => {
        if (!cancelled) {
          setItems(data)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load planner')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  const priorityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
  const sortedItems = [...items].sort((a, b) => priorityOrder[a.priority as keyof typeof priorityOrder] - priorityOrder[b.priority as keyof typeof priorityOrder])

  if (loading) return <div className="text-sm text-slate-500">Loading maintenance planner…</div>
  if (error) return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Maintenance Planner</h1>
          <p className="text-xs text-slate-500">Upcoming maintenance with parts, costs, and production impact</p>
        </div>
      </div>

      {error && <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

      {/* Priority Queue */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="p-4 border-b border-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">Priority Queue</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Priority</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Work Order</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Machine</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Issue</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Parts</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Parts Avail</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Downtime</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Cost</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Prod Impact</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sortedItems.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-slate-400">No maintenance items scheduled.</td>
                </tr>
              ) : (
                sortedItems.map((item) => (
                  <tr key={item.work_order_id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                        item.priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                        item.priority === 'HIGH' ? 'bg-amber-100 text-amber-700' :
                        item.priority === 'MEDIUM' ? 'bg-blue-100 text-blue-700' :
                        'bg-slate-100 text-slate-700'
                      }`}>
                        {item.priority}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <Link to={`/work-orders/${item.work_order_id}`} className="font-mono text-xs text-blue-600 hover:underline">
                        {item.work_order_id}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      <Link to={`/machines/${item.machine_id}`} className="font-mono text-xs text-blue-600 hover:underline">
                        {item.machine_id}
                      </Link>
                      <p className="text-[10px] text-slate-500">{item.machine_name}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-600 max-w-xs truncate">{item.issue}</td>
                    <td className="px-3 py-2 text-slate-500">
                      {item.required_parts.length === 0 ? '—' : (
                        <span className="text-xs">{item.required_parts.join(', ')}</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                        item.parts_available ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {item.parts_available ? 'Available' : 'Missing'}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-600">{item.estimated_downtime_hours}h</td>
                    <td className="px-3 py-2 font-mono text-slate-600">${item.estimated_cost_usd?.toLocaleString() ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">${item.production_impact_usd.toLocaleString()}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                        item.source === 'AGENT' ? 'bg-amber-100 text-amber-700' :
                        'bg-blue-100 text-blue-700'
                      }`}>
                        {item.source}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Upcoming Maintenance Timeline */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="p-4 border-b border-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">Upcoming Maintenance Schedule</h2>
        </div>
        <div className="p-4 space-y-3">
          {sortedItems.length === 0 ? (
            <p className="text-sm text-slate-500">No upcoming maintenance.</p>
          ) : (
            <ul className="space-y-3">
              {sortedItems.map((item) => (
                <li key={item.work_order_id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Link to={`/work-orders/${item.work_order_id}`} className="font-mono text-sm text-blue-600 hover:underline">
                          {item.work_order_id}
                        </Link>
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                          item.priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                          item.priority === 'HIGH' ? 'bg-amber-100 text-amber-700' :
                          item.priority === 'MEDIUM' ? 'bg-blue-100 text-blue-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {item.priority}
                        </span>
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                          item.source === 'AGENT' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                        }`}>
                          {item.source}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-slate-700">{item.issue}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        <Link to={`/machines/${item.machine_id}`} className="font-mono text-blue-600 hover:underline">{item.machine_id}</Link>{' '}
                        · {item.machine_name} · {item.machine_type} · {item.line.replace('_LINE', ' Line')}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 shrink-0">
                      <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-slate-400" />
                        {item.estimated_downtime_hours}h downtime
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-amber-400" />
                        ${item.estimated_cost_usd?.toLocaleString() ?? '—'} cost
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
                        ${item.production_impact_usd.toLocaleString()} prod impact
                      </span>
                      <span className={`flex items-center gap-1 ${
                        item.parts_available ? 'text-green-700' : 'text-red-700'
                      }`}>
                        <span className={`inline-block h-2 w-2 rounded-full ${item.parts_available ? 'bg-green-500' : 'bg-red-500'}`} />
                        Parts {item.parts_available ? 'Available' : 'Missing'}
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* Reports Section */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="p-4 border-b border-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">Reports & Exports</h2>
        </div>
        <div className="p-4 grid gap-3 md:grid-cols-3">
          <button className="rounded-lg border border-slate-200 p-4 text-left hover:bg-slate-50 transition">
            <p className="text-sm font-semibold text-slate-800">Incident Summary</p>
            <p className="mt-1 text-xs text-slate-500">All incidents in current simulation window</p>
          </button>
          <button className="rounded-lg border border-slate-200 p-4 text-left hover:bg-slate-50 transition">
            <p className="text-sm font-semibold text-slate-800">Maintenance Actions</p>
            <p className="mt-1 text-xs text-slate-500">Completed work orders and costs</p>
          </button>
          <button className="rounded-lg border border-slate-200 p-4 text-left hover:bg-slate-50 transition">
            <p className="text-sm font-semibold text-slate-800">Production Impact</p>
            <p className="mt-1 text-xs text-slate-500">OEE, reroutes, and economics</p>
          </button>
        </div>
      </section>
    </div>
  )
}