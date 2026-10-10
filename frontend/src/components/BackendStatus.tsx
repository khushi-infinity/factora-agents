import { useCallback, useEffect, useState } from 'react'
import type { HealthPayload } from '../lib/api'
import { fetchHealth } from '../lib/api'
import { observabilityLabel, summariseHealth, type Tone } from '../lib/health'

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; payload: HealthPayload; roundTripMs: number }
  | { kind: 'error'; message: string }

const TONE_CHIP: Record<Tone, string> = {
  ok: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700',
  warn: 'border-amber-500/40 bg-amber-500/10 text-amber-700',
  error: 'border-red-500/40 bg-red-500/10 text-red-700',
  neutral: 'border-slate-300 bg-slate-100 text-slate-600',
}

const BACKEND_START_COMMAND = 'cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000'

export default function BackendStatus() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  const load = useCallback(async () => {
    const started = performance.now()
    try {
      const payload = await fetchHealth()
      setState({ kind: 'ok', payload, roundTripMs: Math.round(performance.now() - started) })
    } catch (error) {
      setState({ kind: 'error', message: error instanceof Error ? error.message : 'Unknown error' })
    }
  }, [])

  useEffect(() => {
    // Initial fetch on mount: the setState calls are async (after the fetch
    // resolves), not synchronous effect-body state updates. The lint rule
    // cannot see that through the callback boundary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Backend API</h2>
          <p className="mt-0.5 font-mono text-[11px] text-slate-500">
            GET /api/health → FastAPI on 127.0.0.1:8000
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:border-blue-500 hover:text-blue-700"
        >
          Re-check
        </button>
      </div>

      <div className="mt-4">
        {state.kind === 'loading' && <p className="text-sm text-slate-500">Contacting the API…</p>}

        {state.kind === 'error' && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-3">
            <p className="text-sm font-medium text-red-700">API unreachable</p>
            <p className="mt-1 font-mono text-[11px] text-red-600">{state.message}</p>
            <p className="mt-2 text-xs text-red-700/80">
              Start it with:
              <code className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px]">
                {BACKEND_START_COMMAND}
              </code>
            </p>
          </div>
        )}

        {state.kind === 'ok' && (
          <div className="space-y-4">
            <div
              className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${
                TONE_CHIP[summariseHealth(state.payload).tone]
              }`}
            >
              {summariseHealth(state.payload).label}
            </div>

            <dl className="grid grid-cols-3 gap-x-4 gap-y-2 text-xs">
              <Fact label="Service" value={state.payload.service} />
              <Fact label="Version" value={state.payload.version} />
              <Fact label="Environment" value={state.payload.environment} />
              <Fact label="API uptime" value={formatUptime(state.payload.uptime_s)} />
              <Fact label="Round trip" value={`${state.roundTripMs} ms`} />
              <Fact label="Tracing" value={state.payload.observability.status} />
            </dl>

            <p className="text-[11px] leading-relaxed text-slate-500">
              {observabilityLabel(state.payload.observability.status)}
              {state.payload.observability.detail ? ` — ${state.payload.observability.detail}` : ''}
            </p>
          </div>
        )}
      </div>
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

function formatUptime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  const total = Math.floor(seconds)
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  return `${minutes}m ${String(total % 60).padStart(2, '0')}s`
}
