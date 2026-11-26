import { useCallback, useId, useMemo, useRef, useState } from "react"

import type { MapCell } from "../../api"
import { useI18n } from "../../i18n/language"
import { hexCenter, hexPoints } from "./geometry"
import { GROUND_LABEL } from "./grounds"
import { lakeOutlines, riverShapes, roadPaths, terrainOutlines, territoryOutlines } from "./courses"
import { ArtDefinitions, EARTH, Fields, noise, OrnamentArt, ornaments } from "./TerrainArt"
import "./board.css"

const SIZE = 28

type Spot = { q: number; r: number }

type OwnedCell = MapCell & { owner_id?: string | null }
type Placed = OwnedCell & { x: number; y: number }
export type TerritoryPlayer = { player_id: string; label: string; color: string }
const NO_PLAYERS: TerritoryPlayer[] = []
const NO_SPOTS: Spot[] = []

const SAMPLES = ["rio", "lago", "playa", "orilla", "pantano", "bosque", "montana", "desierto"]
const STEPS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]]

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
  players = NO_PLAYERS,
  unknown = NO_SPOTS,
  onCellClick,
}: {
  cells: OwnedCell[]
  anchors: Spot[]
  size?: number
  players?: TerritoryPlayer[]
  unknown?: Spot[]
  onCellClick?: (cell: OwnedCell) => void
}) {
  const { t } = useI18n()
  const [zoom, setZoom] = useState(1)
  const [grid, setGrid] = useState(true)
  const [showTerritories, setShowTerritories] = useState(true)
  const caption = useRef<HTMLParagraphElement>(null)
  function terrainName(cell: OwnedCell) {
    const owner = players.find(player => player.player_id === cell.owner_id)
    return [
      t(GROUND_LABEL[cell.ground] ?? "groundPlain"),
      ...(cell.road ? [t("mapRoad")] : []),
      ...(cell.bridge ? [t("mapBridge")] : []),
      ...(owner ? [t("territoryOwner", { player: owner.label })] : []),
    ].join(" · ")
  }
  const label = useRef<(cell: OwnedCell | null) => void>(() => {})
  label.current = (cell) => {
    const node = caption.current
    if (!node) {
      return
    }
    node.textContent = cell ? terrainName(cell) : ""
  }
  const onHover = useCallback((cell: OwnedCell | null) => {
    label.current(cell)
  }, [])
  const boardId = useId().replaceAll(":", "")
  const points = hexPoints(size)
  const placed = useMemo(
    () => cells.map((cell) => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })),
    [cells, size],
  )
  const hidden = useMemo(() => unknown.map(cell => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })), [unknown, size])
  const extent = useMemo(() => [...placed, ...hidden], [placed, hidden])
  const territories = useMemo(() => territoryOutlines(placed, size).flatMap(region => {
    const player = players.find(item => item.player_id === region.owner_id)
    return player?.color ? [{ ...region, player }] : []
  }), [placed, size, players])
  const forts = useMemo(
    () => new Set(anchors.map((spot) => `${spot.q},${spot.r}`)),
    [anchors],
  )
  const rivers = useMemo(() => riverShapes(placed, size), [placed, size])
  const roads = useMemo(() => roadPaths(placed, size, anchors), [placed, size, anchors])
  const lakes = useMemo(() => lakeOutlines(placed, size), [placed, size])
  const regions = useMemo(() => Object.entries(EARTH)
    .filter(([ground]) => !["llanura", "lago", "rio"].includes(ground))
    .map(([ground, color]) => ({ ground, color, path: terrainOutlines(placed, size, new Set([ground])).join(" ") })),
  [placed, size])
  const scenery = useMemo(() => placed.flatMap((cell) =>
    ["lago", "rio", "campo", "mina"].includes(cell.ground) || forts.has(`${cell.q},${cell.r}`)
      ? []
      : ornaments(cell).map((mark, index) => ({
        ...mark,
        key: `${cell.q},${cell.r}-${index}`,
        x: cell.x + mark.x * size / SIZE,
        y: cell.y + mark.y * size / SIZE,
      })),
  ).sort((left, right) => left.y - right.y || left.x - right.x), [placed, forts, size])
  const sceneryArt = useMemo(() => scenery.map((mark) => (
    <g key={mark.key} transform={`translate(${mark.x} ${mark.y}) scale(${mark.scale * size / SIZE})`}>
      <g transform={`scale(${mark.mirror} 1)`}><OrnamentArt mark={mark} id={boardId} /></g>
    </g>
  )), [scenery, boardId, size])
  if (extent.length === 0) {
    return null
  }
  const pad = size + 6
  const minX = Math.min(...extent.map((cell) => cell.x)) - pad
  const minY = Math.min(...extent.map((cell) => cell.y)) - pad
  const width = Math.max(...extent.map((cell) => cell.x)) - minX + pad
  const height = Math.max(...extent.map((cell) => cell.y)) - minY + pad

  return (
    <div className="hex-stage">
      {extent.length > 8 ? (
        <div className="hex-tools">
          <button type="button" onClick={() => setZoom((value) => Math.max(1, value - .5))} disabled={zoom === 1} aria-label={t("mapZoomOut")}>−</button>
          <button type="button" onClick={() => setZoom(1)} aria-label={t("mapFit")}>{Math.round(zoom * 100)}%</button>
          <button type="button" onClick={() => setZoom((value) => Math.min(3, value + .5))} disabled={zoom === 3} aria-label={t("mapZoomIn")}>+</button>
          <button type="button" onClick={() => setGrid((value) => !value)} aria-pressed={grid}>{t("mapGrid")}</button>
          {territories.length > 0 ? (
            <button type="button" onClick={() => setShowTerritories(value => !value)} aria-pressed={showTerritories}>
              {t("territoryToggle")}
            </button>
          ) : null}
        </div>
      ) : null}
      <div className={extent.length > 8 ? "hex-viewport" : undefined} tabIndex={extent.length > 8 ? 0 : undefined} role="group" aria-label={t("mapsTitle")}>
      <svg
        className="hex-board"
        style={{ width: `${zoom * 100}%` }}
        viewBox={`${minX} ${minY} ${width} ${height}`}
        role="img"
        aria-label={t("mapsTitle")}
      >
        <ArtDefinitions id={boardId} size={size} />
        <defs>
          {territories.map((region, index) => (
            <clipPath key={region.owner_id} id={`${boardId}-territory-${index}`}>
              <path d={region.clip} clipRule="evenodd" />
            </clipPath>
          ))}
          <clipPath id={`${boardId}-outline`}>
            {placed.map((cell) => (
              <polygon key={`${cell.q},${cell.r}`} points={points} transform={`translate(${cell.x} ${cell.y})`} />
            ))}
          </clipPath>
          <clipPath id={`${boardId}-water-clip`}>
            <path d={lakes.join(" ")} clipRule="evenodd" />
            {rivers.map((river, index) => <path key={index} d={river.channel} />)}
          </clipPath>
        </defs>
        <g className="hex-fog">
          {hidden.map(cell => (
            <polygon key={`${cell.q},${cell.r}`} points={points} transform={`translate(${cell.x} ${cell.y})`}>
              <title>{t("unknownTerrain")}</title>
            </polygon>
          ))}
        </g>
        <g clipPath={`url(#${boardId}-outline)`} className="hex-ink">
          <rect x={minX} y={minY} width={width} height={height} fill={EARTH.llanura} />
          <g filter={`url(#${boardId}-blend)`}>
            {regions.map((region) => <path key={region.ground} d={region.path} fill={region.color} fillRule="evenodd" />)}
          </g>
          <g filter={`url(#${boardId}-blend)`}>
            {placed.map((cell) => (
              <g key={`${cell.q},${cell.r}`} transform={`translate(${cell.x} ${cell.y})`}>
                <ellipse rx={size * 1.3} ry={size * .7} fill={noise(cell.q, cell.r, 17) > .5 ? "#8b8a56" : "#ebd9a8"} opacity=".13"
                  transform={`rotate(${noise(cell.q, cell.r, 18) * 180})`} />
              </g>
            ))}
          </g>
          <rect x={minX} y={minY} width={width} height={height} fill={`url(#${boardId}-paper)`} />
          <g fill="#8d9567" stroke="#8d9567" strokeWidth={size * .35} filter={`url(#${boardId}-blend)`}>
            <path d={lakes.join(" ")} fillRule="evenodd" />
            {rivers.map((river, index) => <path key={index} d={river.banks} />)}
          </g>
          <g fill="#b5aa7f" stroke="#756f4c" strokeWidth={size * .045}>
            <path d={lakes.join(" ")} fillRule="evenodd" strokeWidth={size * .14} />
            {rivers.map((river, index) => <path key={index} d={river.banks} />)}
          </g>
          <g clipPath={`url(#${boardId}-water-clip)`}>
            <rect x={minX} y={minY} width={width} height={height} fill={`url(#${boardId}-water)`} />
            {rivers.map((river, index) => <path key={index} d={river.current} fill="#599196" opacity=".18" filter={`url(#${boardId}-blend)`} />)}
            <rect x={minX} y={minY} width={width} height={height} fill={`url(#${boardId}-ripples)`} />
          </g>
          {showTerritories ? territories.map((region, index) => (
            <g key={region.owner_id} className="hex-territory" clipPath={`url(#${boardId}-territory-${index})`}>
              <path d={region.outline} fill={region.player.color} fillRule="evenodd" opacity=".19" />
              <path d={region.outline} fill="none" stroke={region.player.color} strokeWidth={size * .24} opacity=".13" />
              <path d={region.outline} fill="none" stroke={region.player.color} strokeWidth={size * .055} opacity=".8" />
            </g>
          )) : null}
          <g filter={cells.length <= 547 ? `url(#${boardId}-grain)` : undefined}>
            {sceneryArt}
          </g>
          {placed.filter((cell) => cell.ground === "rio").map((cell) => (
            <g key={`stones-${cell.q},${cell.r}`} transform={`translate(${cell.x} ${cell.y}) scale(${size / SIZE})`} opacity=".55">
              <ellipse cx="11" cy="8" rx="1.5" ry=".8" fill="#c4c4a7" />
              <ellipse cx="-10" cy="-11" rx="1" ry=".6" fill="#d1c7a1" />
            </g>
          ))}
          <g className="hex-roads" fill="none" strokeLinecap="round" strokeLinejoin="round">
            <path d={roads.join(" ")} stroke="#696147" strokeWidth={size * .14} opacity=".8" />
            <path d={roads.join(" ")} stroke="#d0b982" strokeWidth={size * .075} />
            <path d={roads.join(" ")} stroke="#ede0b2" strokeWidth={size * .018} opacity=".7" />
          </g>
          {placed.map((cell) => (
            <g key={`${cell.q},${cell.r}`} transform={`translate(${cell.x} ${cell.y}) scale(${size / SIZE})`}>
              {cell.ground === "campo" ? <Fields /> : null}
              {cell.ground === "mina" ? <use href={`#${boardId}-mine`} x="-17" y="-20" width="34" height="26" /> : null}
              {cell.bridge ? <Bridge cell={cell} cells={placed} /> : null}
              {forts.has(`${cell.q},${cell.r}`) ? <use href={`#${boardId}-keep`} x="-20" y="-29" width="40" height="38" /> : null}
              {forts.has(`${cell.q},${cell.r}`) && players.some(player => player.player_id === cell.owner_id && player.color) ? (
                <g className="hex-banner">
                  <path d="M9-18V-36" stroke="#504832" strokeWidth="1.2" />
                  <path d="M9-36L22-33L9-29Z" fill={players.find(player => player.player_id === cell.owner_id)?.color} stroke="#eee0b7" strokeWidth=".55" />
                </g>
              ) : null}
            </g>
          ))}
        </g>
        <g className={grid ? undefined : "hex-grid-hidden"}>
          {placed.map((cell) => (
            <polygon
              key={`${cell.q},${cell.r}`}
              points={points}
              transform={`translate(${cell.x} ${cell.y})`}
              className={`hex-edge${forts.has(`${cell.q},${cell.r}`) ? " is-fort" : ""}${onCellClick ? " is-pick" : ""}`}
              style={{ strokeWidth: size / SIZE * (forts.has(`${cell.q},${cell.r}`) ? 1.6 : .45) }}
              onMouseEnter={() => onHover(cell)}
              onMouseLeave={() => onHover(null)}
              onClick={onCellClick ? () => onCellClick(cell) : undefined}
            >
              <title>{terrainName(cell)}</title>
            </polygon>
          ))}
        </g>
      </svg>
      </div>
      <p ref={caption} className="hex-caption" />
    </div>
  )
}

