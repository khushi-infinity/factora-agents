import { useEffect, useState } from 'react'

import { fetchSpareParts, type SparePart } from '../lib/factory'

export default function SpareParts() {
  const [parts, setParts] = useState<SparePart[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPart, setSelectedPart] = useState<SparePart | null>(null)
  const [filterStatus, setFilterStatus] = useState<'all' | 'IN_STOCK' | 'LOW_STOCK' | 'CRITICAL_STOCK'>('all')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchSpareParts()
      .then((data) => {
        if (!cancelled) {
          setParts(data)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load spare parts')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  const filtered = parts.filter(p => filterStatus === 'all' || p.stock_status === filterStatus)

  if (loading) return <div className="text-sm text-slate-500">Loading spare parts inventory…</div>
  if (error) return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Spare Parts Inventory</h1>
          <p className="text-xs text-slate-500">Parts inventory with stock status and compatibility</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">Filter:</span>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 bg-white"
          >
            <option value="all">All</option>
            <option value="IN_STOCK">In Stock</option>
            <option value="LOW_STOCK">Low Stock</option>
            <option value="CRITICAL_STOCK">Critical</option>
          </select>
        </div>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Part ID</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Name</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Category</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Compatible Types</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Stock</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Reorder Point</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Unit Cost</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Lead Time</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Supplier</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-slate-400">No spare parts found.</td>
                </tr>
              ) : (
                filtered.map((part) => (
                  <tr key={part.part_id} className="hover:bg-slate-50 cursor-pointer" onClick={() => setSelectedPart(part)}>
                    <td className="px-3 py-2 font-mono text-xs text-blue-600 hover:underline">{part.part_id}</td>
                    <td className="px-3 py-2 text-slate-600">{part.name}</td>
                    <td className="px-3 py-2 text-slate-600">{part.category}</td>
                    <td className="px-3 py-2 text-slate-500 max-w-xs truncate">{part.compatible_types}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{part.stock_qty}</td>
                    <td className="px-3 py-2 font-mono text-slate-500">{part.reorder_point}</td>
                    <td className="px-3 py-2 font-mono text-slate-600">${part.unit_cost_usd.toLocaleString()}</td>
                    <td className="px-3 py-2 font-mono text-slate-500">{part.lead_time_days} days</td>
                    <td className="px-3 py-2 text-slate-500">{part.supplier ?? '—'}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-medium ${
                        part.stock_status === 'CRITICAL_STOCK' ? 'bg-red-100 text-red-700' :
                        part.stock_status === 'LOW_STOCK' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {part.stock_status.replace('_', ' ')}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {selectedPart && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">{selectedPart.part_id} — {selectedPart.name}</h2>
              <p className="text-xs text-slate-500">{selectedPart.category} · {selectedPart.compatible_types}</p>
            </div>
            <button onClick={() => setSelectedPart(null)} className="text-sm text-slate-500 hover:text-slate-700">Close</button>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Stock Status</p>
              <p className="mt-1 text-2xl font-bold text-slate-800">{selectedPart.stock_qty}</p>
              <p className="text-[10px] text-slate-500">Reorder at {selectedPart.reorder_point}</p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Unit Cost</p>
              <p className="mt-1 text-2xl font-bold text-slate-800">${selectedPart.unit_cost_usd.toLocaleString()}</p>
              <p className="text-[10px] text-slate-500">Lead: {selectedPart.lead_time_days} days</p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Status</p>
              <p className="mt-1 text-lg font-bold text-slate-800 capitalize">{selectedPart.stock_status.replace('_', ' ')}</p>
              <p className="text-[10px] text-slate-500">Supplier: {selectedPart.supplier ?? '—'}</p>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}