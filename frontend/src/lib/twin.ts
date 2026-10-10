/**
 * Pure digital-twin logic, deliberately free of Three.js/React so it is
 * unit-testable (N2 §21): state colours, line labels, floor placement, lane
 * geometry and derived UI facts. Every input is a typed API payload — there is
 * no factory truth in this file.
 */
import type { TwinMachine } from './factory'

export type MachineState =
  | 'HEALTHY' | 'WARNING' | 'CRITICAL' | 'MAINTENANCE' | 'OFFLINE'

/** Legend / chart ordering (not insertion order of the colour map). */
export const STATE_ORDER: MachineState[] = [
  'HEALTHY', 'WARNING', 'CRITICAL', 'MAINTENANCE', 'OFFLINE',
]

/** Design-token palette, identical to `--state-*` in index.css (mockup 02). */
export const STATE_COLORS: Record<MachineState, string> = {
  HEALTHY: '#16a34a',
  WARNING: '#d97706',
  CRITICAL: '#dc2626',
  MAINTENANCE: '#546e8f',
  OFFLINE: '#9ca3af',
}

export const STATE_LABELS: Record<MachineState, string> = {
  HEALTHY: 'Healthy',
  WARNING: 'Warning',
  CRITICAL: 'Critical',
  MAINTENANCE: 'Maintenance',
  OFFLINE: 'Offline',
}

/** Production lines present in FactoryWorld, in floor order (top → bottom). */
export const LINE_ORDER = [
  'ASSEMBLY_LINE', 'CNC_LINE', 'PRESS_LINE', 'PACKAGING_LINE', 'QUALITY_LINE',
] as const

/** Subtle pastel floor tint per line — lanes only, never state meaning. */
export const LINE_FLOOR_COLORS: Record<string, string> = {
  ASSEMBLY_LINE: '#e0f2fe',
  CNC_LINE: '#dbeafe',
  PRESS_LINE: '#fee2e2',
  PACKAGING_LINE: '#f3e8ff',
  QUALITY_LINE: '#ecfccb',
}

const LINE_LABELS: Record<string, string> = {
  ASSEMBLY_LINE: 'Assembly Line',
  CNC_LINE: 'CNC Line',
  PRESS_LINE: 'Press Line',
  PACKAGING_LINE: 'Packaging Line',
  QUALITY_LINE: 'Quality Line',
}

export function lineLabel(line: string): string {
  return LINE_LABELS[line] ?? line.replace(/_/g, ' ')
}

/** Base scene size of a machine body before spacing adaptation (metres). */
export const BASE_FOOTPRINT = 7

/** Machines whose state changed between two snapshots (one-time pulse). */
export function machinesWithStateChange(
  before: TwinMachine[] | null,
  after: TwinMachine[],
): Set<string> {
  if (!before) return new Set()
  const previous = new Map(before.map((m) => [m.machine_id, m.state]))
  const changed = new Set<string>()
  for (const machine of after) {
    if (previous.get(machine.machine_id) !== machine.state) {
      changed.add(machine.machine_id)
    }
  }
  return changed
}

/** Procedural geometry family per machine type. */
export type MachineGeometry = 'mill' | 'press' | 'cell' | 'packer' | 'station'

export function geometryForType(machineType: string): MachineGeometry {
  switch (machineType) {
    case 'CNC':
      return 'mill'
    case 'PRESS':
      return 'press'
    case 'ASSEMBLY':
      return 'cell'
    case 'PACKAGING':
      return 'packer'
    case 'QUALITY':
      return 'station'
    default:
      return 'cell'
  }
}

export interface TwinFloorScale {
  scale: number
  offset: [number, number]
}

/**
 * Centre the world coordinates into a scene of `extent` scene-metres:
 * FactoryWorld spans x ∈ [6, 41], y ∈ [2, 66], so we normalise around the
 * middle and scale uniformly (aspect preserved — no warped floor).
 */
export function floorTransform(
  machines: TwinMachine[],
  extent = 110,
): TwinFloorScale {
  if (machines.length === 0) return { scale: 1, offset: [0, 0] }
  const xs = machines.map((m) => m.x_m)
  const ys = machines.map((m) => m.y_m)
  const spanX = Math.max(...xs) - Math.min(...xs) || 1
  const spanY = Math.max(...ys) - Math.min(...ys) || 1
  const scale = Math.min(extent / (spanX + 10), extent / (spanY + 10))
  const centerX = (Math.max(...xs) + Math.min(...xs)) / 2
  const centerY = (Math.max(...ys) + Math.min(...ys)) / 2
  return { scale, offset: [centerX, centerY] }
}

/**
 * Body size that never overlaps neighbours: derived from the smallest gap
 * between two machines on the same line, in scene units. FactoryWorld places
 * machines on a 5 m pitch, so a fixed footprint would collide once scaled.
 */
export function footprintFor(
  machines: TwinMachine[],
  scale: number,
  min = 3.5,
  max = 9,
): number {
  const byLine = new Map<string, number[]>()
  for (const machine of machines) {
    const xs = byLine.get(machine.line) ?? []
    xs.push(machine.x_m)
    byLine.set(machine.line, xs)
  }
  let smallest = Infinity
  for (const xs of byLine.values()) {
    const sorted = [...xs].sort((a, b) => a - b)
    for (let i = 1; i < sorted.length; i += 1) {
      const gap = (sorted[i] - sorted[i - 1]) * scale
      if (gap > 0 && gap < smallest) smallest = gap
    }
  }
  if (!Number.isFinite(smallest)) return BASE_FOOTPRINT
  return Math.min(max, Math.max(min, smallest * 0.7))
}

export interface Lane {
  line: string
  label: string
  /** Scene-space centre of the lane along the floor depth axis. */
  z: number
  /** Scene-space bounds along the floor width axis. */
  xMin: number
  xMax: number
  color: string
}

/**
 * One lane per production line, derived from where that line's machines
 * actually are — never hardcoded. Sorted top → bottom (floor order).
 */
export function lanesFor(
  machines: TwinMachine[],
  scale: number,
  offset: [number, number],
  footprint = BASE_FOOTPRINT,
): Lane[] {
  const grouped = new Map<string, { xs: number[]; zs: number[] }>()
  for (const machine of machines) {
    const entry = grouped.get(machine.line) ?? { xs: [], zs: [] }
    entry.xs.push((machine.x_m - offset[0]) * scale)
    entry.zs.push((machine.y_m - offset[1]) * scale)
    grouped.set(machine.line, entry)
  }
  const pad = footprint * 0.9
  return [...grouped.entries()]
    .map(([line, entry]) => ({
      line,
      label: lineLabel(line),
      xMin: Math.min(...entry.xs) - pad,
      xMax: Math.max(...entry.xs) + pad,
      z: entry.zs.reduce((a, b) => a + b, 0) / entry.zs.length,
      color: LINE_FLOOR_COLORS[line] ?? '#eef2f7',
    }))
    .sort((a, b) => a.z - b.z)
}
