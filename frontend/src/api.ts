import { readCookie } from "./cookies"
import { isMessageKey, type MessageKey } from "./i18n/catalog"
import { GROUND_LABEL } from "./game/hex/grounds"

export type FieldErrors = Record<string, string[]>

export type Sex = "woman" | "man" | "other" | "undisclosed"

export type Player = {
  email: string
  alias: string
}

export class ApiError extends Error {
  readonly status: number
  readonly errors: FieldErrors

  constructor(status: number, errors: FieldErrors) {
    super("api")
    this.status = status
    this.errors = errors
  }
}

const ALIAS = /^[A-Za-z0-9_]{3,24}$/
const CONTROL = /[\u0000-\u001F\u007F]/

function isErrorBody(value: unknown): value is { errors: FieldErrors } {
  if (!value || typeof value !== "object" || !("errors" in value)) {
    return false
  }
  const errors = value.errors
  if (!errors || typeof errors !== "object" || Array.isArray(errors)) {
    return false
  }
  const entries = Object.entries(errors)
  if (entries.length === 0 || entries.length > 12) {
    return false
  }
  return entries.every(([, messages]) => {
    return (
      Array.isArray(messages) &&
      messages.length > 0 &&
      messages.length <= 8 &&
      messages.every((item) => typeof item === "string" && item.length > 0 && item.length <= 300)
    )
  })
}

function readPlayer(value: unknown): Player | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const { email, alias } = record
  if (typeof email !== "string" || typeof alias !== "string") {
    return null
  }
  if (email.length === 0 || email.length > 254 || CONTROL.test(email)) {
    return null
  }
  if (!ALIAS.test(alias)) {
    return null
  }
  return { email, alias }
}

function readDetail(value: unknown): string | null {
  if (!value || typeof value !== "object" || !("detail" in value)) {
    return null
  }
  const detail = (value as { detail: unknown }).detail
  if (typeof detail !== "string" || detail.length === 0 || detail.length > 500 || CONTROL.test(detail)) {
    return null
  }
  return detail
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

async function request(path: string, init: RequestInit): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(0, {})
  }
  const data = await readJson(response)
  if (!response.ok) {
    throw new ApiError(response.status, isErrorBody(data) ? data.errors : {})
  }
  return data
}

export async function login(email: string, password: string): Promise<Player> {
  const player = readPlayer(
    await request("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  )
  if (!player) {
    throw new ApiError(200, {})
  }
  return player
}

export async function currentPlayer(): Promise<Player | null> {
  try {
    const player = readPlayer(await request("/api/session", { method: "GET" }))
    if (!player) {
      throw new ApiError(200, {})
    }
    return player
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }
    throw error
  }
}

export async function logout(): Promise<void> {
  const token = readCookie("__Host-csrf")
  await request("/api/session/logout", {
    method: "POST",
    headers: token ? { "X-CSRF-Token": token } : {},
  })
}

export type Registration = {
  email: string
  password: string
  alias: string
  birth_date: string
  sex: Sex
}

export async function register(payload: Registration): Promise<{ detail: string }> {
  const detail = readDetail(
    await request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  )
  if (!detail) {
    throw new ApiError(202, {})
  }
  return { detail }
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
}

export type CampaignHex = ({ known: true; owner_id: string | null } & MapCell)
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

export type CampaignDetail = {
  id: string
  name: string
  phase: CampaignPhase
  revision: number
  turn: number
  rules: CampaignRules
  members: CampaignMember[]
  joined: boolean
  you: CampaignMember | null
  hexes: CampaignHex[]
  fortresses: { q: number; r: number; player_id: string }[]
  chronicle: ChronicleEntry[]
  road_ready: string[]
  roads: RoadPrep | null
}

export const DEFAULT_CAMPAIGN_RULES: CampaignRules = {
  seats: 2,
  armies: 1,
  movement: 1,
  map_size: 19,
  visibility: "full",
  victory: "armies",
  hold_turns: 3,
  placement: "app",
  order_days: 7,
  battle_days: 7,
  missed_turns: 2,
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

function isPhase(value: unknown): value is CampaignPhase {
  return typeof value === "string" && (PHASES as readonly string[]).includes(value)
}

function isMapSize(value: unknown): value is MapSize {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 19) return false
  const radius = (Math.sqrt(12 * value - 3) - 3) / 6
  return Number.isInteger(radius) && radius <= 64
}

function isVisibility(value: unknown): value is Visibility {
  return typeof value === "string" && (VISIBILITIES as readonly string[]).includes(value)
}

function isVictory(value: unknown): value is Victory {
  return typeof value === "string" && (VICTORIES as readonly string[]).includes(value)
}

function isPlacement(value: unknown): value is Placement {
  return typeof value === "string" && (PLACEMENTS as readonly string[]).includes(value)
}

function readInt(value: unknown, min: number, max: number): number | null {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min || value > max) {
    return null
  }
  return value
}

