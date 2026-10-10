import type { TwinMachine } from '../../lib/factory'
import { STATE_COLORS, STATE_LABELS, lineLabel, type MachineState } from '../../lib/twin'

/**
 * Non-WebGL fallback (N2 §14). Rendered when the canvas is unsupported or the
 * 3D scene throws — the twin stays readable as a plain factory floor table.
 */
export default function TwinFallback({
  machines,
  reason,
}: {
  machines: TwinMachine[]
  reason?: string
}) {
  if (machines.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-slate-200 bg-white">
        <p className="text-sm text-slate-500">No machines returned by the factory API.</p>
      </div>
    )
  }

  const lines = [...new Set(machines.map((m) => m.line))]

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-auto rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Factory floor — table view</h2>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {machines.length} machines
        </span>
      </div>
      {reason && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          3D view unavailable — {reason}. Showing the same FactoryWorld data as a table.
        </p>
      )}
      <div className="space-y-4">
        {lines.map((line) => (
          <table key={line} className="w-full border-collapse text-left text-sm">
            <caption className="mb-1.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              {lineLabel(line)}
            </caption>
            <thead>
              <tr className="border-b border-slate-200 text-xs text-slate-500">
                <th className="py-1 pr-3 font-medium">Machine</th>
                <th className="py-1 pr-3 font-medium">Name</th>
                <th className="py-1 pr-3 font-medium">Type</th>
                <th className="py-1 pr-3 font-medium">State</th>
                <th className="py-1 font-medium">Health</th>
              </tr>
            </thead>
            <tbody>
              {machines
                .filter((m) => m.line === line)
                .map((m) => (
                  <tr key={m.machine_id} className="border-b border-slate-100">
                    <td className="py-1.5 pr-3 font-mono text-xs">{m.machine_id}</td>
                    <td className="py-1.5 pr-3 text-slate-700">{m.name}</td>
                    <td className="py-1.5 pr-3 text-slate-500">{m.machine_type}</td>
                    <td className="py-1.5 pr-3">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium text-white"
                        style={{ backgroundColor: STATE_COLORS[m.state as MachineState] }}
                      >
                        {STATE_LABELS[m.state as MachineState]}
                      </span>
                    </td>
                    <td className="py-1.5 text-slate-600">{m.health_score ?? '—'}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        ))}
      </div>
    </div>
  )
}
