import { memo, useCallback, useId, useMemo, useRef } from "react"

import type { MapCell } from "../../api"
import { useI18n } from "../../i18n/language"
import { hexCenter, hexPoints } from "./geometry"
import { GROUND_ART, GROUND_LABEL, isWater } from "./grounds"
import "./board.css"

const SIZE = 28

type Spot = { q: number; r: number }

type Placed = MapCell & { x: number; y: number }

const SAMPLES = ["rio", "lago", "playa", "orilla", "pantano", "bosque", "montana", "desierto"]

export function HexStrip() {
  const cells = SAMPLES.map((ground, index) => ({
    q: index,
    r: 0,
    ground,
    road: false,
    bridge: false,
  }))
  return <HexBoard cells={cells} anchors={[]} />
}

export function HexBoard({
  cells,
  anchors,
  size = SIZE,
}: {
  cells: MapCell[]
  anchors: Spot[]
  size?: number
}) {
  const { t } = useI18n()
  const caption = useRef<HTMLParagraphElement>(null)
  const label = useRef<(ground: string | null) => void>(() => {})
  label.current = (ground) => {
    const node = caption.current
    if (!node) {
      return
    }
    const key = ground ? GROUND_LABEL[ground] : undefined
    node.textContent = key ? t(key) : ""
  }
  const onHover = useCallback((ground: string | null) => {
    label.current(ground)
  }, [])
  const boardId = useId().replaceAll(":", "")
  const points = hexPoints(size)
  const placed = useMemo(
    () => cells.map((cell) => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })),
    [cells, size],
  )
  const forts = useMemo(
    () => new Set(anchors.map((spot) => `${spot.q},${spot.r}`)),
    [anchors],
  )
  if (placed.length === 0) {
    return null
  }
  const pad = size + 6
  const minX = Math.min(...placed.map((cell) => cell.x)) - pad
  const minY = Math.min(...placed.map((cell) => cell.y)) - pad
  const width = Math.max(...placed.map((cell) => cell.x)) - minX + pad
  const height = Math.max(...placed.map((cell) => cell.y)) - minY + pad

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
            clipId={`${boardId}-${cell.q}-${cell.r}`}
            onHover={onHover}
          />
        ))}
      </svg>
      <p ref={caption} className="hex-caption" />
    </div>
  )
}

const HexTile = memo(function HexTile({
  cell,
  points,
  fort,
  clipId,
  onHover,
}: {
  cell: Placed
  points: string
  fort: boolean
  clipId: string
  onHover: (ground: string | null) => void
}) {
  const span = SIZE * 5
  const driftX = ((Math.abs(cell.q * 37 + cell.r * 17) % 70) - 35)
  const driftY = ((Math.abs(cell.q * 11 + cell.r * 41) % 70) - 35)
  return (
    <g
      transform={`translate(${cell.x} ${cell.y})`}
      onMouseEnter={() => onHover(cell.ground)}
      onMouseLeave={() => onHover(null)}
    >
      <clipPath id={clipId}>
        <polygon points={points} />
      </clipPath>
      <g clipPath={`url(#${clipId})`}>
        <image
          href={GROUND_ART[cell.ground] ?? GROUND_ART.llanura}
          x={-span / 2 + driftX}
          y={-span / 2 + driftY}
          width={span}
          height={span}
          preserveAspectRatio="xMidYMid slice"
        />
        {isWater(cell.ground) ? <rect className="hex-sheen" x={-SIZE} y={-SIZE} width={SIZE * 2} height={SIZE * 2} /> : null}
      </g>
      <polygon points={points} className={`hex-edge${fort ? " is-fort" : ""}`} />
      {fort ? (
        <>
          <clipPath id={`${clipId}-keep`}>
            <circle r="11" />
          </clipPath>
          <image
            className="hex-keep"
            href="/terrain/fortaleza.jpg"
            x={-12}
            y={-12}
            width={24}
            height={24}
            clipPath={`url(#${clipId}-keep)`}
          />
        </>
      ) : null}
    </g>
  )
})
