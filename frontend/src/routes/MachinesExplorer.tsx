import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { fetchMachines, type TwinMachine } from '../lib/factory'
import { STATE_COLORS, STATE_LABELS, STATE_ORDER, type MachineState } from '../lib/twin'

export default function MachinesExplorer() {
  const [machines, setMachines] = useState<TwinMachine[]>([])
  const [filterLine, setFilterLine] = useState<string>('')
  const [filterState, setFilterState] = useState<MachineState | 'all'>('all')
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<'health' | 'state' | 'id'>('health')

  useEffect(() => {
    let cancelled = false
    fetchMachines()
      .then((list) => {
        if (!cancelled) setMachines(list)
      })
      .catch(console.error)
    return () => {
      cancelled = true
    }
  }, [])

  const lines = [...new Set(machines.map((m) => m.line))].sort()

  const filtered = machines
    .filter((m) => filterLine === '' || m.line === filterLine)
    .filter((m) => filterState === 'all' || m.state === filterState)
    .filter((m) =>
      search === '' ||
      m.machine_id.toLowerCase().includes(search.toLowerCase()) ||
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.machine_type.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      if (sortBy === 'health') return (b.health_score ?? 0) - (a.health_score ?? 0)
      if (sortBy === 'state') return STATE_ORDER.indexOf(a.state as MachineState) - STATE_ORDER.indexOf(b.state as MachineState)
      return a.machine_id.localeCompare(b.machine_id)
    })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Machines Explorer</h1>
          <p className="text-xs text-slate-500">All machines in FactoryWorld with live state and telemetry</p>
        </div>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Search</label>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Machine ID, name, type…"
              className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <select
            value={filterLine}
            onChange={(e) => setFilterLine(e.target.value)}
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 bg-white"
          >
            <option value="">All Lines</option>
            {lines.map((line) => (
              <option key={line} value={line}>
                {line.replace('_LINE', ' Line')}
              </option>
            ))}
          </select>
          <select
            value={filterState}
            onChange={(e) => setFilterState(e.target.value as MachineState | 'all')}
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 bg-white"
          >
            <option value="all">All States</option>
            {STATE_ORDER.map((state) => (
              <option key={state} value={state}>
                {STATE_LABELS[state]}
              </option>
            ))}
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'health' | 'state' | 'id')}
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 bg-white"
          >
            <option value="health">Sort: Health ↓</option>
            <option value="state">Sort: State</option>
            <option value="id">Sort: ID</option>
          </select>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Machine</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Type</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Line</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">State</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Health</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Current Job</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Output/h</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Vibration</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Temp</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Incident</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-slate-400">
                    No machines match the current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((machine) => (
                  <tr key={machine.machine_id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <Link
                        to={`/machines/${machine.machine_id}`}
                        className="font-mono font-medium text-blue-600 hover:underline"
                      >
                        {machine.machine_id}
                      </Link>
                      <p className="text-[10px] text-slate-500">{machine.name}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{machine.machine_type}</td>
                    <td className="px-3 py-2 text-slate-600">{machine.line.replace('_LINE', ' Line')}</td>
                    <td className="px-3 py-2">
                      <span
                        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                        style={{ backgroundColor: STATE_COLORS[machine.state as keyof typeof STATE_COLORS] }}
                      >
                        {STATE_LABELS[machine.state as keyof typeof STATE_LABELS]}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="font-mono text-slate-700">{machine.health_score ?? '—'}</span>
                    </td>
                    <td className="px-3 py-2 text-slate-500">—</td>
                    <td className="px-3 py-2 font-mono text-slate-600">{machine.output_per_hour?.toFixed(1) ?? '—'} u/h</td>
                    <td className="px-3 py-2 text-slate-500">—</td>
                    <td className="px-3 py-2 text-slate-500">—</td>
                    <td className="px-3 py-2 text-slate-500">—</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}