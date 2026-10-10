import { useCallback, useEffect, useState } from 'react'

import {
  advanceSimulation,
  fetchFactorySnapshot,
  resetSimulation,
  type FactorySnapshot,
} from '../lib/factory'

const STATE_CHIP: Record<string, string> = {
  HEALTHY: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700',
  WARNING: 'border-amber-500/40 bg-amber-500/10 text-amber-700',
  CRITICAL: 'border-red-500/40 bg-red-500/10 text-red-700',
  MAINTENANCE: 'border-slate-400/40 bg-slate-400/10 text-slate-600',
  OFFLINE: 'border-slate-300 bg-slate-100 text-slate-500',
}

const ADVANCE_OPTIONS = [10, 30, 60] as const

type ErrorState = { message: string } | null

export default function FactoryStatus() {
  const [snapshot, setSnapshot] = useState<FactorySnapshot | null>(null)
  const [error, setError] = useState<ErrorState>(null)
  const [busy, setBusy] = useState(false)
  const [lastAction, setLastAction] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setSnapshot(await fetchFactorySnapshot())
    } catch (e) {
      setError({ message: e instanceof Error ? e.message : 'Unknown error' })
    }
  }, [])

  useEffect(() => {
    // Initial snapshot fetch on mount; setStates happen after the fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  const run = useCallback(
    async (action: () => Promise<string>) => {
      setBusy(true)
      setError(null)
      try {
        setLastAction(await action())
        await load()
      } catch (e) {
        setError({ message: e instanceof Error ? e.message : 'Unknown error' })
      } finally {
        setBusy(false)
      }
    },
    [load],
  )

  const cnc03 = snapshot?.state_distribution // full distribution only; detail via /machines

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">FactoryWorld</h2>
          <p className="mt-0.5 font-mono text-[11px] text-slate-500">GET /api/factory</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void run(async () => {
              const r = await resetSimulation()
              return `reset → clock ${r.clock}`
            })}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:border-blue-500 disabled:opacity-50"
          >
            Reset Scenario
          </button>
          {ADVANCE_OPTIONS.map((minutes) => (
            <button
              key={minutes}
              type="button"
              disabled={busy}
              onClick={() => void run(async () => {
                const r = await advanceSimulation(minutes)
                return `advance ${minutes}m → ${r.cnc03_state}`
              })}
              className="rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 transition hover:border-blue-500 disabled:opacity-50"
            >
              +{minutes}m
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/5 p-3">
          <p className="text-sm font-medium text-red-700">API error</p>
          <p className="mt-1 font-mono text-[11px] text-red-600">{error.message}</p>
        </div>
      )}

      {snapshot && !error && (
        <div className="mt-4 space-y-3">
          <dl className="grid grid-cols-3 gap-x-4 gap-y-2 text-xs">
            <Fact label="Sim clock" value={snapshot.clock} />
            <Fact label="Machines" value={String(snapshot.machine_count)} />
            <Fact label="Open incidents" value={String(snapshot.open_incidents.length)} />
          </dl>

          <div className="flex flex-wrap gap-2">
            {Object.entries(snapshot.state_distribution).map(([state, count]) => (
              <span
                key={state}
                className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${STATE_CHIP[state] ?? STATE_CHIP.OFFLINE}`}
              >
                {state} · {count}
              </span>
            ))}
          </div>

          {snapshot.open_incidents.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
              {snapshot.open_incidents.map((incident) => (
                <li key={incident.incident_id} className="px-3 py-2 text-xs text-slate-600">
                  <span className="font-mono text-[11px] text-slate-500">
                    {incident.incident_id}
                  </span>{' '}
                  {incident.summary}
                </li>
              ))}
            </ul>
          )}

          {lastAction && (
            <p className="font-mono text-[11px] text-emerald-700">{lastAction}</p>
          )}
          {cnc03 && null /* CNC-03 detail arrives with the twin (N2) */}
        </div>
      )}
    </section>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="font-mono text-[11px] text-slate-700">{value}</dd>
    </div>
  )
}
