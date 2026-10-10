import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { fetchFactorySnapshot, fetchMachines, type FactorySnapshot, type TwinMachine } from '../lib/factory'
import { STATE_COLORS, STATE_LABELS, STATE_ORDER, type MachineState } from '../lib/twin'

const SHOWCASE_MACHINE = 'CNC-03'
const ATTENTION_STATES: MachineState[] = ['CRITICAL', 'WARNING']

export default function CommandCenter() {
  const [snapshot, setSnapshot] = useState<FactorySnapshot | null>(null)
  const [machines, setMachines] = useState<TwinMachine[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchFactorySnapshot(), fetchMachines()])
      .then(([snap, list]) => {
        if (cancelled) return
        setSnapshot(snap)
        setMachines(list)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load factory')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">
        Factory API unreachable — {error}
      </div>
    )
  }
  if (!snapshot) {
    return <div className="text-sm text-slate-500">Loading factory…</div>
  }

  const cnc03 = machines.find((m) => m.machine_id === SHOWCASE_MACHINE) ?? null
  const attention = machines
    .filter((m) => ATTENTION_STATES.includes(m.state as MachineState))
    .sort((a, b) => ATTENTION_STATES.indexOf(a.state as MachineState) - ATTENTION_STATES.indexOf(b.state as MachineState))

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Command Center</h1>
          <p className="text-xs text-slate-500">Live FactoryWorld snapshot (deterministic simulation)</p>
        </div>
        <Link
          to="/twin"
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
        >
          Open the twin →
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card label="Machines" value={String(snapshot.machine_count)} />
        <Card label="Open incidents" value={String(snapshot.open_incidents.length)} />
        <Card label="Simulation time" value={snapshot.clock} mono />
        <Card
          label={`${SHOWCASE_MACHINE} state`}
          value={cnc03 ? STATE_LABELS[cnc03.state as MachineState] : '—'}
          accent={cnc03 ? STATE_COLORS[cnc03.state as MachineState] : undefined}
        />
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Machine health distribution</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {STATE_ORDER.map((state) => {
            const count = snapshot.state_distribution[state] ?? 0
            return (
              <span
                key={state}
                className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: STATE_COLORS[state] }}
                />
                {STATE_LABELS[state]}
                <span className="font-mono font-semibold">{count}</span>
              </span>
            )
          })}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Needs attention</h2>
        {attention.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">
            No machine is in WARNING or CRITICAL state right now.
          </p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-2">
            {attention.map((machine) => (
              <li
                key={machine.machine_id}
                className="flex items-center gap-2 rounded-md border border-slate-200 px-2.5 py-1.5 text-xs"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: STATE_COLORS[machine.state as MachineState] }}
                />
                <span className="font-mono font-medium text-slate-700">{machine.machine_id}</span>
                <span className="text-slate-500">{machine.name}</span>
                <span className="text-slate-400">{machine.line.replace('_LINE', ' line')}</span>
                <span className="font-mono text-slate-400">health {machine.health_score ?? '—'}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {snapshot.open_incidents.length > 0 && (
        <section className="rounded-xl border border-red-200 bg-red-50 p-5">
          <h2 className="text-sm font-semibold text-red-700">Active incidents</h2>
          <ul className="mt-2 space-y-2">
            {snapshot.open_incidents.map((incident) => (
              <li key={incident.incident_id} className="text-xs text-red-800">
                <span className="font-mono text-[10px] text-red-500">{incident.incident_id}</span>{' '}
                {incident.machine_id} · {incident.summary}{' '}
                <span className="text-red-600">({incident.opened_at})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-xl border border-blue-200 bg-blue-50 p-5">
        <h2 className="text-sm font-semibold text-blue-800">Factory Digital Twin</h2>
        <p className="mt-1 text-xs text-blue-700">
          Open the visual twin to watch the floor, select machines, and advance the scenario.
        </p>
        <Link
          to="/twin"
          className="mt-3 inline-block rounded-md bg-blue-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
        >
          Open Digital Twin →
        </Link>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Coming later (deterministic scope)</h2>
        <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400">
          {['Machines Explorer', 'Predictive Maintenance', 'Agent Activity', 'Work Orders',
            'Spare Parts', 'OEE Analytics', 'Maintenance Planner'].map((page) => (
            <li key={page} className="flex justify-between border-b border-dashed border-slate-100 pb-1">
              {page} <span className="text-[10px] uppercase">Later milestone</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function Card({ label, value, mono, accent }: { label: string; value: string; mono?: boolean; accent?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${mono ? 'font-mono' : ''} ${accent ? '' : 'text-slate-800'}`}
         style={accent ? { color: accent } : undefined}>
        {value}
      </p>
    </div>
  )
}