function readRules(value: unknown): CampaignRules | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const seats = readInt(record.seats, 2, 4)
  const armies = readInt(record.armies, 1, 2)
  const movement = readInt(record.movement, 1, 3)
  const hold_turns = readInt(record.hold_turns, 1, 999)
  const order_days = readInt(record.order_days, 1, 30)
  const battle_days = readInt(record.battle_days, 1, 30)
  const missed_turns = readInt(record.missed_turns, 1, 5)
  if (
    seats === null ||
    armies === null ||
    movement === null ||
    hold_turns === null ||
    order_days === null ||
    battle_days === null ||
    missed_turns === null ||
    !isMapSize(record.map_size) ||
    !isVisibility(record.visibility) ||
    !isVictory(record.victory) ||
    !isPlacement(record.placement)
  ) {
    return null
  }
  return {
    seats,
    armies,
    movement,
    map_size: record.map_size,
    visibility: record.visibility,
    victory: record.victory,
    hold_turns,
    placement: record.placement,
    order_days,
    battle_days,
    missed_turns,
  }
}

function readSummary(value: unknown): CampaignSummary | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const { id, name, role, status, phase } = record
  if (
    typeof id !== "string" ||
    id.length === 0 ||
    id.length > 64 ||
    typeof name !== "string" ||
    name.length === 0 ||
    name.length > 120 ||
    CONTROL.test(name) ||
    typeof role !== "string" ||
    role.length === 0 ||
    role.length > 32 ||
    typeof status !== "string" ||
    status.length === 0 ||
    status.length > 32 ||
    !isPhase(phase)
  ) {
    return null
  }
  return { id, name, role, status, phase }
}

function readMember(value: unknown): CampaignMember | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const { player_id, alias, role, status, faction, color } = record
  if (
    typeof player_id !== "string" ||
    player_id.length === 0 ||
    player_id.length > 64 ||
    typeof alias !== "string" ||
    !ALIAS.test(alias) ||
    typeof role !== "string" ||
    role.length === 0 ||
    role.length > 32 ||
    typeof status !== "string" ||
    status.length === 0 ||
    status.length > 32 ||
    typeof faction !== "string" ||
    (faction !== "" && !isMessageKey(`race_${faction}`)) ||
    typeof color !== "string" ||
    (color !== "" && !/^#[0-9a-f]{6}$/.test(color))
  ) {
    return null
  }
  return { player_id, alias, role, status, faction, color }
}

function readCampaignHex(value: unknown): CampaignHex | null {
  const spot = readSpot(value)
  if (!spot || !value || typeof value !== "object" || !("known" in value)) return null
  if (value.known === false) {
    if ("owner_id" in value || "ground" in value || "road" in value || "bridge" in value) return null
    return { ...spot, known: false }
  }
  if (value.known !== true || !("ground" in value) || typeof value.ground !== "string" ||
    !Object.hasOwn(GROUND_LABEL, value.ground) || !("road" in value) || typeof value.road !== "boolean" ||
    !("bridge" in value) || typeof value.bridge !== "boolean" || !("owner_id" in value) ||
    (value.owner_id !== null && readLabel(value.owner_id, 64) === undefined)) return null
  return {
    ...spot, known: true, ground: value.ground, road: value.road, bridge: value.bridge,
    owner_id: value.owner_id === null ? null : String(value.owner_id),
  }
}

