import { Component, Suspense, lazy, useCallback, useEffect, useState, type ReactNode } from 'react'

import {
  advanceSimulation,
  fetchFactorySnapshot,
  fetchLines,
  fetchMachineContext,
  fetchMachines,
  resetSimulation,
  type FactoryLine,
  type FactorySnapshot,
  type MachineContext,
  type TwinMachine,
} from '../lib/factory'
import {
  LINE_ORDER,
  STATE_COLORS,
  STATE_LABELS,
  STATE_ORDER,
  machinesWithStateChange,
  type MachineState,
} from '../lib/twin'

// three.js is heavy: keep it out of the initial bundle (same policy as N0 scaffold).
const TwinScene = lazy(() => import('../components/twin/TwinScene'))
const MachineInspector = lazy(() => import('../components/twin/MachineInspector'))
const TwinFallback = lazy(() => import('../components/twin/TwinFallback'))

/** Non-WebGL browsers must still get a usable twin (N2 §14). */
function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}

class TwinErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { error: string | null }
> {
  state = { error: null as string | null }
  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error.message : 'Twin render failure' }
  }
  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div className="flex h-full items-center justify-center rounded-xl border border-amber-300 bg-amber-50 p-8">
          <div className="max-w-md text-center">
            <p className="text-sm font-semibold text-amber-800">3D twin unavailable</p>
            <p className="mt-2 text-xs text-amber-700">
              The 3D canvas could not start in this browser (usually missing WebGL).
            </p>
            <p className="mt-2 font-mono text-[10px] text-amber-600">{this.state.error}</p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

const SHOWCASE_MACHINE = 'CNC-03'
const ADVANCE_CHOICES = [10, 30, 60] as const

