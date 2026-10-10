import { describe, expect, it } from 'vitest'

import type { TwinMachine } from './factory'
import {
  LINE_ORDER,
  STATE_COLORS,
  STATE_LABELS,
  STATE_ORDER,
  floorTransform,
  footprintFor,
  geometryForType,
  lanesFor,
  lineLabel,
  machinesWithStateChange,
} from './twin'

const machine = (
  id: string,
  state: TwinMachine['state'],
  x = 10,
  y = 10,
  line = 'CNC_LINE',
): TwinMachine => ({
  machine_id: id,
  name: id,
  machine_type: 'CNC',
  line,
  state,
  health_score: 80,
  x_m: x,
  y_m: y,
  z_m: 0,
})

describe('state palette', () => {
  it('maps the five states to the mockup colours', () => {
    expect(STATE_COLORS.HEALTHY).toBe('#16a34a')
    expect(STATE_COLORS.WARNING).toBe('#d97706')
    expect(STATE_COLORS.CRITICAL).toBe('#dc2626')
    expect(STATE_COLORS.MAINTENANCE).toBe('#546e8f')
    expect(STATE_COLORS.OFFLINE).toBe('#9ca3af')
  })

  it('has a human label for each state, in legend order', () => {
    expect(STATE_LABELS.CRITICAL).toBe('Critical')
    expect(STATE_LABELS.MAINTENANCE).toBe('Maintenance')
    expect(STATE_ORDER).toEqual(['HEALTHY', 'WARNING', 'CRITICAL', 'MAINTENANCE', 'OFFLINE'])
  })
})

describe('machinesWithStateChange', () => {
  it('flags machines whose state changed between snapshots (CNC-03 story)', () => {
    const before = [
      machine('CNC-03', 'WARNING', 16, 18),
      machine('CNC-01', 'HEALTHY'),
    ]
    const after = [
      machine('CNC-03', 'CRITICAL', 16, 18),
      machine('CNC-01', 'HEALTHY'),
    ]
    const changed = machinesWithStateChange(before, after)
    expect(changed.has('CNC-03')).toBe(true)
    expect(changed.has('CNC-01')).toBe(false)
  })

  it('returns empty set when there was no prior snapshot (no pulse on load)', () => {
    expect(machinesWithStateChange(null, [machine('CNC-03', 'WARNING')]).size).toBe(0)
  })
})

describe('geometryForType', () => {
  it('maps machine types to procedural geometry kinds', () => {
    expect(geometryForType('CNC')).toBe('mill')
    expect(geometryForType('PRESS')).toBe('press')
    expect(geometryForType('ASSEMBLY')).toBe('cell')
    expect(geometryForType('PACKAGING')).toBe('packer')
    expect(geometryForType('QUALITY')).toBe('station')
    expect(geometryForType('UNKNOWN')).toBe('cell')
  })
})

describe('floorTransform', () => {
  it('normalises FactoryWorld coordinates around the centre', () => {
    const machines = [machine('A', 'HEALTHY', 6, 2), machine('B', 'HEALTHY', 41, 66)]
    const { scale, offset } = floorTransform(machines, 110)
    expect(scale).toBeGreaterThan(0)
    expect(offset).toEqual([23.5, 34])
  })

  it('handles an empty inventory safely', () => {
    const { scale, offset } = floorTransform([], 110)
    expect(scale).toBe(1)
    expect(offset).toEqual([0, 0])
  })
})

describe('footprintFor', () => {
  it('shrinks bodies to the smallest same-line gap so neighbours cannot overlap', () => {
    // 5 m pitch at scale 1.486 → 7.43 scene units apart; a 7-wide body + plinth would collide.
    const line = [
      machine('A', 'HEALTHY', 6, 18),
      machine('B', 'HEALTHY', 11, 18),
      machine('C', 'HEALTHY', 16, 18),
    ]
    const footprint = footprintFor(line, 1.486)
    expect(footprint).toBeLessThan(7.43 * 0.85)
    expect(footprint).toBeGreaterThanOrEqual(3.5)
  })

  it('keeps the base footprint when no spacing is known (single machine)', () => {
    expect(footprintFor([machine('A', 'HEALTHY')], 1.486)).toBe(7)
  })
})

describe('lanesFor', () => {
  it('derives one lane per production line from real machine positions', () => {
    const machines = [
      machine('CNC-01', 'HEALTHY', 6, 18, 'CNC_LINE'),
      machine('CNC-02', 'HEALTHY', 41, 18, 'CNC_LINE'),
      machine('PRS-01', 'HEALTHY', 6, 34, 'PRESS_LINE'),
      machine('PRS-02', 'HEALTHY', 21, 34, 'PRESS_LINE'),
    ]
    const { scale, offset } = floorTransform(machines, 110)
    const lanes = lanesFor(machines, scale, offset, 5)

    expect(lanes).toHaveLength(2)
    expect(lanes.map((l) => l.line)).toEqual(['CNC_LINE', 'PRESS_LINE']) // sorted top → bottom
    const cnc = lanes[0]
    expect(cnc.label).toBe('CNC Line')
    expect(cnc.xMin).toBeLessThan(cnc.xMax)
    // lane must contain every machine body of its line
    const firstX = (6 - offset[0]) * scale
    const lastX = (41 - offset[0]) * scale
    expect(cnc.xMin).toBeLessThanOrEqual(firstX)
    expect(cnc.xMax).toBeGreaterThanOrEqual(lastX)
  })

  it('is empty for an empty inventory', () => {
    expect(lanesFor([], 1, [0, 0])).toEqual([])
  })
})

describe('lineLabel', () => {
  it('renders the five lines with readable names', () => {
    expect(lineLabel('CNC_LINE')).toBe('CNC Line')
    expect(lineLabel('PACKAGING_LINE')).toBe('Packaging Line')
    expect(lineLabel('SOME_NEW_LINE')).toBe('SOME NEW LINE')
  })

  it('covers every line FactoryWorld can produce', () => {
    for (const line of LINE_ORDER) {
      expect(lineLabel(line)).not.toBe(line)
    }
  })
})
