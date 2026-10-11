import { useEffect, useState } from 'react'

import { fetchAgentRunSummaries, fetchAgentRunDetail, type AgentRunSummary, type AgentStep } from '../lib/factory'
import { RUN_LABEL, stepTone, RUN_TONE } from '../lib/agents'

export default function AgentActivity() {
  const [runs, setRuns] = useState<AgentRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState<AgentRunSummary | null>(null)
  const [detail, setDetail] = useState<{ runId: string; steps: AgentStep[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchAgentRunSummaries()
      .then((data) => {
        if (!cancelled) {
          setRuns(data)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load agent runs')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!selectedRun) {
      setDetail(null)
      return
    }
    let cancelled = false
    fetchAgentRunDetail(selectedRun.run_id)
      .then((data) => {
        if (!cancelled) setDetail({ runId: selectedRun.run_id, steps: data.steps })
      })
      .catch(console.error)
    return () => { cancelled = true }
  }, [selectedRun])

  if (loading) {
    return <div className="text-sm text-slate-500">Loading agent runs…</div>
  }
  if (error) {
    return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Agent Operations Center</h1>
          <p className="text-xs text-slate-500">Autonomous maintenance & optimisation runs — fully traced</p>
        </div>
        <div className="text-[10px] text-slate-400">
          {runs.length} total runs
        </div>
      </div>

      {error && <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

      {/* Runs List */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Run ID</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Incident</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Machine</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Status</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Active Agent</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Model</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Outcome</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Started</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Completed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-3 py-8 text-center text-slate-400">
                    No agent runs recorded yet. Advance the simulation on the Twin to trigger the Watcher.
                  </td>
                </tr>
              ) : (
                runs.slice().sort((a, b) => b.started_at.localeCompare(a.started_at)).map((run) => (
                  <tr key={run.run_id} className="hover:bg-slate-50 cursor-pointer" onClick={() => setSelectedRun(run)}>
                    <td className="px-3 py-2 font-mono text-xs text-blue-600 hover:underline">{run.run_id}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-600">{run.incident_id}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-600">{run.machine_id}</td>
                    <td className="px-3 py-2">
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-medium"
                        style={{ backgroundColor: `${RUN_TONE[run.status as keyof typeof RUN_TONE]}20`, color: RUN_TONE[run.status as keyof typeof RUN_TONE] }}
                      >
                        {RUN_LABEL[run.status as keyof typeof RUN_LABEL] ?? run.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600 text-xs">{run.active_agent ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{run.model_provider}/{run.model_name}</td>
                    <td className="px-3 py-2 text-slate-600 text-xs">{run.outcome ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{run.started_at}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{run.completed_at ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Selected Run Detail */}
      {selectedRun && (
        <section className="rounded-xl border border-blue-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-blue-50 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-500" />
              <span className="text-[11px] font-bold uppercase tracking-wide text-blue-800">Factora is responding</span>
              <span className="font-mono text-[11px] text-blue-700">{selectedRun.run_id}</span>
              <span className="rounded border border-blue-300 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
                {RUN_LABEL[selectedRun.status as keyof typeof RUN_LABEL] ?? selectedRun.status}
              </span>
            </div>
            <button
              onClick={() => setSelectedRun(null)}
              className="text-[11px] text-slate-500 hover:text-slate-800"
            >
              hide
            </button>
          </div>

          <div className="border-b border-slate-100 px-4 py-2 text-[11px] text-slate-600">
            <span className="font-semibold">Goal:</span> {selectedRun.goal}
            <span className="ml-2 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
              {selectedRun.model_provider}/{selectedRun.model_name}
            </span>
          </div>

          {/* Timeline */}
          <div className="max-h-80 overflow-y-auto px-4 py-3">
            {detail?.steps.length === 0 ? (
              <p className="text-xs text-slate-500">Loading steps…</p>
            ) : (
              <ol>
                {detail?.steps.map((step) => (
                  <li key={step.sequence} className="flex gap-2.5 py-1.5">
                    <span
                      className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: stepTone(step) }}
                      aria-hidden
                    />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                          {['watcher', 'coordinator', 'maintenance', 'production', 'finance'].includes(step.agent) 
                            ? step.agent.charAt(0).toUpperCase() + step.agent.slice(1) 
                            : step.agent}
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
            )}
          </div>

          {selectedRun.outcome && (
            <div className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-700">
              <span className="font-semibold">Outcome:</span> {selectedRun.outcome}
            </div>
          )}
        </section>
      )}
    </div>
  )
}