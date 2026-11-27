import type { MessageKey } from "../i18n/catalog"

export type MapCell = {
  q: number
  r: number
  ground: string
  road: boolean
  bridge: boolean
}

export type MapSize = number
export type Visibility = "full" | "adjacent" | "anonymous" | "total" | "charted" | "home"
export type Victory = "armies" | "fortress" | "either"
export type Placement = "players" | "app"
export type CampaignPhase =
  | "recruiting"
  | "placing"
  | "preparing"
  | "orders"
  | "battles"
  | "finished"

export type RoadPrep = {
  budget: number
  laid: number
  left: number
  ready: boolean
}

export type RoadsDelta = {
  kind: "roads_delta"
  id: string
  revision: number
  phase: CampaignPhase
  turn: number
  road_ready: string[]
  roads: RoadPrep | null
  hexes: CampaignHex[]
  joined: true
}

export type CampaignRules = {
  seats: number
  armies: number
  movement: number
  map_size: MapSize
  visibility: Visibility
  victory: Victory
  hold_turns: number
  placement: Placement
  order_days: number
  battle_days: number
  missed_turns: number
  roster_required: boolean
}

export type CampaignSummary = {
  id: string
  name: string
  role: string
  status: string
  phase: CampaignPhase
}

export type CampaignMember = {
  player_id: string
  alias: string
  role: string
  status: string
  faction: string
  color: string
  ready: boolean
  orders_locked: boolean
}

export type CampaignHex = ({ known: true; owner_id: string | null; sight: boolean } & MapCell)
  | { q: number; r: number; known: false }

export type IdentityOptions = {
  factions: { id: string; label: MessageKey; legacy: boolean }[]
  colors: { id: string; label: MessageKey; value: string }[]
}

export type ChronicleSpot = {
  q: number
  r: number
}

export type ChronicleEntry = {
  turn: number
  code: string
  player_id?: string
  target_id?: string
  holder_id?: string
  army_id?: string
  battle_id?: string
  name?: string
  result?: string
  q?: number
  r?: number
  hold?: number
  undone?: number
  origin?: ChronicleSpot
  destination?: ChronicleSpot
  winners?: string[]
}

export type UnitKind = "army" | "explorer"

export type CampaignArmy = {
  id: string
  player_id: string | null
  name: string
  commander: string
  roster: string
  q: number | null
  r: number | null
  kind: UnitKind
  race: string
  anonymous: boolean
  destroyed: boolean
  paid: number
}

export type CampaignBattle = {
  id: string
  q: number
  r: number
  army_ids: string[]
  players: string[]
  result: string | null
  reverted: boolean
  due: boolean
  conflict: boolean
}

export type CampaignDetail = {
  id: string
  name: string
  description: string
  phase: CampaignPhase
  revision: number
  turn: number
  rules: CampaignRules
  members: CampaignMember[]
  joined: boolean
  you: CampaignMember | null
  hexes: CampaignHex[]
  fortresses: { q: number; r: number; player_id: string }[]
  armies: CampaignArmy[]
  battles: CampaignBattle[]
  orders: Record<string, { q: number; r: number }[]>
  playback: {
    turn: number
    moves: {
      army_id: string
      from: { q: number; r: number }
      steps: { q: number; r: number }[]
      costs?: number[]
      lost?: boolean
      kind?: "army" | "explorer"
      faction?: string
      color?: string
      name?: string
    }[]
  }
  chronicle: ChronicleEntry[]
  road_ready: string[]
  lobby_ready: string[]
  naming: boolean
  fort_open: boolean
  prep_done: string[]
  prep: "fort" | "roads" | "armies" | "waiting" | null
  roads: RoadPrep | null
}

export const DEFAULT_CAMPAIGN_RULES: CampaignRules = {
  seats: 2,
  armies: 1,
  movement: 3,
  // Small table disk (radius 9). Tiny disks like 19 cannot host fortresses.
  map_size: 271,
  visibility: "home",
  victory: "armies",
  hold_turns: 3,
  placement: "app",
  order_days: 7,
  battle_days: 7,
  missed_turns: 2,
  roster_required: false,
}

const PHASES: readonly CampaignPhase[] = [
  "recruiting",
  "placing",
  "preparing",
  "orders",
  "battles",
  "finished",
]
const VISIBILITIES: readonly Visibility[] = [
  "full",
  "adjacent",
  "anonymous",
  "total",
  "charted",
  "home",
]
const VICTORIES: readonly Victory[] = ["armies", "fortress", "either"]
const PLACEMENTS: readonly Placement[] = ["players", "app"]

export function isPhase(value: unknown): value is CampaignPhase {
  return typeof value === "string" && (PHASES as readonly string[]).includes(value)
}

export function isMapSize(value: unknown): value is MapSize {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 19) return false
  const radius = (Math.sqrt(12 * value - 3) - 3) / 6
  return Number.isInteger(radius) && radius <= 64
}

export function isVisibility(value: unknown): value is Visibility {
  return typeof value === "string" && (VISIBILITIES as readonly string[]).includes(value)
}

export function isVictory(value: unknown): value is Victory {
  return typeof value === "string" && (VICTORIES as readonly string[]).includes(value)
}

export function isPlacement(value: unknown): value is Placement {
  return typeof value === "string" && (PLACEMENTS as readonly string[]).includes(value)
}
