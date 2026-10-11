import { useEffect, useState } from 'react'

import { fetchAgentRun, stepTone, type AgentRun, type AgentStep } from '../lib/agents'

const AGENT_LABEL: Record<string, string> = {
  watcher: 'Watcher',
  coordinator: 'Coordinator',
  maintenance: 'Maintenance',
}

const RUN_LABEL: Record<string, string> = {
  VERIFIED: 'VERIFIED',
  ESCALATED: 'ESCALATED TO HUMAN',
  FAILED: 'FAILED',
}

/** A small spinner so the timeline reads as live activity, not a static log. */
function isLive(run: AgentRun): boolean {
  return run.status !== 'VERIFIED' && run.status !== 'FAILED' && run.status !== 'ESCALATED'
}

export default function AgentActivity({
  run,
  onClose,
}: {
  run: AgentRun | null
  onClose?: () => void
}) {
  const [detail, setDetail] = useState<{ runId: string; steps: AgentStep[] } | null>(null)
  const runId = run?.run_id ?? null

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    void (async () => {
      try {
        const full = await fetchAgentRun(runId)
        if (!cancelled) setDetail({ runId, steps: full.steps })
      } catch {
        // keep the timeline empty rather than inventing steps
      }
    })()
    return () => {
      cancelled = true
    }
  }, [runId])

  if (!run) return null

  const steps = detail && detail.runId === run.run_id ? detail.steps : []
  const live = isLive(run)

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-blue-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-blue-50 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              live ? 'animate-pulse bg-blue-500' : 'bg-slate-400'
            }`}
          />
          <span className="text-[11px] font-bold uppercase tracking-wide text-blue-800">
            Factora is responding
          </span>
          <span className="font-mono text-[11px] text-blue-700">{run.run_id}</span>
          <span className="rounded border border-blue-300 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
            {RUN_LABEL[run.status] ?? run.status}
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-[11px] text-slate-500 hover:text-slate-800"
          >
            hide
          </button>
        )}
      </div>

      <div className="border-b border-slate-100 px-4 py-2 text-[11px] text-slate-600">
        <span className="font-semibold">Goal:</span> {run.goal}
        <span className="ml-2 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
          {run.model_provider}/{run.model_name}
        </span>
      </div>

      <ol className="max-h-72 overflow-y-auto px-4 py-3">
        {steps.length === 0 && (
          <li className="text-xs text-slate-500">Recording the first step…</li>
        )}
        {steps.map((step) => (
          <li key={step.sequence} className="flex gap-2.5 py-1.5">
            <span
              className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: stepTone(step) }}
              aria-hidden
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {AGENT_LABEL[step.agent] ?? step.agent}
                </span>
                <span className="rounded bg-slate-100 px-1 py-0.5 text-[10px] text-slate-600">
                  {step.type.toLowerCase()}
                </span>
                {step.status !== 'OK' && (
                  <span className="font-mono text-[10px] text-slate-400">{step.status}</span>
                )}
              </div>
              <p className="break-words text-[11px] text-slate-700">{step.summary}</p>
            </div>
          </li>
        ))}
      </ol>

      {run.outcome && (
        <div className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-700">
          <span className="font-semibold">Outcome:</span> {run.outcome}
        </div>
      )}
    </div>
  )
}