function readDetailCampaign(value: unknown): CampaignDetail | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const rules = readRules(record.rules)
  const revision = readInt(record.revision, 1, 1_000_000_000)
  const turn = readInt(record.turn, 0, 1_000_000)
  if (
    typeof record.id !== "string" ||
    record.id.length === 0 ||
    record.id.length > 64 ||
    typeof record.name !== "string" ||
    record.name.length === 0 ||
    record.name.length > 120 ||
    CONTROL.test(record.name) ||
    !isPhase(record.phase) ||
    revision === null ||
    turn === null ||
    rules === null ||
    typeof record.joined !== "boolean" ||
    !Array.isArray(record.members)
  ) {
    return null
  }
  if (record.members.length > 8) {
    return null
  }
  const members: CampaignMember[] = []
  for (const item of record.members) {
    const member = readMember(item)
    if (!member) {
      return null
    }
    members.push(member)
  }
  const you = record.you === null || !record.joined ? null : readMember(record.you)
  const hexes: CampaignHex[] = []
  const fortresses: CampaignDetail["fortresses"] = []
  if (record.joined) {
    if (!you || !Array.isArray(record.hexes) || record.hexes.length !== rules.map_size ||
      !Array.isArray(record.fortresses) || record.fortresses.length > 8) return null
    for (const value of record.hexes) {
      const cell = readCampaignHex(value)
      if (!cell || (cell.known && cell.owner_id !== null &&
        !members.some(member => member.player_id === cell.owner_id))) return null
      hexes.push(cell)
    }
    if (new Set(hexes.map(cell => `${cell.q},${cell.r}`)).size !== hexes.length) return null
    for (const value of record.fortresses) {
      const spot = readSpot(value)
      if (!spot || !value || typeof value !== "object" || !("player_id" in value) ||
        typeof value.player_id !== "string" ||
        !members.some(member => member.player_id === value.player_id) ||
        !hexes.some(cell => cell.q === spot.q && cell.r === spot.r && cell.known)) return null
      fortresses.push({ ...spot, player_id: value.player_id })
    }
  }
  const road_ready = readIdList(record.road_ready)
  const roads = readRoadPrep(record.roads)
  if (road_ready === null || (record.phase === "preparing" && record.joined && roads === null)) {
    return null
  }
  return {
    id: record.id,
    name: record.name,
    phase: record.phase,
    revision,
    turn,
    rules,
    members,
    joined: record.joined,
    you,
    hexes,
    fortresses,
    chronicle: record.phase === "finished" ? readChronicle(record.chronicle) : [],
    road_ready: road_ready ?? [],
    roads: record.phase === "preparing" ? roads : null,
  }
}

function readIdList(value: unknown): string[] | null {
  if (value === undefined) {
    return []
  }
  if (!Array.isArray(value) || value.length > 8) {
    return null
  }
  const ids: string[] = []
  for (const item of value) {
    if (typeof item !== "string" || item.length === 0 || item.length > 64) {
      return null
    }
    ids.push(item)
  }
  return ids
}

function readRoadPrep(value: unknown): RoadPrep | null {
  if (value === null || value === undefined) {
    return null
  }
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const budget = readInt(record.budget, 0, 64)
  const laid = readInt(record.laid, 0, 64)
  const left = readInt(record.left, 0, 64)
  if (budget === null || laid === null || left === null || typeof record.ready !== "boolean") {
    return null
  }
  return { budget, laid, left, ready: record.ready }
}

const CODE = /^[a-z_]{1,40}$/

function readSpot(value: unknown): ChronicleSpot | undefined {
  if (!value || typeof value !== "object") {
    return undefined
  }
  const record = value as Record<string, unknown>
  const q = readInt(record.q, -64, 64)
  const r = readInt(record.r, -64, 64)
  if (q === null || r === null) {
    return undefined
  }
  return { q, r }
}

function readLabel(value: unknown, max: number): string | undefined {
  if (typeof value !== "string" || value.length === 0 || value.length > max || CONTROL.test(value)) {
    return undefined
  }
  return value
}

function readWinners(value: unknown): string[] | undefined {
  if (!Array.isArray(value) || value.length > 4) {
    return undefined
  }
  const winners: string[] = []
  for (const item of value) {
    const winner = readLabel(item, 64)
    if (!winner) {
      return undefined
    }
    winners.push(winner)
  }
  return winners
}

