import { useState } from "react"

import type { MapCell } from "../../api"
import { useI18n } from "../../i18n/language"
import { hexCenter, hexPoints } from "./geometry"
import { GROUND_LABEL } from "./grounds"
import "./board.css"

const SIZE = 28

type Spot = { q: number; r: number }

type Placed = MapCell & { x: number; y: number }

export function HexBoard({ cells, anchors }: { cells: MapCell[]; anchors: Spot[] }) {
  const { t } = useI18n()
  const [hover, setHover] = useState<string | null>(null)
  const points = hexPoints(SIZE)
  const placed = cells.map((cell) => ({ ...cell, ...hexCenter(cell.q, cell.r, SIZE) }))
  if (placed.length === 0) {
    return null
  }
  const pad = SIZE + 6
  const minX = Math.min(...placed.map((cell) => cell.x)) - pad
  const minY = Math.min(...placed.map((cell) => cell.y)) - pad
  const width = Math.max(...placed.map((cell) => cell.x)) - minX + pad
  const height = Math.max(...placed.map((cell) => cell.y)) - minY + pad
  const forts = new Set(anchors.map((spot) => `${spot.q},${spot.r}`))
  const labelKey = hover ? GROUND_LABEL[hover] : undefined

  return (
    <div className="hex-stage">
      <svg
        className="hex-board"
        viewBox={`${minX} ${minY} ${width} ${height}`}
        role="img"
        aria-label={t("mapsTitle")}
      >
        {placed.map((cell) => (
          <HexTile
            key={`${cell.q},${cell.r}`}
            cell={cell}
            points={points}
            fort={forts.has(`${cell.q},${cell.r}`)}
            onHover={setHover}
          />
        ))}
      </svg>
      <p className="hex-caption">{labelKey ? t(labelKey) : ""}</p>
    </div>
  )
}

function HexTile({
  cell,
  points,
  fort,
  onHover,
}: {
  cell: Placed
  points: string
  fort: boolean
  onHover: (ground: string | null) => void
}) {
  const clip = `hex-${cell.q}-${cell.r}`
  return (
    <g
      transform={`translate(${cell.x} ${cell.y})`}
      onMouseEnter={() => onHover(cell.ground)}
      onMouseLeave={() => onHover(null)}
    >
      <clipPath id={clip}>
        <polygon points={points} />
      </clipPath>
      <g clipPath={`url(#${clip})`}>
        <polygon points={points} className={`hex-fill hex-${cell.ground}${fort ? " is-fort" : ""}`} />
        <Face ground={cell.ground} seed={cell.q * 3 + cell.r} />
      </g>
      <polygon points={points} className={`hex-fill${fort ? " is-fort" : ""}`} fill="none" />
      {fort ? <Fortress /> : null}
    </g>
  )
}

function Face({ ground, seed }: { ground: string; seed: number }) {
  if (ground === "colina") {
    return <path className="hex-ridge" d="M -12 4 Q 0 -6 12 5" />
  }
  if (ground === "bosque" || ground === "bosque_profundo") {
    return <Trees deep={ground === "bosque_profundo"} />
  }
  if (ground === "montana" || ground === "montana_rocosa") {
    return <path className="hex-peak" d="M -10 8 L -2 -8 L 4 8 M 0 8 L 8 -4 L 14 8" />
  }
  if (ground === "desierto") {
    return <path className="hex-dune" d="M -14 2 Q -4 -4 6 2 T 16 1" />
  }
  if (ground === "campo") {
    return <path className="hex-furrow" d="M -12 -4 H 12 M -12 2 H 12 M -12 8 H 12" />
  }
  if (ground === "rio" || ground === "lago" || ground === "orilla") {
    return <Current seed={seed} lake={ground === "lago"} />
  }
  if (ground === "playa") {
    return <path className="hex-foam" d="M -16 8 Q 0 2 16 8" />
  }
  if (ground === "pantano") {
    return <Bubbles seed={seed} />
  }
  if (ground === "acantilado") {
    return <path className="hex-peak" d="M -14 10 H 14 M -8 4 H 10 M -2 -2 H 8" />
  }
  return null
}

function Trees({ deep }: { deep: boolean }) {
  const spots = deep
    ? [[-8, 2], [0, 6], [8, 1], [-3, -6], [6, -5]]
    : [[-6, 4], [5, 5], [0, -3]]
  return spots.map(([x, y], index) => (
    <path
      key={`${x},${y}`}
      className="hex-tree"
      style={{ animationDelay: `${index * 0.35}s` }}
      d={`M ${x - 3} ${y + 5} H ${x + 3} L ${x} ${y - 6} Z`}
    />
  ))
}

function Current({ seed, lake }: { seed: number; lake: boolean }) {
  const turn = (Math.abs(seed) % 3) * 60
  return (
    <g transform={`rotate(${turn})`}>
      <path className="hex-current" d="M -16 0 H 16" />
      <path className="hex-current hex-current-slow" d={lake ? "M -16 6 H 16 M -16 -6 H 16" : "M -16 5 H 16"} />
    </g>
  )
}

function Bubbles({ seed }: { seed: number }) {
  const spots = [
    [-6, 2],
    [4, -2],
    [0, 6],
  ]
  return spots.map(([x, y], index) => (
    <circle
      key={`${x},${y}`}
      className="hex-bubble"
      cx={x + (seed % 2)}
      cy={y}
      r={1.3}
      style={{ animationDelay: `${index * 0.8}s` }}
    />
  ))
}

function Fortress() {
  return <path className="hex-fort" d="M -3 6 H 3 L 2 -2 H 5 L 0 -10 L -5 -2 H -2 Z" />
}
