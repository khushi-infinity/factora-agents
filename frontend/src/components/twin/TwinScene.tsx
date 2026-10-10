import { useMemo, useRef, useState } from 'react'
import type { ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'

import {
  STATE_COLORS,
  STATE_LABELS,
  floorTransform,
  footprintFor,
  geometryForType,
  lanesFor,
  type Lane,
  type MachineState,
} from '../../lib/twin'
import type { TwinMachine } from '../../lib/factory'

const EXTENT = 110 // scene metres the factory floor is normalised into

interface SceneProps {
  machines: TwinMachine[]
  selectedId: string | null
  changedIds: Set<string> // machines whose state changed in the last refresh
  filterLine: string | null // active line rail selection (dims the rest)
  onSelect: (machineId: string) => void
  cameraKey: number // bump to reset camera
}

function MachineMesh({
  machine,
  scale,
  offset,
  footprint,
  selected,
  changed,
  dimmed,
  onSelect,
}: {
  machine: TwinMachine
  scale: number
  offset: [number, number]
  footprint: number
  selected: boolean
  changed: boolean
  dimmed: boolean
  onSelect: (id: string) => void
}) {
  const mesh = useRef<Mesh>(null)
  const [hovered, setHovered] = useState(false)
  const state = machine.state as MachineState
  const color = STATE_COLORS[state] ?? STATE_COLORS.OFFLINE

  // Placement: FactoryWorld metres → scene coordinates (centred).
  const x = (machine.x_m - offset[0]) * scale
  const z = (machine.y_m - offset[1]) * scale
  const geometryKind = geometryForType(machine.machine_type)
  const pulseRef = useRef(0)

  useFrame((_, delta) => {
    if (!mesh.current) return
    const target = selected ? 1.06 : hovered ? 1.1 : 1
    if (changed) {
      // One-shot professional pulse on a state change: rises, settles, stops.
      pulseRef.current = Math.min(1, pulseRef.current + delta * 1.6)
      const pulse = Math.sin(pulseRef.current * Math.PI) * 0.18
      mesh.current.scale.setScalar(target + pulse)
    } else {
      pulseRef.current = 0
      mesh.current.scale.setScalar(target)
    }
  })

  const handlePointerOver = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation()
    setHovered(true)
    document.body.style.cursor = 'pointer'
  }
  const handlePointerOut = () => {
    setHovered(false)
    document.body.style.cursor = 'auto'
  }

  const labelY = geometryKind === 'press' ? footprint * 0.7 + 2 : footprint * 0.95 + 2.4

  return (
    <group position={[x, 0, z]}>
      <mesh
        ref={mesh}
        castShadow
        visible={!dimmed}
        onClick={(event) => {
          event.stopPropagation()
          onSelect(machine.machine_id)
        }}
        onPointerOver={handlePointerOver}
        onPointerOut={handlePointerOut}
      >
        <boxGeometry
          args={[
            geometryKind === 'press' ? footprint * 0.7 : footprint,
            geometryKind === 'press' ? 4.5 : footprint * 0.85,
            geometryKind === 'mill' ? footprint * 1.25 : footprint,
          ]}
        />
        <meshStandardMaterial
          color={selected ? '#1d4ed8' : color}
          emissive={color}
          emissiveIntensity={changed ? 0.55 : hovered ? 0.25 : 0.08}
          roughness={0.55}
          metalness={0.25}
        />
      </mesh>
      {/* machine plinth — grounds every unit visually */}
      <mesh position={[0, 0.05, 0]} receiveShadow visible={!dimmed}>
        <boxGeometry args={[footprint * 1.22, 0.3, footprint * 1.22]} />
        <meshStandardMaterial color="#1f2937" roughness={0.9} />
      </mesh>
      {/* selection marker: static, unmistakable, no perpetual animation */}
      {selected && (
        <mesh position={[0, 0.09, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[footprint * 0.78, footprint * 0.98, 40]} />
          <meshBasicMaterial color="#2563eb" />
        </mesh>
      )}
      {!dimmed && (
        <Html
          center
          distanceFactor={90}
          position={[0, labelY, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div
            className={`whitespace-nowrap rounded px-1.5 py-0.5 font-mono text-[10px] font-medium shadow ${
              selected ? 'bg-blue-600 text-white' : 'bg-white/90 text-slate-800'
            }`}
          >
            {machine.machine_id}
          </div>
        </Html>
      )}
      {!dimmed && machine.state === 'CRITICAL' && (
        <Html center distanceFactor={120} position={[0, labelY + 7, 0]} style={{ pointerEvents: 'none' }}>
          <div className="rounded-full bg-red-600 px-1.5 py-0.5 text-[9px] font-bold text-white shadow">
            ⚠ CRITICAL
          </div>
        </Html>
      )}
      {!dimmed && hovered && (
        <Html center distanceFactor={110} position={[0, labelY + 14, 0]} style={{ pointerEvents: 'none' }}>
          <div className="whitespace-nowrap rounded bg-slate-900/90 px-2 py-1 text-[10px] text-white shadow-lg">
            {machine.machine_id} · {STATE_LABELS[state]} · health {machine.health_score ?? '—'}
          </div>
        </Html>
      )}
    </group>
  )
}

function FloorLanes({ lanes, footprint }: { lanes: Lane[]; footprint: number }) {
  const depth = footprint * 2.3
  return (
    <group>
      {lanes.map((lane) => (
        <mesh
          key={lane.line}
          position={[(lane.xMin + lane.xMax) / 2, 0.02, lane.z]}
          receiveShadow
        >
          <boxGeometry args={[lane.xMax - lane.xMin, 0.08, depth]} />
          <meshStandardMaterial color={lane.color} roughness={0.95} />
        </mesh>
      ))}
      {lanes.map((lane) => (
        <Html
          key={`label-${lane.line}`}
          center
          distanceFactor={120}
          position={[lane.xMin + 14, 0.6, lane.z - depth / 2 - 3]}
          style={{ pointerEvents: 'none' }}
        >
          <div className="whitespace-nowrap font-mono text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
            {lane.label}
          </div>
        </Html>
      ))}
    </group>
  )
}

export default function TwinScene({
  machines,
  selectedId,
  changedIds,
  filterLine,
  onSelect,
  cameraKey,
}: SceneProps) {
  const { scale, offset } = useMemo(() => floorTransform(machines, EXTENT), [machines])
  const footprint = useMemo(() => footprintFor(machines, scale), [machines, scale])
  const lanes = useMemo(
    () => lanesFor(machines, scale, offset, footprint),
    [machines, scale, offset, footprint],
  )

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [55, 105, 125], fov: 40 }}
      key={cameraKey}
    >
      <color attach="background" args={['#eef2f7']} />
      <ambientLight intensity={0.75} />
      <directionalLight
        position={[70, 120, 50]}
        intensity={1.15}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      {/* factory ground */}
      <mesh
        position={[0, 0, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
        onClick={() => onSelect('')} // clicking the floor clears selection
      >
        <planeGeometry args={[EXTENT * 1.7, EXTENT * 1.7]} />
        <meshStandardMaterial color="#e2e8f0" roughness={0.98} />
      </mesh>
      <gridHelper args={[EXTENT * 1.6, 24, '#cbd5e1', '#dbe3ec']} position={[0, 0.01, 0]} />
      <FloorLanes lanes={lanes} footprint={footprint} />
      {machines.map((machine) => (
        <MachineMesh
          key={machine.machine_id}
          machine={machine}
          scale={scale}
          offset={offset}
          footprint={footprint}
          selected={machine.machine_id === selectedId}
          changed={changedIds.has(machine.machine_id)}
          dimmed={filterLine !== null && machine.line !== filterLine}
          onSelect={onSelect}
        />
      ))}
      <OrbitControls
        maxPolarAngle={Math.PI / 2.4}
        minDistance={40}
        maxDistance={300}
        target={[0, 0, 0]}
        enablePan
      />
    </Canvas>
  )
}
