import type { MapCell } from "../../api"
import type { UnitKind } from "./tokens"
import type { MarchPath } from "./useMarchFilm"

/** Art scale the ornaments, bridges and forts were drawn at. */
export const SIZE = 28

export type Spot = { q: number; r: number }

export type OwnedCell = MapCell & { owner_id?: string | null }

export type Placed = OwnedCell & { x: number; y: number }

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

export type BoardBounds = {
  minX: number
  minY: number
  width: number
  height: number
}

export type OrderPath = { spots: Spot[]; selected?: boolean; entered?: number }

export type BoardTrace = { spots: Spot[]; color: string }

export type BoardClash = { from: Spot; to: Spot }

export type FocusSpot = { q: number; r: number; n: number }

export const NO_PLAYERS: TerritoryPlayer[] = []
export const NO_SPOTS: Spot[] = []
export const NO_TOKENS: BoardToken[] = []
export const NO_PATHS: OrderPath[] = []
export const NO_TRACES: BoardTrace[] = []
export const NO_CLASHES: BoardClash[] = []

export function markTint(color: string, alpha: number): string {
  const hex = color.trim().replace("#", "")
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return color
  const r = Number.parseInt(hex.slice(0, 2), 16)
  const g = Number.parseInt(hex.slice(2, 4), 16)
  const b = Number.parseInt(hex.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function measure(cells: { x: number; y: number }[], pad: number): BoardBounds | null {
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

export type HexBoardProps = {
  cells: OwnedCell[]
  anchors: Spot[]
  size?: number
  players?: TerritoryPlayer[]
  unknown?: Spot[]
  dimmed?: Spot[]
  traces?: BoardTrace[]
  clashes?: BoardClash[]
  ghosts?: Spot[]
  tokens?: BoardToken[]
  tokensQuiet?: boolean
  marks?: Spot[]
  markColor?: string
  tokenNotes?: Record<string, string>
  onCellClick?: (cell: OwnedCell) => void
  onPaint?: (cells: Array<OwnedCell | Spot>) => void
  orderPaths?: OrderPath[]
  tokenSpots?: Record<string, Spot> | null
  /** Resolved march. Tokens glide along these hexes without redrawing the board. */
  march?: MarchPath[] | null
  movableIds?: ReadonlySet<string>
  selectedTokenId?: string | null
  /** Scroll the board so this hex sits in the middle. `n` repeats the same hex. */
  focusSpot?: FocusSpot | null
  spotlightId?: string | null
  mapTools?: boolean
  onOrderToken?: (id: string, spot: Spot, phase: "down" | "move") => void
  onTokenOpen?: (id: string) => void
  onTokenInspect?: (id: string) => void
  onTokenDrop?: (id: string, spot: Spot) => void
  spotAtRef?: { current: ((clientX: number, clientY: number) => Spot | null) | null }
}
