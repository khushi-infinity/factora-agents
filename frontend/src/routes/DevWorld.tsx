import { useEffect, useState } from 'react'

import { fetchFactorySnapshot, fetchMachines, type FactorySnapshot, type TwinMachine } from '../lib/factory'
import { fetchAgentStatus, type AgentStatus } from '../lib/agents'
import { STATE_COLORS, STATE_LABELS, STATE_ORDER } from '../lib/twin'

export default function DevWorld() {
  const [snapshot, setSnapshot] = useState<FactorySnapshot | null>(null)
  const [machines, setMachines] = useState<TwinMachine[]>([])
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchFactorySnapshot(), fetchMachines(), fetchAgentStatus()])
      .then(([snap, list, agentInfo]) => {
        if (!cancelled) {
          setSnapshot(snap)
          setMachines(list)
          setAgentStatus(agentInfo)
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load factory')
      })
    return () => { cancelled = true }
  }, [])

  if (error) {
    return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>
  }
  if (!snapshot) {
    return <div className="text-sm text-slate-500">Loading factory…</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Factory World (Dev)</h1>
          <p className="text-xs text-slate-500">Direct FactoryWorld health + snapshot panels — debug/admin page</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card label="Machines" value={String(snapshot.machine_count)} />
        <Card label="Open incidents" value={String(snapshot.open_incidents.length)} />
        <Card label="Simulation time" value={snapshot.clock} mono />
        <Card label="Agent mode" value={agentStatus?.mode ?? '—'} />
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Machine health distribution</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {STATE_ORDER.map((state) => {
            const count = snapshot.state_distribution[state] ?? 0
            return (
              <span key={state} className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: STATE_COLORS[state] }} />
                {STATE_LABELS[state]}
                <span className="font-mono font-semibold">{count}</span>
              </span>
            )
          })}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Agent System Status</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <DetailCard label="Model Provider" value={agentStatus?.model_provider ?? '—'} />
          <DetailCard label="Model Name" value={agentStatus?.model_name ?? '—'} />
          <DetailCard label="Mode" value={agentStatus?.mode ?? '—'} />
          <DetailCard label="Observability" value={agentStatus?.observability ?? '—'} />
          <DetailCard label="Failure Injection" value={agentStatus?.failure_injection_available ? 'Available' : 'Disabled'} />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">All Machines (Raw Data)</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">ID</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">Name</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">Type</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">Line</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">State</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">Health</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">X</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">Y</th>
                <th className="px-2 py-1 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-400">Z</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {machines.map((machine) => (
                <tr key={machine.machine_id} className="hover:bg-slate-50">
                  <td className="px-2 py-1 font-mono text-slate-600">{machine.machine_id}</td>
                  <td className="px-2 py-1 text-slate-600">{machine.name}</td>
                  <td className="px-2 py-1 text-slate-600">{machine.machine_type}</td>
                  <td className="px-2 py-1 text-slate-600">{machine.line}</td>
                  <td className="px-2 py-1">
                    <span className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium text-white"
                          style={{ backgroundColor: STATE_COLORS[machine.state as keyof typeof STATE_COLORS] }}>
                      {STATE_LABELS[machine.state as keyof typeof STATE_LABELS]}
                    </span>
                  </td>
                  <td className="px-2 py-1 font-mono text-slate-600">{machine.health_score ?? '—'}</td>
                  <td className="px-2 py-1 font-mono text-slate-500">{machine.x_m.toFixed(1)}</td>
                  <td className="px-2 py-1 font-mono text-slate-500">{machine.y_m.toFixed(1)}</td>
                  <td className="px-2 py-1 font-mono text-slate-500">{machine.z_m.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Card({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${mono ? 'font-mono' : ''} text-slate-800`}>{value}</p>
    </div>
  )
}

function DetailCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm font-mono text-slate-700">{value}</p>
    </div>
  )
}