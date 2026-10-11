import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { fetchPredictiveMaintenance, type PredictiveRisk } from '../lib/factory'
import { STATE_COLORS, STATE_LABELS } from '../lib/twin'

export default function PredictiveMaintenance() {
  const [risks, setRisks] = useState<PredictiveRisk[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterCategory, setFilterCategory] = useState<'all' | 'HIGH' | 'MEDIUM' | 'LOW'>('all')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPredictiveMaintenance()
      .then((data) => {
        if (!cancelled) {
          setRisks(data)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load risk data')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  const filtered = risks.filter((r) => filterCategory === 'all' || r.risk_category === filterCategory)

  if (loading) {
    return <div className="text-sm text-slate-500">Loading predictive risk data…</div>
  }
  if (error) {
    return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Predictive Maintenance</h1>
          <p className="text-xs text-slate-500">Condition-based risk scoring — deterministic, no ML claims</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">Filter:</span>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value as 'all' | 'HIGH' | 'MEDIUM' | 'LOW')}
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 bg-white"
          >
            <option value="all">All Risks</option>
            <option value="HIGH">High Risk</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="LOW">Low Risk</option>
          </select>
        </div>
      </div>

      {error && <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Machine</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Type</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Line</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">State</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Risk Score</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Trend</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Likely Issue</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Urgency</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Spare Part</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Open WOs</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-3 py-8 text-center text-slate-400">
                    No machines match the current filter.
                  </td>
                </tr>
              ) : (
                filtered.map((risk) => (
                  <tr key={risk.machine_id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <Link to={`/machines/${risk.machine_id}`} className="font-mono font-medium text-blue-600 hover:underline">
                        {risk.machine_id}
                      </Link>
                      <p className="text-[10px] text-slate-500">{risk.name}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{risk.machine_type}</td>
                    <td className="px-3 py-2 text-slate-600">{risk.line.replace('_LINE', ' Line')}</td>
                    <td className="px-3 py-2">
                      <span
                        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                        style={{ backgroundColor: STATE_COLORS[risk.risk_category === 'HIGH' ? 'CRITICAL' : risk.risk_category === 'MEDIUM' ? 'WARNING' : 'HEALTHY'] }}
                      >
                        {STATE_LABELS[risk.risk_category === 'HIGH' ? 'CRITICAL' : risk.risk_category === 'MEDIUM' ? 'WARNING' : 'HEALTHY']}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="h-2 w-24 rounded bg-slate-200 relative overflow-hidden">
                        <div
                          className="h-full rounded"
                          style={{
                            width: `${risk.risk_score * 100}%`,
                            backgroundColor: risk.risk_score >= 0.7 ? '#dc2626' : risk.risk_score >= 0.4 ? '#d97706' : '#16a34a',
                          }}
                        />
                      </div>
                      <p className="mt-0.5 font-mono text-[10px] text-slate-600">{(risk.risk_score * 100).toFixed(0)}%</p>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                        risk.trend === 'degrading' ? 'bg-red-100 text-red-700' :
                        risk.trend === 'improving' ? 'bg-green-100 text-green-700' :
                        'bg-slate-100 text-slate-700'
                      }`}>
                        {risk.trend}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{risk.likely_issue ?? '—'}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                        risk.urgency === 'high' ? 'bg-red-100 text-red-700' :
                        risk.urgency === 'medium' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {risk.urgency}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-600">{risk.spare_part_id ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{risk.open_work_orders}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                        risk.risk_category === 'HIGH' ? 'bg-red-100 text-red-700' :
                        risk.risk_category === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {risk.risk_category}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Evidence Detail for High Risk Machines */}
      {filtered.filter(r => r.risk_category === 'HIGH').length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800">High Risk Evidence</h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {filtered.filter(r => r.risk_category === 'HIGH').map((risk) => (
              <div key={risk.machine_id} className="rounded-lg border border-red-200 bg-red-50 p-3">
                <p className="font-mono font-medium text-red-700">{risk.machine_id} · {risk.name}</p>
                <p className="text-[11px] text-red-600 mt-0.5">Score: {(risk.risk_score * 100).toFixed(0)}% · {risk.trend}</p>
                <ul className="mt-1.5 space-y-0.5 text-[10px] text-red-800">
                  {risk.evidence.map((e, i) => (
                    <li key={i} className="flex gap-1">
                      <span className="text-red-500">•</span> {e}
                    </li>
                  ))}
                </ul>
                {risk.likely_issue && (
                  <p className="mt-1.5 text-[10px] font-medium text-red-700">
                    Likely: {risk.likely_issue.replace('_', ' ')}
                  </p>
                )}
                <p className="mt-1.5 text-[10px] text-red-600">
                  Spare: {risk.spare_part_id ?? 'N/A'} · WOs: {risk.open_work_orders}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}