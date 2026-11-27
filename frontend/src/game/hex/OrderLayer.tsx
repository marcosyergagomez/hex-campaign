import { useI18n } from "../../i18n/language"
import type { BoardClash, BoardTrace, OrderPath, Spot } from "./boardTypes"
import { hexCenter } from "./geometry"

export function OrderLayer({
  traces,
  orderPaths,
  size,
}: {
  traces: BoardTrace[]
  orderPaths: OrderPath[]
  size: number
}) {
  const pointsOf = (spots: Spot[]) => spots.map((spot) => {
    const center = hexCenter(spot.q, spot.r, size)
    return `${center.x},${center.y}`
  }).join(" ")
  return (
    <>
      {traces.map((trace, index) => {
        if (trace.spots.length === 0) return null
        const last = trace.spots[trace.spots.length - 1]
        const center = hexCenter(last.q, last.r, size)
        return (
          <g key={`trace-${index}`} className="hex-trace" style={{ color: trace.color }}>
            {trace.spots.length > 1 ? (
              <polyline
                fill="none"
                stroke="currentColor"
                strokeWidth={size * 0.1}
                points={pointsOf(trace.spots)}
              />
            ) : null}
            <circle cx={center.x} cy={center.y} r={size * 0.34} fill="none" stroke="currentColor" strokeWidth={size * 0.08} />
          </g>
        )
      })}
      {orderPaths.map((path, index) => {
        if (path.spots.length < 2) return null
        const entered = path.entered ?? path.spots.length - 1
        const reached = path.spots.slice(0, entered + 1)
        const owing = entered < path.spots.length - 1 ? path.spots.slice(entered) : []
        const selected = path.selected ? " is-selected" : ""
        const width = size * (path.selected ? 0.18 : 0.12)
        return (
          <g key={`order-${index}`}>
            {reached.length > 1 ? (
              <polyline className={`hex-order-path${selected}`} fill="none" strokeWidth={width} points={pointsOf(reached)} />
            ) : null}
            {owing.length > 1 ? (
              <polyline className={`hex-order-path is-owing${selected}`} fill="none" strokeWidth={width} points={pointsOf(owing)} />
            ) : null}
          </g>
        )
      })}
    </>
  )
}

export function ClashLayer({
  clashes,
  size,
}: {
  clashes: BoardClash[]
  size: number
}) {
  const { t } = useI18n()
  return (
    <>
      {clashes.map((clash, index) => {
        const left = hexCenter(clash.from.q, clash.from.r, size)
        const right = hexCenter(clash.to.q, clash.to.r, size)
        return (
          <CrossedSwords
            key={`clash-${index}`}
            x={(left.x + right.x) / 2}
            y={(left.y + right.y) / 2}
            size={size}
            label={t("battleSwords")}
          />
        )
      })}
    </>
  )
}

function CrossedSwords({
  x, y, size, label,
}: {
  x: number
  y: number
  size: number
  label: string
}) {
  const length = size * 0.72
  return (
    <g className="hex-clash" transform={`translate(${x} ${y})`} pointerEvents="none">
      <title>{label}</title>
      <g transform="rotate(-42)">
        <Sword length={length} />
      </g>
      <g transform="rotate(42)">
        <Sword length={length} />
      </g>
    </g>
  )
}

function Sword({ length }: { length: number }) {
  const blade = length * 0.58
  return (
    <g>
      <path className="hex-clash-blade" d={`M0 ${-blade} L${length * 0.07} ${length * 0.08} L${-length * 0.07} ${length * 0.08} Z`} />
      <rect className="hex-clash-guard" x={-length * 0.24} y={length * 0.06} width={length * 0.48} height={length * 0.07} rx={length * 0.02} />
      <rect className="hex-clash-grip" x={-length * 0.045} y={length * 0.13} width={length * 0.09} height={length * 0.2} />
      <circle className="hex-clash-pommel" cx={0} cy={length * 0.38} r={length * 0.07} />
    </g>
  )
}
