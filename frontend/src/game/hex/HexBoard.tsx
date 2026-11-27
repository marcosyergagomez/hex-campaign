import { memo, useCallback, useDeferredValue, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type PointerEvent, type ReactNode } from "react"

import type { MapCell } from "../../api"
import { useI18n } from "../../i18n/language"
import { axialFromPixel, hexCenter, hexPoints } from "./geometry"
import { HOP_MS, type MarchPath } from "./useMarchFilm"
import { GROUND_LABEL, GROUND_TIP, GROUND_TIP_ON_ROAD } from "./grounds"
import { lakeOutlines, riverShapes, roadPaths, terrainOutlines, territoryOutlines, type RiverShape } from "./courses"
import { ArtDefinitions, EARTH, Fields, noise, OrnamentArt, ornaments } from "./TerrainArt"
import { TokenDefinitions, UnitToken, type UnitKind } from "./tokens"
import { useHexPaint } from "./useHexPaint"
import "./board.css"

const SIZE = 28
const ZOOMS = [0.5, 0.75, 1, 1.5, 2, 2.5, 3]

function markTint(color: string, alpha: number): string {
  const hex = color.trim().replace("#", "")
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return color
  const r = Number.parseInt(hex.slice(0, 2), 16)
  const g = Number.parseInt(hex.slice(2, 4), 16)
  const b = Number.parseInt(hex.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function adjacentZoom(current: number, direction: -1 | 1): number {
  const index = ZOOMS.findIndex((step) => step >= current - 0.001)
  const at = index === -1 ? ZOOMS.length - 1 : index
  return ZOOMS[Math.min(ZOOMS.length - 1, Math.max(0, at + direction))]
}

function measure(cells: { x: number; y: number }[], pad: number) {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const cell of cells) {
    if (cell.x < minX) minX = cell.x
    if (cell.y < minY) minY = cell.y
    if (cell.x > maxX) maxX = cell.x
    if (cell.y > maxY) maxY = cell.y
  }
  if (!Number.isFinite(minX)) return null
  return {
    minX: minX - pad,
    minY: minY - pad,
    width: maxX - minX + pad * 2,
    height: maxY - minY + pad * 2,
  }
}

type Spot = { q: number; r: number }

type OwnedCell = MapCell & { owner_id?: string | null }
type Placed = OwnedCell & { x: number; y: number }
export type TerritoryPlayer = { player_id: string; label: string; color: string }
export type BoardToken = {
  id: string
  q: number
  r: number
  kind: UnitKind
  faction: string
  color: string
  label: string
  mark?: number
  attention?: boolean
}
const NO_PLAYERS: TerritoryPlayer[] = []
const NO_SPOTS: Spot[] = []
const NO_TOKENS: BoardToken[] = []
const NO_PATHS: { spots: Spot[]; selected?: boolean }[] = []
const NO_TRACES: { spots: Spot[]; color: string }[] = []
const NO_CLASHES: { from: Spot; to: Spot }[] = []

const SAMPLES = ["rio", "lago", "playa", "pantano", "bosque", "montana", "desierto"]
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
  dimmed = NO_SPOTS,
  traces = NO_TRACES,
  clashes = NO_CLASHES,
  ghosts = NO_SPOTS,
  tokens = NO_TOKENS,
  tokensQuiet = false,
  marks = NO_SPOTS,
  markColor,
  tokenNotes,
  onCellClick,
  onPaint,
  orderPaths = NO_PATHS,
  tokenSpots,
  march = null,
  movableIds,
  selectedTokenId,
  focusSpot = null,
  spotlightId = null,
  mapTools = true,
  onOrderToken,
  onTokenOpen,
  onTokenInspect,
  onTokenDrop,
  spotAtRef,
}: {
  cells: OwnedCell[]
  anchors: Spot[]
  size?: number
  players?: TerritoryPlayer[]
  unknown?: Spot[]
  dimmed?: Spot[]
  traces?: { spots: Spot[]; color: string }[]
  clashes?: { from: Spot; to: Spot }[]
  ghosts?: Spot[]
  tokens?: BoardToken[]
  tokensQuiet?: boolean
  marks?: Spot[]
  markColor?: string
  tokenNotes?: Record<string, string>
  onCellClick?: (cell: OwnedCell) => void
  onPaint?: (cells: Array<OwnedCell | Spot>) => void
  orderPaths?: { spots: Spot[]; selected?: boolean; entered?: number }[]
  tokenSpots?: Record<string, Spot> | null
  /** Resolved march. Tokens glide along these hexes without redrawing the board. */
  march?: MarchPath[] | null
  movableIds?: ReadonlySet<string>
  selectedTokenId?: string | null
  /** Scroll the board so this hex sits in the middle. `n` repeats the same hex. */
  focusSpot?: { q: number; r: number; n: number } | null
  spotlightId?: string | null
  mapTools?: boolean
  onOrderToken?: (id: string, spot: Spot, phase: "down" | "move") => void
  onTokenOpen?: (id: string) => void
  onTokenInspect?: (id: string) => void
  onTokenDrop?: (id: string, spot: Spot) => void
  spotAtRef?: { current: ((clientX: number, clientY: number) => Spot | null) | null }
}) {
  const { t } = useI18n()
  const [zoom, setZoom] = useState(1)
  const [grid, setGrid] = useState(mapTools)
  const [showTerritories, setShowTerritories] = useState(mapTools)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragToken = useRef<string | null>(null)
  const tokenPress = useRef<{ id: string; x: number; y: number; armed: boolean } | null>(null)
  const tokenTap = useRef<{ id: string; at: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  const viewportRef = useRef<HTMLDivElement>(null)
  const byKey = useRef(new Map<string, OwnedCell | Spot>())
  const sizeRef = useRef(size)
  sizeRef.current = size
  function hexFromEvent(event: PointerEvent<SVGElement>): Spot | null {
    const svg = svgRef.current
    if (!svg) return null
    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY
    const matrix = svg.getScreenCTM()
    if (!matrix) return null
    const local = point.matrixTransform(matrix.inverse())
    return axialFromPixel(local.x, local.y, size)
  }
  useEffect(() => {
    if (!spotAtRef) return
    spotAtRef.current = (clientX, clientY) => {
      const svg = svgRef.current
      if (!svg) return null
      const rect = svg.getBoundingClientRect()
      if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) {
        return null
      }
      const point = svg.createSVGPoint()
      point.x = clientX
      point.y = clientY
      const matrix = svg.getScreenCTM()
      if (!matrix) return null
      const local = point.matrixTransform(matrix.inverse())
      return axialFromPixel(local.x, local.y, sizeRef.current)
    }
    return () => {
      spotAtRef.current = null
    }
  }, [spotAtRef])
  const { beginPaint } = useHexPaint(onPaint, svgRef, byKey, sizeRef)
  const caption = useRef<HTMLParagraphElement>(null)
  const playersById = useMemo(
    () => new Map(players.map(player => [player.player_id, player])),
    [players],
  )
  function terrainName(cell: OwnedCell) {
    const owner = cell.owner_id ? playersById.get(cell.owner_id) : undefined
    return [
      t(GROUND_LABEL[cell.ground] ?? "groundPlain"),
      ...(cell.road ? [t("mapRoad")] : []),
      ...(cell.bridge ? [t("mapBridge")] : []),
      ...(owner ? [t("territoryOwner", { player: owner.label })] : []),
    ].join(" · ")
  }
  function terrainEffect(cell: OwnedCell) {
    if (cell.road || cell.bridge) {
      return t(GROUND_TIP_ON_ROAD[cell.ground] ?? "groundTipRoadClear")
    }
    return t(GROUND_TIP[cell.ground] ?? "groundTipPlain")
  }
  const label = useRef<(cell: OwnedCell | null) => void>(() => {})
  label.current = (cell) => {
    const node = caption.current
    if (!node) {
      return
    }
    if (!cell) {
      node.replaceChildren()
      return
    }
    const title = document.createElement("span")
    title.className = "hex-caption-title"
    title.textContent = terrainName(cell)
    const tip = document.createElement("span")
    tip.className = "hex-caption-tip"
    tip.textContent = terrainEffect(cell)
    node.replaceChildren(title, tip)
  }
  const showTokenNote = useRef<(token: BoardToken | null) => void>(() => {})
  showTokenNote.current = (token) => {
    const node = caption.current
    if (!node) return
    const note = token ? tokenNotes?.[token.id] : undefined
    if (!token || !note) {
      node.replaceChildren()
      return
    }
    const title = document.createElement("span")
    title.className = "hex-caption-title"
    title.textContent = token.label
    const tip = document.createElement("span")
    tip.className = "hex-caption-tip"
    tip.textContent = note
    node.replaceChildren(title, tip)
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
  const shaded = useMemo(() => dimmed.map(cell => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })), [dimmed, size])
  const ghosted = useMemo(
    () => ghosts.map(cell => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })),
    [ghosts, size],
  )
  const extent = useMemo(() => [...placed, ...hidden, ...ghosted], [placed, hidden, ghosted])
  byKey.current = new Map(
    [...cells, ...ghosts].map(cell => [`${cell.q},${cell.r}`, cell]),
  )
  // Art can lag behind the stroke so pointer sampling stays responsive.
  const artCells = useDeferredValue(cells)
  // Ground art stays put when only a road flag changes. Road strokes use the other key.
  const groundKey = artCells.map(cell => `${cell.q},${cell.r},${cell.ground},${cell.owner_id ?? ""}`).join(";")
  const roadKey = artCells.map(cell => `${cell.q},${cell.r},${cell.road ? 1 : 0},${cell.bridge ? 1 : 0}`).join(";")
  const groundPlaced = useMemo(
    () => artCells.map(cell => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })),
    [groundKey, size],
  )
  const roadPlaced = useMemo(
    () => artCells.map(cell => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })),
    [roadKey, size],
  )
  const centeredZoom = useRef<number | null>(null)
  useEffect(() => {
    const viewport = viewportRef.current
    const board = svgRef.current
    if (!viewport || !board || centeredZoom.current === zoom) return
    const center = () => {
      if (board.scrollWidth === 0) return
      centeredZoom.current = zoom
      viewport.scrollLeft = Math.max(0, (board.scrollWidth - viewport.clientWidth) / 2)
      viewport.scrollTop = Math.max(0, (board.scrollHeight - viewport.clientHeight) / 2)
    }
    center()
    const frame = requestAnimationFrame(center)
    return () => cancelAnimationFrame(frame)
  }, [zoom, extent.length])
  useLayoutEffect(() => {
    if (!focusSpot) return
    const viewport = viewportRef.current
    const svg = svgRef.current
    if (!viewport || !svg) return
    const local = hexCenter(focusSpot.q, focusSpot.r, sizeRef.current)
    const point = svg.createSVGPoint()
    point.x = local.x
    point.y = local.y
    const matrix = svg.getScreenCTM()
    if (!matrix) return
    const screen = point.matrixTransform(matrix)
    const box = viewport.getBoundingClientRect()
    viewport.scrollTo({
      left: Math.max(0, viewport.scrollLeft + screen.x - box.left - box.width / 2),
      top: Math.max(0, viewport.scrollTop + screen.y - box.top - box.height / 2),
      behavior: "smooth",
    })
  }, [focusSpot])
  const territories = useMemo(() => territoryOutlines(groundPlaced, size).flatMap(region => {
    const player = players.find(item => item.player_id === region.owner_id)
    return player?.color ? [{ ...region, player }] : []
  }), [groundPlaced, size, players])
  const forts = useMemo(
    () => new Set(anchors.map((spot) => `${spot.q},${spot.r}`)),
    [anchors],
  )
  const rivers = useMemo(() => riverShapes(groundPlaced, size), [groundPlaced, size])
  const roads = useMemo(() => roadPaths(roadPlaced, size, anchors), [roadPlaced, size, anchors])
  const lakes = useMemo(() => lakeOutlines(groundPlaced, size), [groundPlaced, size])
  const regions = useMemo(() => Object.entries(EARTH)
    .filter(([ground]) => !["llanura", "lago", "rio"].includes(ground))
    .map(([ground, color]) => ({ ground, color, path: terrainOutlines(groundPlaced, size, new Set([ground])).join(" ") })),
  [groundPlaced, size])
  const scenery = useMemo(() => groundPlaced.flatMap((cell) =>
    ["lago", "rio", "campo", "mina"].includes(cell.ground) || forts.has(`${cell.q},${cell.r}`)
      ? []
      : ornaments(cell).map((mark, index) => ({
        ...mark,
        key: `${cell.q},${cell.r}-${index}`,
        x: cell.x + mark.x * size / SIZE,
        y: cell.y + mark.y * size / SIZE,
      })),
  ).sort((left, right) => left.y - right.y || left.x - right.x), [groundPlaced, forts, size])
  const sceneryArt = useMemo(() => scenery.map((mark) => (
    <g key={mark.key} transform={`translate(${mark.x} ${mark.y}) scale(${mark.scale * size / SIZE})`}>
      <g transform={`scale(${mark.mirror} 1)`}><OrnamentArt mark={mark} id={boardId} /></g>
    </g>
  )), [scenery, boardId, size])
  const marchKey = march?.map((path) =>
    `${path.id}:${path.spots.map((spot) => `${spot.q},${spot.r}`).join(">")}`,
  ).join("|") ?? ""
  const marchLayer = useRef<SVGGElement>(null)
  useMarchGlide(marchLayer, march, marchKey, size)
  const gliding = useMemo(() => new Set(march?.map((path) => path.id) ?? []), [marchKey, march])
  const pickRef = useRef({ onCellClick, onPaint, beginPaint })
  pickRef.current = { onCellClick, onPaint, beginPaint }
  const bounds = useMemo(() => measure(extent, size + 6), [extent, size])
  if (extent.length === 0 || !bounds) {
    return null
  }
  const { minX, minY, width, height } = bounds
  const marked = new Set(marks.map((mark) => `${mark.q},${mark.r}`))
  const tokenStacks = new Map<string, BoardToken[]>()
  for (const token of tokens) {
    const placed = tokenSpots?.[token.id] ?? token
    const key = `${placed.q},${placed.r}`
    const row = tokenStacks.get(key)
    if (row) row.push(token)
    else tokenStacks.set(key, [token])
  }

  return (
    <div className="hex-stage">
      {extent.length > 8 ? (
        <div className="hex-tools">
          <button type="button" onClick={() => setZoom((value) => adjacentZoom(value, -1))} disabled={zoom <= ZOOMS[0]} aria-label={t("mapZoomOut")}>−</button>
          <button type="button" onClick={() => setZoom(1)} aria-label={t("mapFit")}>{Math.round(zoom * 100)}%</button>
          <button type="button" onClick={() => setZoom((value) => adjacentZoom(value, 1))} disabled={zoom >= ZOOMS[ZOOMS.length - 1]} aria-label={t("mapZoomIn")}>+</button>
          {mapTools ? (
            <button type="button" onClick={() => setGrid((value) => !value)} aria-pressed={grid}>{t("mapGrid")}</button>
          ) : null}
          {mapTools && territories.length > 0 ? (
            <button type="button" onClick={() => setShowTerritories(value => !value)} aria-pressed={showTerritories}>
              {t("territoryToggle")}
            </button>
          ) : null}
        </div>
      ) : null}
      <div
        ref={extent.length > 8 ? viewportRef : undefined}
        className={extent.length > 8 ? "hex-viewport" : undefined}
        tabIndex={extent.length > 8 ? 0 : undefined}
        role="group"
        aria-label={t("mapsTitle")}
      >
      <svg
        ref={svgRef}
        className="hex-board"
        style={{
          width: `${zoom * 100}%`,
          touchAction: onPaint || dragging ? "none" : undefined,
          ["--mark" as string]: markColor,
          ["--mark-fill" as string]: markColor ? markTint(markColor, 0.3) : undefined,
        }}
        onPointerMove={(event) => {
          const start = tokenPress.current
          if (start && !start.armed && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) {
            if (movableIds?.has(start.id) && (onOrderToken || onTokenDrop)) {
              start.armed = true
              dragToken.current = start.id
              setDragging(true)
              svgRef.current?.setPointerCapture(event.pointerId)
              if (onOrderToken) {
                const at = hexFromEvent(event)
                if (at) onOrderToken(start.id, at, "down")
              }
            }
          }
          const id = dragToken.current
          if (!id || !onOrderToken) return
          const spot = hexFromEvent(event)
          if (spot) onOrderToken(id, spot, "move")
        }}
        onPointerUp={(event) => {
          const id = dragToken.current
          const spot = id && onTokenDrop ? hexFromEvent(event) : null
          const moved = tokenPress.current?.armed === true
          dragToken.current = null
          tokenPress.current = null
          setDragging(false)
          if (id && spot && onTokenDrop && moved) onTokenDrop(id, spot)
        }}
        viewBox={`${minX} ${minY} ${width} ${height}`}
        role="img"
        aria-label={t("mapsTitle")}
        data-picking={onCellClick || onPaint ? "true" : undefined}
      >
        <ArtDefinitions id={boardId} size={size} />
        {tokens.length > 0 ? <TokenDefinitions id={boardId} /> : null}
        <HexTerrain
          boardId={boardId}
          size={size}
          points={points}
          placed={placed}
          groundPlaced={groundPlaced}
          hidden={hidden}
          ghosted={ghosted}
          marks={marks}
          grid={grid}
          showTerritories={showTerritories}
          forts={forts}
          players={players}
          rivers={rivers}
          roads={roads}
          lakes={lakes}
          regions={regions}
          territories={territories}
          sceneryArt={sceneryArt}
          cellCount={cells.length}
          bounds={bounds}
          pickRef={pickRef}
          onHover={onHover}
        />
        <g className="hex-dim" pointerEvents="none">
          {shaded.map(cell => (
            <polygon key={`dim-${cell.q},${cell.r}`} points={points} transform={`translate(${cell.x} ${cell.y})`}>
              <title>{t("sightDim")}</title>
            </polygon>
          ))}
        </g>
        <g className="hex-marks" pointerEvents="none">
          {placed.filter((cell) => marked.has(`${cell.q},${cell.r}`)).map((cell) => {
            const arm = size * 0.18
            return (
              <g key={`mark-${cell.q},${cell.r}`} transform={`translate(${cell.x} ${cell.y})`}>
                <path className="hex-mark-cross is-shadow" d={`M ${-arm} 0 H ${arm} M 0 ${-arm} V ${arm}`} />
                <path className="hex-mark-cross" d={`M ${-arm} 0 H ${arm} M 0 ${-arm} V ${arm}`} />
              </g>
            )
          })}
        </g>
        {traces.map((trace, index) => trace.spots.length > 0 ? (
          <g key={`trace-${index}`} className="hex-trace" style={{ color: trace.color }}>
            {trace.spots.length > 1 ? (
              <polyline
                fill="none"
                stroke="currentColor"
                strokeWidth={size * 0.1}
                points={trace.spots.map((spot) => {
                  const center = hexCenter(spot.q, spot.r, size)
                  return `${center.x},${center.y}`
                }).join(" ")}
              />
            ) : null}
            {(() => {
              const last = trace.spots[trace.spots.length - 1]
              const center = hexCenter(last.q, last.r, size)
              return <circle cx={center.x} cy={center.y} r={size * 0.34} fill="none" stroke="currentColor" strokeWidth={size * 0.08} />
            })()}
          </g>
        ) : null)}
        {orderPaths.map((path, index) => {
          if (path.spots.length < 2) return null
          const entered = path.entered ?? path.spots.length - 1
          const reached = path.spots.slice(0, entered + 1)
          const owing = entered < path.spots.length - 1 ? path.spots.slice(entered) : []
          const pointsOf = (spots: Spot[]) => spots.map((spot) => {
            const center = hexCenter(spot.q, spot.r, size)
            return `${center.x},${center.y}`
          }).join(" ")
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
        {tokens.length > 0 ? (
          <g
            ref={marchLayer}
            className={tokensQuiet ? "hex-tokens is-quiet" : "hex-tokens"}
            pointerEvents="none"
          >
            {tokens.map((token) => {
              const placed = tokenSpots?.[token.id] ?? token
              const spot = hexCenter(placed.q, placed.r, size)
              const stack = tokenStacks.get(`${placed.q},${placed.r}`) ?? [token]
              const slot = stack.findIndex(item => item.id === token.id)
              const spread = stack.length > 1 ? (slot - (stack.length - 1) / 2) * size * 0.42 : 0
              const movable = movableIds?.has(token.id) ?? false
              const onMarch = gliding.has(token.id)
              return (
                <g
                  key={token.id}
                  data-token={token.id}
                  className={onMarch ? "hex-token-glide" : undefined}
                  transform={onMarch ? undefined : `translate(${spot.x + spread} ${spot.y})`}
                >
                  <UnitToken
                    boardId={boardId}
                    faction={token.faction}
                    kind={token.kind}
                    color={token.color}
                    x={0}
                    y={0}
                    size={size}
                    label={token.label}
                    mark={token.mark}
                    attention={token.attention}
                  />
                  <circle
                    className={selectedTokenId === token.id || spotlightId === token.id ? "hex-token-hit is-selected" : "hex-token-hit"}
                    r={size * 0.72}
                    onPointerEnter={() => showTokenNote.current(token)}
                    onPointerLeave={() => showTokenNote.current(null)}
                    onPointerDown={(event) => {
                      event.stopPropagation()
                      tokenPress.current = { id: token.id, x: event.clientX, y: event.clientY, armed: false }
                    }}
                    onPointerUp={(event) => {
                      const start = tokenPress.current
                      if (!start || start.id !== token.id || start.armed) return
                      event.stopPropagation()
                      const now = performance.now()
                      if (tokenTap.current?.id === token.id && now - tokenTap.current.at < 450) {
                        tokenTap.current = null
                        onTokenInspect?.(token.id)
                        return
                      }
                      tokenTap.current = { id: token.id, at: now }
                    }}
                    onClick={(event) => {
                      event.stopPropagation()
                      if (!movable) onTokenOpen?.(token.id)
                    }}
                    onDoubleClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      tokenTap.current = null
                      onTokenInspect?.(token.id)
                    }}
                  />
                </g>
              )
            })}
          </g>
        ) : null}
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
      </svg>
      </div>
      <p ref={caption} className="hex-caption" />
    </div>
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

function Bridge({ cell, at }: { cell: Placed; at: Map<string, Placed> }) {
  // Span bank to bank: opposite dry neighbours, never along the channel.
  const banks = STEPS.map(([q, r], index) => {
    const other = at.get(`${cell.q + q},${cell.r + r}`)
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

type BoardPick = {
  onCellClick?: (cell: OwnedCell) => void
  onPaint?: (cells: Array<OwnedCell | Spot>) => void
  beginPaint: (cell: OwnedCell | Spot) => void
}

type TerrainRegion = { owner_id: string; outline: string; clip: string; player: TerritoryPlayer }

const HexTerrain = memo(function HexTerrain({
  boardId,
  size,
  points,
  placed,
  groundPlaced,
  hidden,
  ghosted,
  marks,
  grid,
  showTerritories,
  forts,
  players,
  rivers,
  roads,
  lakes,
  regions,
  territories,
  sceneryArt,
  cellCount,
  bounds,
  pickRef,
  onHover,
}: {
  boardId: string
  size: number
  points: string
  placed: Placed[]
  groundPlaced: Placed[]
  hidden: Array<Spot & { x: number; y: number }>
  ghosted: Array<Spot & { x: number; y: number }>
  marks: Spot[]
  grid: boolean
  showTerritories: boolean
  forts: Set<string>
  players: TerritoryPlayer[]
  rivers: RiverShape[]
  roads: string[]
  lakes: string[]
  regions: { ground: string; color: string; path: string }[]
  territories: TerrainRegion[]
  sceneryArt: ReactNode
  cellCount: number
  bounds: { minX: number; minY: number; width: number; height: number }
  pickRef: { current: BoardPick }
  onHover: (cell: OwnedCell | null) => void
}) {
  const { t } = useI18n()
  const { minX, minY, width, height } = bounds
  const at = useMemo(() => {
    const map = new Map<string, Placed>()
    for (const cell of placed) map.set(`${cell.q},${cell.r}`, cell)
    return map
  }, [placed])
  const playersById = useMemo(
    () => new Map(players.map((player) => [player.player_id, player])),
    [players],
  )
  const faces = useMemo(() => {
    const markedCells = new Set(marks.map((mark) => `${mark.q},${mark.r}`))
    return placed.map((cell) => {
    const key = `${cell.q},${cell.r}`
    const fort = forts.has(key)
    const owner = cell.owner_id ? playersById.get(cell.owner_id) : undefined
    const name = [
      t(GROUND_LABEL[cell.ground] ?? "groundPlain"),
      ...(cell.road ? [t("mapRoad")] : []),
      ...(cell.bridge ? [t("mapBridge")] : []),
      ...(owner ? [t("territoryOwner", { player: owner.label })] : []),
    ].join(" · ")
    const effect = cell.road || cell.bridge
      ? t(GROUND_TIP_ON_ROAD[cell.ground] ?? "groundTipRoadClear")
      : t(GROUND_TIP[cell.ground] ?? "groundTipPlain")
    return (
      <polygon
        key={key}
        data-hex={key}
        points={points}
        transform={`translate(${cell.x} ${cell.y})`}
        className={`hex-edge${markedCells.has(key) ? " is-placeable" : ""}${fort ? " is-fort" : ""}`}
        style={{ strokeWidth: size / SIZE * (fort ? 1.6 : .45) }}
        onMouseEnter={() => onHover(cell)}
        onMouseLeave={(event) => {
          const next = event.relatedTarget
          if (next instanceof Element && next.closest(".hex-token-hit")) return
          onHover(null)
        }}
        onClick={() => {
          if (pickRef.current.onPaint) return
          pickRef.current.onCellClick?.(cell)
        }}
        onPointerDown={(event) => {
          if (!pickRef.current.onPaint) return
          event.preventDefault()
          pickRef.current.beginPaint(cell)
        }}
      >
        <title>{`${name}. ${effect}`}</title>
      </polygon>
    )
    })
  }, [placed, marks, forts, points, size, onHover, t, playersById, pickRef])
  return (
    <>
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
        {hidden.map((cell) => (
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
          {groundPlaced.map((cell) => (
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
        <g filter={cellCount <= 547 ? `url(#${boardId}-grain)` : undefined}>
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
        {placed.map((cell) => {
          const owner = cell.owner_id ? playersById.get(cell.owner_id) : undefined
          const key = `${cell.q},${cell.r}`
          return (
            <g key={key} transform={`translate(${cell.x} ${cell.y}) scale(${size / SIZE})`}>
              {cell.ground === "campo" ? <Fields /> : null}
              {cell.ground === "mina" ? <use href={`#${boardId}-mine`} x="-17" y="-20" width="34" height="26" /> : null}
              {cell.bridge ? <Bridge cell={cell} at={at} /> : null}
              {forts.has(key) ? <use href={`#${boardId}-keep`} x="-20" y="-29" width="40" height="38" /> : null}
              {forts.has(key) && owner?.color ? (
                <g className="hex-banner">
                  <path d="M9-18V-36" stroke="#504832" strokeWidth="1.2" />
                  <path d="M9-36L22-33L9-29Z" fill={owner.color} stroke="#eee0b7" strokeWidth=".55" />
                </g>
              ) : null}
            </g>
          )
        })}
      </g>
      <g className={grid ? undefined : "hex-grid-hidden"}>
        {ghosted.map((cell) => (
          <polygon
            key={`ghost-${cell.q},${cell.r}`}
            data-hex={`${cell.q},${cell.r}`}
            points={points}
            transform={`translate(${cell.x} ${cell.y})`}
            className="hex-edge hex-ghost"
            style={{ strokeWidth: size / SIZE * .45 }}
            onPointerDown={(event) => {
              if (!pickRef.current.onPaint) return
              event.preventDefault()
              pickRef.current.beginPaint(cell)
            }}
          >
            <title>{t("editorAddHex")}</title>
          </polygon>
        ))}
        {faces}
      </g>
    </>
  )
})

function useMarchGlide(
  layer: { current: SVGGElement | null },
  march: MarchPath[] | null,
  marchKey: string,
  size: number,
) {
  const marchRef = useRef(march)
  const keyRef = useRef(marchKey)
  const sizeRef = useRef(size)
  marchRef.current = march
  keyRef.current = marchKey
  sizeRef.current = size
  const clock = useRef<{ key: string; started: number } | null>(null)
  useLayoutEffect(() => {
    const host = layer.current
    const moves = marchRef.current
    const key = keyRef.current
    const hex = sizeRef.current
    if (!host || !moves || moves.length === 0 || !key) {
      clock.current = null
      return
    }
    if (clock.current?.key !== key) clock.current = { key, started: performance.now() }
    const started = clock.current.started
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const tracks = moves.flatMap((move) => {
      const node = host.querySelector<SVGGElement>(`[data-token="${CSS.escape(move.id)}"]`)
      if (!node || move.spots.length === 0) return []
      const costs = move.costs.length === move.spots.length - 1
        ? move.costs
        : move.spots.slice(0, -1).map(() => 1)
      return [{
        node,
        points: move.spots.map((spot) => hexCenter(spot.q, spot.r, hex)),
        costs,
      }]
    })
    const place = (node: SVGGElement, x: number, y: number) => {
      node.setAttribute("transform", `translate(${x} ${y})`)
    }
    const draw = (now: number) => {
      let running = false
      const elapsed = now - started
      for (const track of tracks) {
        const points = track.costs.reduce((sum, cost) => sum + Math.max(1, cost), 0)
        const span = Math.max(HOP_MS, points * HOP_MS)
        const progress = reduced ? 1 : Math.min(1, elapsed / span)
        const point = pointOnPath(track.points, track.costs, progress)
        place(track.node, point.x, point.y)
        if (progress < 1) running = true
      }
      return running
    }
    if (!draw(performance.now())) return
    let frame = 0
    const loop = (now: number) => {
      if (draw(now)) frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(frame)
  })
}

function pointOnPath(
  points: { x: number; y: number }[],
  costs: number[],
  progress: number,
): { x: number; y: number } {
  const last = points[points.length - 1]
  if (points.length === 1 || progress <= 0) return points[0]
  if (progress >= 1) return last
  const weights = costs.length === points.length - 1 ? costs : points.slice(0, -1).map(() => 1)
  const total = weights.reduce((sum, cost) => sum + Math.max(1, cost), 0)
  let remain = progress * total
  for (let index = 0; index < weights.length; index += 1) {
    const weight = Math.max(1, weights[index])
    if (remain <= weight || index === weights.length - 1) {
      const rest = Math.min(1, remain / weight)
      const from = points[index]
      const to = points[index + 1]
      return {
        x: from.x + (to.x - from.x) * rest,
        y: from.y + (to.y - from.y) * rest,
      }
    }
    remain -= weight
  }
  return last
}