function Bridge({ cell, cells }: { cell: Placed; cells: Placed[] }) {
  // Span bank to bank: opposite dry neighbours, never along the channel.
  const banks = STEPS.map(([q, r], index) => {
    const other = cells.find((spot) => spot.q === cell.q + q && spot.r === cell.r + r)
    if (!other || other.ground === "rio" || other.ground === "lago") return null
    return { index, other }
  }).filter((item): item is { index: number; other: Placed } => item !== null)
  let start = banks[0]?.other
  let end: Placed | undefined
  for (const left of banks) {
    const right = banks.find((item) => item.index === (left.index + 3) % 6)
    if (right) {
      start = left.other
      end = right.other
      break
    }
  }
  if (!end && banks.length >= 2) {
    let best = 0
    for (const left of banks) {
      for (const right of banks) {
        const gap = Math.min((right.index - left.index + 6) % 6, (left.index - right.index + 6) % 6)
        if (gap > best) {
          best = gap
          start = left.other
          end = right.other
        }
      }
    }
  }
  const angle = start && end
    ? Math.atan2(end.y - start.y, end.x - start.x) * 180 / Math.PI
    : 0
  return (
    <g className="hex-bridge" transform={`rotate(${angle})`}>
      <rect x="-18" y="-4" width="36" height="10" rx="1" fill="#343d32" opacity=".35" />
      <rect x="-18" y="-5" width="36" height="8" rx="1" fill="#b19a6b" stroke="#5e513b" />
      {[-12, -6, 0, 6, 12].map((x) => <path key={x} d={`M${x}-5V3`} stroke="#786447" strokeWidth=".8" />)}
      <path d="M-19-6H19M-19 4H19" stroke="#ddcba0" strokeWidth="1.5" />
    </g>
  )
}