export default function TwinPage() {
  const [snapshot, setSnapshot] = useState<FactorySnapshot | null>(null)
  const [machines, setMachines] = useState<TwinMachine[]>([])
  const [lines, setLines] = useState<FactoryLine[]>([])
  const [changedIds, setChangedIds] = useState<Set<string>>(new Set())
  const [context, setContext] = useState<MachineContext | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(SHOWCASE_MACHINE)
  const [contextLoading, setContextLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cameraKey, setCameraKey] = useState(0)
  const [legendOpen, setLegendOpen] = useState(true)
  const [filterLine, setFilterLine] = useState<string | null>(null)
  const [webgl] = useState<boolean>(() => webglAvailable())

  const refresh = useCallback(async (pulseFrom: TwinMachine[] | null) => {
    const [snap, list] = await Promise.all([fetchFactorySnapshot(), fetchMachines()])
    setSnapshot(snap)
    setMachines(list)
    setChangedIds(machinesWithStateChange(pulseFrom, list))
    return list
  }, [])

  const loadContext = useCallback(async (machineId: string) => {
    setContextLoading(true)
    setError(null)
    try {
      setContext(await fetchMachineContext(machineId))
    } catch (e) {
      setContext(null)
      setError(e instanceof Error ? e.message : 'Failed to load machine')
    } finally {
      setContextLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [snap, list, lineList] = await Promise.all([
          fetchFactorySnapshot(),
          fetchMachines(),
          fetchLines(),
        ])
        if (cancelled) return
        setSnapshot(snap)
        setMachines(list)
        setLines(lineList)
        // The scene starts focused on CNC-03, so the inspector must agree with it.
        if (list.some((m) => m.machine_id === SHOWCASE_MACHINE)) {
          await loadContext(SHOWCASE_MACHINE)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load factory')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [loadContext])

  const handleAdvance = useCallback(
    async (minutes: number) => {
      setBusy(true)
      setError(null)
      try {
        await advanceSimulation(minutes)
        await refresh(machines)
        if (selectedId) await loadContext(selectedId)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Advance failed')
      } finally {
        setBusy(false)
      }
    },
    [refresh, machines, selectedId, loadContext],
  )

  const handleReset = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      await resetSimulation()
      await refresh(null) // no pulse on a deterministic reset
      if (selectedId) await loadContext(selectedId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setBusy(false)
    }
  }, [refresh, selectedId, loadContext])

  const handleSelect = useCallback(
    async (machineId: string) => {
      if (!machineId) {
        setSelectedId(null)
        setContext(null)
        return
      }
      setSelectedId(machineId)
      await loadContext(machineId)
    },
    [loadContext],
  )

  if (error && !snapshot) {
    return (
      <div className="rounded-xl border border-red-300 bg-red-50 p-6 text-sm text-red-700">
        Factory API unreachable — {error}
      </div>
    )
  }
  if (!snapshot) {
    return <div className="text-sm text-slate-500">Loading factory…</div>
  }

  const orderedLines = LINE_ORDER.map((name) => lines.find((l) => l.line === name)).filter(
    (l): l is FactoryLine => Boolean(l),
  )
  const openIncidents = snapshot.open_incidents

  const scene = webgl ? (
    <TwinErrorBoundary
      fallback={
        <TwinFallback machines={machines} reason="the 3D canvas failed to start in this browser" />
      }
    >
      <Suspense
        fallback={
          <div className="flex h-full items-center justify-center text-sm text-slate-500">
            Loading 3D twin…
          </div>
        }
      >
        <TwinScene
          machines={machines}
          selectedId={selectedId}
          changedIds={changedIds}
          filterLine={filterLine}
          onSelect={(id) => void handleSelect(id)}
          cameraKey={cameraKey}
        />
      </Suspense>
    </TwinErrorBoundary>
  ) : (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
          Loading floor view…
        </div>
      }
    >
      <TwinFallback machines={machines} reason="WebGL is not available in this browser" />
    </Suspense>
  )

  return (
    <div className="flex h-full flex-col gap-3">
      {/* header strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Factory Digital Twin</h1>
          <p className="text-[11px] text-slate-500">
            {snapshot.machine_count} machines · {openIncidents.length} open incident
            {openIncidents.length === 1 ? '' : 's'} · state from FactoryWorld
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1 font-mono text-sm text-slate-700">
            {snapshot.clock}
          </span>
          <span className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-700">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
            LIVE SIM
          </span>
        </div>
      </div>

      {/* open incidents — the result of ADVANCE must be visible without selecting anything */}
      {openIncidents.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2">
          <span className="text-[11px] font-bold uppercase tracking-wide text-red-700">
            {openIncidents.length} open incident{openIncidents.length === 1 ? '' : 's'}
          </span>
          {openIncidents.map((incident) => (
            <span key={incident.incident_id} className="text-[11px] text-red-800">
              <span className="font-mono">{incident.incident_id}</span> · {incident.machine_id} ·{' '}
              {incident.type} · {incident.summary}
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1 gap-3">
        {/* main 3D column */}
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          {/* production-line rail: line groupings come from /api/factory/lines */}
          {orderedLines.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Lines
              </span>
              <button
                type="button"
                onClick={() => setFilterLine(null)}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                  filterLine === null
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-slate-200 text-slate-600 hover:border-slate-400'
                }`}
              >
                All lines · {machines.length}
              </button>
              {orderedLines.map((line) => {
                const active = filterLine === line.line
                const counts = line.machine_ids.reduce(
                  (acc, id) => {
                    const machine = machines.find((m) => m.machine_id === id)
                    if (machine) acc[machine.state] = (acc[machine.state] ?? 0) + 1
                    return acc
                  },
                  {} as Partial<Record<MachineState, number>>,
                )
                return (
                  <button
                    key={line.line}
                    type="button"
                    onClick={() => setFilterLine(active ? null : line.line)}
                    className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                      active
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-slate-200 text-slate-600 hover:border-slate-400'
                    }`}
                  >
                    {line.line.replace('_LINE', ' LINE')} · {line.machine_count}
                    <span className="flex gap-0.5">
                      {STATE_ORDER.filter((s) => (counts[s] ?? 0) > 0).map((s) => (
                        <span
                          key={s}
                          className="inline-block h-2 w-2 rounded-full"
                          style={{ backgroundColor: STATE_COLORS[s] }}
                        />
                      ))}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            {scene}

            {/* state legend overlay */}
            <div className="absolute bottom-3 left-3 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 shadow">
              <button
                type="button"
                onClick={() => setLegendOpen(!legendOpen)}
                className="text-[10px] font-semibold uppercase tracking-wide text-slate-400"
              >
                State legend {legendOpen ? '▾' : '▸'}
              </button>
              {legendOpen && (
                <div className="mt-1.5 flex gap-3">
                  {STATE_ORDER.map((state) => (
                    <span key={state} className="flex items-center gap-1 text-[10px] text-slate-600">
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-sm"
                        style={{ backgroundColor: STATE_COLORS[state] }}
                      />
                      {STATE_LABELS[state]}{' '}
                      <span className="font-mono text-slate-400">
                        {snapshot.state_distribution[state] ?? 0}
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* scenario control strip */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2.5 shadow-sm">
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleReset()}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-red-400 hover:text-red-700 disabled:opacity-50"
              >
                Reset
              </button>
              <span className="text-[10px] uppercase tracking-wide text-slate-400">Advance</span>
              {ADVANCE_CHOICES.map((minutes) => (
                <button
                  key={minutes}
                  type="button"
                  disabled={busy}
                  onClick={() => void handleAdvance(minutes)}
                  className="rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:border-blue-500 disabled:opacity-50"
                >
                  +{minutes} min
                </button>
              ))}
              <button
                type="button"
                onClick={() => setCameraKey((k) => k + 1)}
                className="ml-2 rounded-md border border-slate-200 px-3 py-1.5 text-xs text-slate-500 hover:border-slate-400 hover:text-slate-700"
              >
                Reset View
              </button>
            </div>
            <span className="text-[11px] text-slate-500">
              Simulation time is authoritative from FactoryWorld — shown in the header, never the
              wall clock.
            </span>
          </div>
        </div>

        {/* machine inspector */}
        <TwinErrorBoundary>
          <Suspense fallback={<div className="w-96 shrink-0 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading inspector…</div>}>
            <MachineInspector
              context={context}
              loading={contextLoading}
              onClose={() => {
                setSelectedId(null)
                setContext(null)
              }}
            />
          </Suspense>
        </TwinErrorBoundary>
      </div>
    </div>
  )
}
