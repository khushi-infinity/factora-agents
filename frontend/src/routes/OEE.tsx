import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
  Cell,
} from 'recharts'

import { fetchOEEFactory, fetchOEELines, fetchOEEMachines, type OEEFactory, type OEELine, type OEEMachine } from '../lib/factory'

export default function OEE() {
  const [factoryOEE, setFactoryOEE] = useState<OEEFactory | null>(null)
  const [lines, setLines] = useState<OEELine[]>([])
  const [machines, setMachines] = useState<OEEMachine[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'factory' | 'lines' | 'machines' | 'loss'>('factory')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([fetchOEEFactory(), fetchOEELines(), fetchOEEMachines()])
      .then(([factory, linesData, machinesData]) => {
        if (!cancelled) {
          setFactoryOEE(factory)
          setLines(linesData)
          setMachines(machinesData)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load OEE data')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="text-sm text-slate-500">Loading OEE analytics…</div>
  if (error) return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>
  if (!factoryOEE) return <div className="text-sm text-slate-500">No OEE data available</div>

  const COLORS = ['#16a34a', '#d97706', '#dc2626', '#546e8f', '#9ca3af']

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">OEE & Production Analytics</h1>
          <p className="text-xs text-slate-500">Overall Equipment Effectiveness — synthetic demo economics</p>
        </div>
        <div className="flex gap-2">
          {(['factory', 'lines', 'machines', 'loss'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
                view === v
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

      {/* KPI Cards */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KPICard label="Factory OEE" value={`${(factoryOEE.factory_oee * 100).toFixed(1)}%`} accent="#16a34a" />
        <KPICard label="Availability" value={`${((factoryOEE.lines.reduce((a, l) => a + l.availability, 0) / factoryOEE.lines.length) * 100).toFixed(1)}%`} />
        <KPICard label="Performance" value={`${((factoryOEE.lines.reduce((a, l) => a + l.performance, 0) / factoryOEE.lines.length) * 100).toFixed(1)}%`} />
        <KPICard label="Quality" value={`${((factoryOEE.lines.reduce((a, l) => a + l.quality, 0) / factoryOEE.lines.length) * 100).toFixed(1)}%`} />
      </section>

      {/* View Content */}
      {view === 'factory' && factoryOEE && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
          <h2 className="text-sm font-semibold text-slate-800">Factory OEE Breakdown</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <OEEComponentChart title="Availability" value={(factoryOEE.lines.reduce((a, l) => a + l.availability, 0) / factoryOEE.lines.length) * 100} color="#3b82f6" />
            <OEEComponentChart title="Performance" value={(factoryOEE.lines.reduce((a, l) => a + l.performance, 0) / factoryOEE.lines.length) * 100} color="#8b5cf6" />
            <OEEComponentChart title="Quality" value={(factoryOEE.lines.reduce((a, l) => a + l.quality, 0) / factoryOEE.lines.length) * 100} color="#ec4899" />
          </div>
          <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Loss Breakdown</p>
            <ul className="mt-2 grid gap-2 md:grid-cols-4 text-xs">
              {Object.entries(factoryOEE.loss_breakdown).map(([key, value]) => (
                <li key={key} className="flex justify-between text-slate-600">
                  <span className="capitalize">{key.replace('_', ' ')}</span>
                  <span className="font-mono font-semibold text-slate-800">{(value * 100).toFixed(1)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {view === 'lines' && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800 mb-3">OEE by Line</h2>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {lines.map((line, i) => (
              <LineOEECard key={line.line} line={line} color={COLORS[i % COLORS.length]} />
            ))}
          </div>
        </section>
      )}

      {view === 'machines' && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <h2 className="text-sm font-semibold text-slate-800 p-4 mb-0">OEE by Machine</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Machine</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Line</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">OEE</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Availability</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Performance</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Quality</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Target</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Actual</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Good</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Scrap</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Unplanned Downtime</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {machines.map((m) => (
                  <tr key={m.machine_id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 font-mono text-xs text-blue-600">{m.machine_id}</td>
                    <td className="px-3 py-2 text-slate-600">{m.line.replace('_LINE', ' Line')}</td>
                    <td className="px-3 py-2 font-mono text-slate-700">{(m.oee * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2 font-mono text-slate-700">{(m.availability * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2 font-mono text-slate-700">{(m.performance * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2 font-mono text-slate-700">{(m.quality * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{m.target_units}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{m.actual_units}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{m.good_units}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{m.scrap_units}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{m.unplanned_downtime_hours.toFixed(1)}h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {view === 'loss' && factoryOEE && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
          <h2 className="text-sm font-semibold text-slate-800">Production Loss Breakdown</h2>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {Object.entries(factoryOEE.loss_breakdown).map(([key, value]) => (
              <LossCard key={key} label={key.replace('_', ' ')} value={value * 100} />
            ))}
          </div>
          <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Total Loss</p>
            <p className="mt-1 text-xl font-bold text-slate-800">{(Object.values(factoryOEE.loss_breakdown).reduce((a, b) => a + b, 0) * 100).toFixed(1)}%</p>
          </div>
        </section>
      )}
    </div>
  )
}

function KPICard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800" style={accent ? { color: accent } : undefined}>{value}</p>
    </div>
  )
}

function OEEComponentChart({ title, value, color }: { title: string; value: number; color: string }) {
  const pct = Math.min(100, Math.max(0, value))
  return (
    <div className="rounded-lg border border-slate-200 p-4 bg-white">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      <div className="mt-2 h-24 relative">
        <svg width="100%" height="100%" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="40"
            stroke="#e2e8f0"
            strokeWidth="8"
            fill="none"
          />
          <circle
            cx="50"
            cy="50"
            r="40"
            stroke={color}
            strokeWidth="8"
            fill="none"
            strokeDasharray={`${pct / 100 * 251.2} 251.2`}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            style={{ transition: 'stroke-dasharray 0.5s' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-slate-800">{pct.toFixed(1)}%</span>
        </div>
      </div>
      <p className="mt-2 text-[10px] text-slate-500">Target: 85%</p>
    </div>
  )
}

function LineOEECard({ line, color }: { line: { line: string; oee: number; availability: number; performance: number; quality: number; machines: number }; color: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4 bg-white">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-800">{line.line.replace('_LINE', ' Line')}</h3>
        <span className="text-xs text-slate-500">{line.machines} machines</span>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center">
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-2xl font-bold text-slate-800" style={{ color }}>{(line.oee * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-slate-400">OEE</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-lg font-bold text-slate-700">{(line.availability * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-slate-400">Avail</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-lg font-bold text-slate-700">{(line.performance * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-slate-400">Perf</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-lg font-bold text-slate-700">{(line.quality * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-slate-400">Qual</p>
        </div>
      </div>
    </div>
  )
}

function LossCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4 bg-white text-center">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 capitalize">{label}</p>
      <p className="mt-1 text-3xl font-bold text-red-600">{value.toFixed(1)}%</p>
    </div>
  )
}