function readChronicleEntry(value: unknown): ChronicleEntry | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const turn = readInt(record.turn, 0, 1_000_000)
  if (turn === null || typeof record.code !== "string" || !CODE.test(record.code)) {
    return null
  }
  const entry: ChronicleEntry = { turn, code: record.code }
  const player_id = readLabel(record.player_id, 64)
  const target_id = readLabel(record.target_id, 64)
  const holder_id = readLabel(record.holder_id, 64)
  const army_id = readLabel(record.army_id, 64)
  const battle_id = readLabel(record.battle_id, 64)
  const name = readLabel(record.name, 80)
  const result = readLabel(record.result, 64)
  const q = readInt(record.q, -64, 64)
  const r = readInt(record.r, -64, 64)
  const hold = readInt(record.hold, 0, 999)
  const undone = readInt(record.undone, 0, 1_000_000)
  const origin = readSpot(record.origin)
  const destination = readSpot(record.destination)
  const winners = readWinners(record.winners)
  if (player_id) entry.player_id = player_id
  if (target_id) entry.target_id = target_id
  if (holder_id) entry.holder_id = holder_id
  if (army_id) entry.army_id = army_id
  if (battle_id) entry.battle_id = battle_id
  if (name) entry.name = name
  if (result) entry.result = result
  if (q !== null) entry.q = q
  if (r !== null) entry.r = r
  if (hold !== null) entry.hold = hold
  if (undone !== null) entry.undone = undone
  if (origin) entry.origin = origin
  if (destination) entry.destination = destination
  if (winners) entry.winners = winners
  return entry
}

function readChronicle(value: unknown): ChronicleEntry[] {
  if (!Array.isArray(value)) {
    return []
  }
  const entries: ChronicleEntry[] = []
  for (const item of value.slice(0, 5000)) {
    const entry = readChronicleEntry(item)
    if (entry) {
      entries.push(entry)
    }
  }
  return entries
}

function csrfHeaders(): HeadersInit {
  const token = readCookie("__Host-csrf")
  return token ? { "X-CSRF-Token": token } : {}
}

export async function listCampaigns(): Promise<CampaignSummary[]> {
  const data = await request("/api/campaigns", { method: "GET" })
  if (!Array.isArray(data) || data.length > 100) {
    throw new ApiError(200, {})
  }
  const rows: CampaignSummary[] = []
  for (const item of data) {
    const row = readSummary(item)
    if (!row) {
      throw new ApiError(200, {})
    }
    rows.push(row)
  }
  return rows
}

export async function createCampaign(
  name: string,
  rules: CampaignRules,
  map?: { id: string; blind: boolean },
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request("/api/campaigns", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...csrfHeaders(),
      },
      body: JSON.stringify({
        name,
        rules,
        map_id: map?.id ?? null,
        blind: map?.blind ?? false,
      }),
    }),
  )
  if (!campaign) {
    throw new ApiError(201, {})
  }
  return campaign
}

export async function getCampaign(id: string): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}`, { method: "GET" }),
  )
  if (!campaign) {
    throw new ApiError(200, {})
  }
  return campaign
}

export async function identityOptions(): Promise<IdentityOptions> {
  const data = await request("/api/campaign-identity", { method: "GET" })
  if (!data || typeof data !== "object" || !("factions" in data) || !Array.isArray(data.factions) ||
    !("colors" in data) || !Array.isArray(data.colors) ||
    data.factions.length === 0 || data.factions.length > 40 ||
    data.colors.length < 4 || data.colors.length > 16) throw new ApiError(200, {})
  const factions = data.factions.map((value: unknown) => {
    if (!value || typeof value !== "object" || !("id" in value) || typeof value.id !== "string" ||
      !("legacy" in value) || typeof value.legacy !== "boolean") throw new ApiError(200, {})
    const label = `race_${value.id}`
    if (!isMessageKey(label)) throw new ApiError(200, {})
    return { id: value.id, label, legacy: value.legacy }
  })
  const colors = data.colors.map((value: unknown) => {
    if (!value || typeof value !== "object" || !("id" in value) || typeof value.id !== "string" ||
      !("value" in value) || typeof value.value !== "string" ||
      !/^#[0-9a-f]{6}$/.test(value.value)) throw new ApiError(200, {})
    const label = `color_${value.id}`
    if (!isMessageKey(label)) throw new ApiError(200, {})
    return { id: value.id, label, value: value.value }
  })
  if (new Set(factions.map(item => item.id)).size !== factions.length ||
    new Set(colors.map(item => item.value)).size !== colors.length) throw new ApiError(200, {})
  return { factions, colors }
}

export async function saveIdentity(
  id: string, revision: number, faction: string, color: string,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(await request(`/api/campaigns/${encodeURIComponent(id)}/identity`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ revision, faction, color }),
  }))
  if (!campaign) throw new ApiError(200, {})
  return campaign
}

async function postRoadMutation(
  id: string,
  path: string,
  body: object,
  baseline: CampaignDetail,
): Promise<CampaignDetail> {
  const data = await request(`/api/campaigns/${encodeURIComponent(id)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(body),
  })
  const merged = readRoadMutation(data, baseline)
  if (!merged) throw new ApiError(200, {})
  return merged
}

