import { useEffect, useState } from 'react'

import { fetchWorkOrders, createWorkOrder, updateWorkOrder, type WorkOrder, type WorkOrderCreate, type WorkOrderUpdate } from '../lib/factory'

export default function WorkOrders() {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'open' | 'agent' | 'completed'>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [newWO, setNewWO] = useState<WorkOrderCreate>({
    machine_id: 'CNC-03',
    issue: '',
    proposed_action: '',
    priority: 'MEDIUM',
    estimated_cost_usd: 5000,
  })

  useEffect(() => {
    loadWorkOrders()
  }, [filter])

  const loadWorkOrders = async () => {
    setLoading(true)
    try {
      const data = await fetchWorkOrders(filter === 'open')
      if (filter === 'agent') {
        setWorkOrders(data.filter(wo => wo.source === 'AGENT'))
      } else if (filter === 'completed') {
        setWorkOrders(data.filter(wo => wo.status === 'COMPLETED'))
      } else {
        setWorkOrders(data)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load work orders')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createWorkOrder(newWO)
      setShowCreate(false)
      setNewWO({ machine_id: 'CNC-03', issue: '', proposed_action: '', priority: 'MEDIUM', estimated_cost_usd: 5000 })
      await loadWorkOrders()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create work order')
    }
  }

  const handleStatusChange = async (wo: WorkOrder, status: WorkOrderUpdate['status']) => {
    try {
      await updateWorkOrder(wo.work_order_id, { status })
      await loadWorkOrders()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update work order')
    }
  }

  if (loading) return <div className="text-sm text-slate-500">Loading work orders…</div>
  if (error) return <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-800">Work Orders</h1>
          <p className="text-xs text-slate-500">Maintenance work order management — includes autonomous AGENT orders</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
        >
          {showCreate ? 'Cancel' : 'Create Work Order'}
        </button>
      </div>

      {error && <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

      {showCreate && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-[10px] font-medium text-slate-500 mb-1">Machine</label>
                <select
                  value={newWO.machine_id}
                  onChange={(e) => setNewWO({ ...newWO, machine_id: e.target.value })}
                  className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700"
                >
                  {['CNC-01','CNC-02','CNC-03','CNC-04','CNC-05','CNC-06','CNC-07','CNC-08',
                    'PRESS-01','PRESS-02','PRESS-03','PRESS-04',
                    'ASSEMBLY-01','ASSEMBLY-02',
                    'PACKAGING-01','PACKAGING-02',
                    'QUALITY-01','QUALITY-02'].map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-medium text-slate-500 mb-1">Priority</label>
                <select
                  value={newWO.priority}
                  onChange={(e) => setNewWO({ ...newWO, priority: e.target.value as any })}
                  className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-1">Issue</label>
              <textarea
                value={newWO.issue}
                onChange={(e) => setNewWO({ ...newWO, issue: e.target.value })}
                rows={3}
                className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700"
                placeholder="Describe the issue…"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-1">Proposed Action</label>
              <textarea
                value={newWO.proposed_action}
                onChange={(e) => setNewWO({ ...newWO, proposed_action: e.target.value })}
                rows={3}
                className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700"
                placeholder="Describe the proposed action…"
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-[10px] font-medium text-slate-500 mb-1">Estimated Cost (USD)</label>
                <input
                  type="number"
                  value={newWO.estimated_cost_usd ?? ''}
                  onChange={(e) => setNewWO({ ...newWO, estimated_cost_usd: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700"
                  step="100"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button type="button" onClick={() => setShowCreate(false)} className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="submit" className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">Create</button>
            </div>
          </form>
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        {(['all', 'open', 'agent', 'completed'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {error && <div className="rounded-xl border border-red-300 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="text-sm text-slate-500">Loading work orders…</div>
      ) : (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">ID</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Machine</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Issue</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Source</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Priority</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Status</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Cost (USD)</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Created</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {workOrders.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-8 text-center text-slate-400">No work orders found.</td>
                  </tr>
                ) : (
                  workOrders.map((wo) => (
                    <tr key={wo.work_order_id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-mono text-xs text-blue-600">{wo.work_order_id}</td>
                      <td className="px-3 py-2 text-slate-600">{wo.machine_id}</td>
                      <td className="px-3 py-2 text-slate-600 max-w-xs truncate">{wo.issue}</td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                          wo.source === 'AGENT' ? 'bg-amber-100 text-amber-700' :
                          wo.source === 'MANUAL' ? 'bg-blue-100 text-blue-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {wo.source}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                          wo.priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                          wo.priority === 'HIGH' ? 'bg-amber-100 text-amber-700' :
                          wo.priority === 'MEDIUM' ? 'bg-blue-100 text-blue-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {wo.priority}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium ${
                          wo.status === 'OPEN' ? 'bg-slate-100 text-slate-700' :
                          wo.status === 'ASSIGNED' ? 'bg-blue-100 text-blue-700' :
                          wo.status === 'IN_PROGRESS' ? 'bg-amber-100 text-amber-700' :
                          wo.status === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {wo.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-600">{wo.estimated_cost_usd ? `$${wo.estimated_cost_usd.toLocaleString()}` : '—'}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{wo.created_at}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          {wo.status !== 'COMPLETED' && wo.status !== 'CANCELLED' && (
                            <select
                              value={wo.status}
                              onChange={(e) => handleStatusChange(wo, e.target.value as any)}
                              className="rounded border border-slate-200 px-2 py-1 text-[10px] text-slate-700"
                            >
                              <option value="OPEN">Open</option>
                              <option value="ASSIGNED">Assigned</option>
                              <option value="IN_PROGRESS">In Progress</option>
                              <option value="COMPLETED">Completed</option>
                              <option value="CANCELLED">Cancelled</option>
                            </select>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}