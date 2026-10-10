import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { FactorySnapshot, TwinMachine } from '../lib/factory'

const snapshot: FactorySnapshot = {
  clock: '2026-10-05 06:00:00',
  machine_count: 23,
  state_distribution: { HEALTHY: 19, WARNING: 2, MAINTENANCE: 1, OFFLINE: 1 },
  open_incidents: [],
}
const machines: TwinMachine[] = [
  {
    machine_id: 'CNC-03',
    name: 'Vertical Mill 3',
    machine_type: 'CNC',
    line: 'CNC_LINE',
    state: 'WARNING',
    health_score: 63,
    x_m: 16,
    y_m: 18,
    z_m: 0,
  },
]

describe('CommandCenter', () => {
  it('renders the real snapshot (23 machines, sim clock, CNC-03 state, twin link)', async () => {
    vi.doMock('../lib/factory', async (importOriginal) => {
      const actual = await importOriginal<typeof import('../lib/factory')>()
      return {
        ...actual,
        fetchFactorySnapshot: () => Promise.resolve(snapshot),
        fetchMachines: () => Promise.resolve(machines),
      }
    })
    vi.resetModules()

    const { default: CommandCenter } = await import('./CommandCenter')
    render(
      <MemoryRouter>
        <CommandCenter />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('23')).toBeInTheDocument())
    expect(screen.getByText('2026-10-05 06:00:00')).toBeInTheDocument()
    expect(screen.getAllByText('Warning').length).toBeGreaterThan(0)   // CNC-03 card + legend chip
    expect(screen.getByText('Healthy')).toBeInTheDocument()
    expect(screen.getByText('19', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Open Digital Twin →')).toBeInTheDocument()
    expect(screen.getAllByText('Later milestone').length).toBe(7)
  })
})