export async function placeRoad(
  id: string, revision: number, q: number, r: number, baseline: CampaignDetail,
): Promise<CampaignDetail> {
  return postRoadMutation(id, "/roads", { revision, q, r }, baseline)
}

export async function clearRoad(
  id: string, revision: number, q: number, r: number, baseline: CampaignDetail,
): Promise<CampaignDetail> {
  return postRoadMutation(id, "/roads/clear", { revision, q, r }, baseline)
}

export async function finishRoads(
  id: string, revision: number, baseline: CampaignDetail,
): Promise<CampaignDetail> {
  return postRoadMutation(id, "/roads/ready", { revision }, baseline)
}

function readRoadMutation(value: unknown, baseline: CampaignDetail): CampaignDetail | null {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  if (record.kind === "roads_delta") {
    return applyRoadsDelta(baseline, record)
  }
  return readDetailCampaign(value)
}

function applyRoadsDelta(
  baseline: CampaignDetail,
  record: Record<string, unknown>,
): CampaignDetail | null {
  if (baseline.id !== record.id || record.joined !== true || !isPhase(record.phase)) {
    return null
  }
  const revision = readInt(record.revision, 1, 1_000_000_000)
  const turn = readInt(record.turn, 0, 1_000_000)
  const road_ready = readIdList(record.road_ready)
  if (revision === null || turn === null || road_ready === null) return null
  if (revision < baseline.revision) return null
  const roads = readRoadPrep(record.roads)
  if (record.phase === "preparing" && roads === null) return null
  if (!Array.isArray(record.hexes) || record.hexes.length > 8) return null

  const patches = new Map<string, CampaignHex>()
  for (const value of record.hexes) {
    const cell = readCampaignHex(value)
    if (!cell) return null
    if (cell.known && cell.owner_id !== null &&
      !baseline.members.some(member => member.player_id === cell.owner_id)) {
      return null
    }
    patches.set(`${cell.q},${cell.r}`, cell)
  }

  let applied = 0
  const hexes = baseline.hexes.map(cell => {
    const patch = patches.get(`${cell.q},${cell.r}`)
    if (!patch) return cell
    applied += 1
    return patch
  })
  if (applied !== patches.size) return null

  return {
    ...baseline,
    revision,
    phase: record.phase,
    turn,
    road_ready,
    roads: record.phase === "preparing" ? roads : null,
    hexes,
    chronicle: record.phase === "finished" ? baseline.chronicle : [],
  }
}

export type SavedMap = {
  id: string
  name: string
  size: MapSize
  seats: number | null
  generated: boolean
}

export type MapCell = {
  q: number
  r: number
  ground: string
  road: boolean
  bridge: boolean
}

export type SavedMapDetail = SavedMap & {
  cells: MapCell[]
  anchors: { q: number; r: number }[]
}

export type MapScale = {
  key: "small" | "medium" | "large"
  size: MapSize
  seats: number[]
  recommend: number
  home_size: number
}

