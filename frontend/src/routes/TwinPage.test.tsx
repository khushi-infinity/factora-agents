import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { FactoryLine, FactorySnapshot, MachineContext, TwinMachine } from '../lib/factory'

const IDS = [
  ...['ASM-01', 'ASM-02', 'ASM-03', 'ASM-04', 'ASM-05'].map((id, i) => ({ id, line: 'ASSEMBLY_LINE', i })),
  ...['CNC-01', 'CNC-02', 'CNC-03', 'CNC-04', 'CNC-05', 'CNC-06', 'CNC-07', 'CNC-08'].map((id, i) => ({ id, line: 'CNC_LINE', i })),
  ...['PKG-01', 'PKG-02', 'PKG-03'].map((id, i) => ({ id, line: 'PACKAGING_LINE', i })),
  ...['PRS-01', 'PRS-02', 'PRS-03', 'PRS-04'].map((id, i) => ({ id, line: 'PRESS_LINE', i })),
  ...['QLT-01', 'QLT-02', 'QLT-03'].map((id, i) => ({ id, line: 'QUALITY_LINE', i })),
]

const stateOf = (id: string): TwinMachine['state'] =>
  id === 'CNC-03' || id === 'CNC-06'
    ? 'WARNING'
    : id === 'PRS-03'
      ? 'MAINTENANCE'
      : id === 'PKG-03'
        ? 'OFFLINE'
        : 'HEALTHY'

const machines: TwinMachine[] = IDS.map(({ id, line, i }) => ({
  machine_id: id,
  name: id,
  machine_type: 'CNC',
  line,
  state: stateOf(id),
  health_score: 90,
  x_m: 6 + i * 5,
  y_m: line === 'ASSEMBLY_LINE' ? 2 : line === 'CNC_LINE' ? 18 : line === 'PRESS_LINE' ? 34 : line === 'PACKAGING_LINE' ? 50 : 66,
  z_m: 0,
}))

const snapshot: FactorySnapshot = {
  clock: '2026-10-05 06:00:00',
  machine_count: 23,
  state_distribution: { HEALTHY: 19, WARNING: 2, MAINTENANCE: 1, OFFLINE: 1 },
  open_incidents: [],
}

const lines: FactoryLine[] = [
  { line: 'ASSEMBLY_LINE', machine_ids: [], machine_count: 5 },
  { line: 'CNC_LINE', machine_ids: [], machine_count: 8 },
  { line: 'PACKAGING_LINE', machine_ids: [], machine_count: 3 },
  { line: 'PRESS_LINE', machine_ids: [], machine_count: 4 },
  { line: 'QUALITY_LINE', machine_ids: [], machine_count: 3 },
]

const context: MachineContext = {
  machine: {
    ...machines.find((m) => m.machine_id === 'CNC-03')!,
    name: 'Vertical Mill 3',
    manufacturer: 'Okuma',
    model: 'MB-4000A',
    installed_year: 2019,
    output_per_hour: 30,
    cost_per_hour_usd: 48.5,
    contribution_per_unit_usd: 6.2,
    scrap_cost_per_unit_usd: 12.4,
    latest_telemetry: {
      machine_id: 'CNC-03',
      ts: '2026-10-05 05:50:00',
      vibration_mm_s: 4.99,
      bearing_temp_c: 70.7,
      spindle_rpm: 8260,
      motor_current_a: 23.7,
      cycle_time_s: 117.2,
      production_rate_uph: 26.2,
      defect_rate_pct: 5.0,
    },
  },
  telemetry: [
    { machine_id: 'CNC-03', ts: '2026-10-05 05:40:00', vibration_mm_s: 4.8, bearing_temp_c: 70.1, spindle_rpm: null, motor_current_a: null, cycle_time_s: null, production_rate_uph: null, defect_rate_pct: null },
    { machine_id: 'CNC-03', ts: '2026-10-05 05:45:00', vibration_mm_s: 4.9, bearing_temp_c: 70.4, spindle_rpm: null, motor_current_a: null, cycle_time_s: null, production_rate_uph: null, defect_rate_pct: null },
    { machine_id: 'CNC-03', ts: '2026-10-05 05:50:00', vibration_mm_s: 4.99, bearing_temp_c: 70.7, spindle_rpm: null, motor_current_a: null, cycle_time_s: null, production_rate_uph: null, defect_rate_pct: null },
  ],
  maintenance: [],
  work_orders: [],
  production: [],
  incidents: [],
  economics_note: 'Synthetic demo economics',
}

describe('TwinPage', () => {
  it('renders the twin shell from real API data and falls back without WebGL', async () => {
    vi.doMock('../lib/factory', async (importOriginal) => {
      const actual = await importOriginal<typeof import('../lib/factory')>()
      return {
        ...actual,
        fetchFactorySnapshot: () => Promise.resolve(snapshot),
        fetchMachines: () => Promise.resolve(machines),
        fetchLines: () => Promise.resolve(lines),
        fetchMachineContext: () => Promise.resolve(context),
        advanceSimulation: () => Promise.resolve({ clock: '', emitted_readings: 0, cnc03_state: 'CRITICAL', open_incidents: 1 }),
        resetSimulation: () => Promise.resolve({ status: 'reset', clock: '', machines: 23, telemetry_rows: 3312 }),
      }
    })

    const { default: TwinPage } = await import('./TwinPage')
    render(
      <MemoryRouter>
        <TwinPage />
      </MemoryRouter>,
    )

    // header: authoritative sim clock + machine count, never the wall clock
    expect(await screen.findByText('Factory Digital Twin')).toBeInTheDocument()
    expect(screen.getByText('2026-10-05 06:00:00')).toBeInTheDocument()
    expect(screen.getByText(/23 machines/)).toBeInTheDocument()

    // scenario controls (backend supports these exact steps)
    expect(await screen.findByRole('button', { name: 'Reset' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+10 min' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+30 min' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+60 min' })).toBeInTheDocument()

    // production-line rail comes from /api/factory/lines
    expect(await screen.findByText('CNC LINE · 8')).toBeInTheDocument()
    expect(screen.getByText('QUALITY LINE · 3')).toBeInTheDocument()

    // no WebGL in jsdom → the table fallback must carry every machine
    expect(await screen.findByText('Factory floor — table view')).toBeInTheDocument()
    const ids = await screen.findAllByText(/^(ASM|CNC|PKG|PRS|QLT)-\d+$/)
    expect(new Set(ids.map((el) => el.textContent)).size).toBe(23)

    // state legend + floor table together reflect the authoritative distribution
    expect(await screen.findByText(/^State legend/)).toBeInTheDocument()
    expect(screen.getAllByText('Healthy').length).toBeGreaterThanOrEqual(19)

    // the preselected CNC-03 inspector shows real context data
    await waitFor(() => expect(screen.getByText(/Vertical Mill 3/)).toBeInTheDocument())
    expect(screen.getByText('Synthetic demo economics')).toBeInTheDocument()
    // latest-telemetry label + a dedicated vibration trend chart, plus both
    // separate charts (mm/s and °C would share one useless axis otherwise)
    expect(screen.getAllByText('Vibration').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('(mm/s)').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('(°C)').length).toBeGreaterThanOrEqual(1)
  })
})