export async function listMapScales(): Promise<MapScale[]> {
  const data = await request("/api/map-scales", { method: "GET" })
  if (!Array.isArray(data) || data.length !== 3) throw new ApiError(200, {})
  const scales = data.map((value): MapScale => {
    if (!value || typeof value !== "object") throw new ApiError(200, {})
    const record = value as Record<string, unknown>
    if (
      (record.key !== "small" && record.key !== "medium" && record.key !== "large") ||
      !isMapSize(record.size) || !Array.isArray(record.seats) ||
      record.seats.length < 1 || record.seats.length > 3
    ) throw new ApiError(200, {})
    const seats = record.seats.map((seat: unknown) => {
      const parsed = readInt(seat, 2, 4)
      if (parsed === null) throw new ApiError(200, {})
      return parsed
    })
    const recommend = readInt(record.recommend, 2, 4)
    const home = readInt(record.home_size, 7, Math.floor(record.size / 2) - 1)
    if (recommend === null || home === null || !seats.includes(recommend)) {
      throw new ApiError(200, {})
    }
    return { key: record.key, size: record.size, seats, recommend, home_size: home }
  })
  if (new Set(scales.map(scale => scale.key)).size !== 3 ||
    new Set(scales.map(scale => scale.size)).size !== 3) throw new ApiError(200, {})
  return scales
}

export async function listMaps(): Promise<SavedMap[]> {
  const data = await request("/api/maps", { method: "GET" })
  if (!Array.isArray(data) || data.length > 100) {
    throw new ApiError(200, {})
  }
  return data.map(readSavedMap)
}

export async function generateMap(name: string, size: MapSize, seats: number): Promise<SavedMap> {
  return readSavedMap(
    await request("/api/maps", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name, size, seats }),
    }),
  )
}

export async function deleteMap(id: string): Promise<void> {
  await request(`/api/maps/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { ...csrfHeaders() },
  })
}

export async function saveDrawnMap(
  name: string,
  size: MapSize,
  cells: MapCell[],
  anchors: { q: number; r: number }[],
): Promise<SavedMap> {
  return readSavedMap(
    await request("/api/maps", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name, size, cells, anchors }),
    }),
  )
}

export async function updateDrawnMap(
  id: string,
  name: string,
  size: MapSize,
  cells: MapCell[],
  anchors: { q: number; r: number }[],
): Promise<SavedMap> {
  return readSavedMap(
    await request(`/api/maps/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name, size, cells, anchors }),
    }),
  )
}

export async function copyMapForEdit(id: string, name?: string): Promise<SavedMap> {
  return readSavedMap(
    await request(`/api/maps/${encodeURIComponent(id)}/copy`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name: name ?? null }),
    }),
  )
}

export async function getMap(id: string): Promise<SavedMapDetail> {
  const data = await request(`/api/maps/${encodeURIComponent(id)}`, { method: "GET" })
  const summary = readSavedMap(data)
  if (!data || typeof data !== "object") {
    throw new ApiError(200, {})
  }
  const record = data as Record<string, unknown>
  if (!Array.isArray(record.cells) || !Array.isArray(record.anchors)) {
    throw new ApiError(200, {})
  }
  const cells: MapCell[] = []
  for (const item of record.cells) {
    if (!item || typeof item !== "object") {
      throw new ApiError(200, {})
    }
    const cell = item as Record<string, unknown>
    const q = readInt(cell.q, -64, 64)
    const r = readInt(cell.r, -64, 64)
    if (q === null || r === null || typeof cell.ground !== "string") {
      throw new ApiError(200, {})
    }
    cells.push({
      q,
      r,
      ground: cell.ground,
      road: cell.road === true,
      bridge: cell.bridge === true,
    })
  }
  const anchors: { q: number; r: number }[] = []
  for (const item of record.anchors) {
    if (!item || typeof item !== "object") {
      throw new ApiError(200, {})
    }
    const spot = item as Record<string, unknown>
    const q = readInt(spot.q, -64, 64)
    const r = readInt(spot.r, -64, 64)
    if (q === null || r === null) {
      throw new ApiError(200, {})
    }
    anchors.push({ q, r })
  }
  return { ...summary, cells, anchors }
}

function readSavedMap(value: unknown): SavedMap {
  if (!value || typeof value !== "object") {
    throw new ApiError(200, {})
  }
  const record = value as Record<string, unknown>
  if (
    typeof record.id !== "string" ||
    typeof record.name !== "string" ||
    !isMapSize(record.size) ||
    typeof record.generated !== "boolean"
  ) {
    throw new ApiError(200, {})
  }
  const seats = record.seats === null ? null : readInt(record.seats, 2, 4)
  if (record.seats !== null && seats === null) {
    throw new ApiError(200, {})
  }
  return {
    id: record.id,
    name: record.name,
    size: record.size,
    seats,
    generated: record.generated,
  }
}

