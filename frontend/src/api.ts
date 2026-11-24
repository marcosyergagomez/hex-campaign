import { readCookie } from "./cookies"

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

export type MapSize = 19 | 37 | 61
export type Visibility = "full" | "adjacent" | "anonymous"
export type Victory = "armies" | "fortress" | "either"
export type Placement = "players" | "app"
export type CampaignPhase =
  | "recruiting"
  | "placing"
  | "orders"
  | "battles"
  | "finished"

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
  "orders",
  "battles",
  "finished",
]
const MAP_SIZES: readonly MapSize[] = [19, 37, 61]
const VISIBILITIES: readonly Visibility[] = ["full", "adjacent", "anonymous"]
const VICTORIES: readonly Victory[] = ["armies", "fortress", "either"]
const PLACEMENTS: readonly Placement[] = ["players", "app"]

function isPhase(value: unknown): value is CampaignPhase {
  return typeof value === "string" && (PHASES as readonly string[]).includes(value)
}

function isMapSize(value: unknown): value is MapSize {
  return typeof value === "number" && (MAP_SIZES as readonly number[]).includes(value)
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
  const { player_id, alias, role, status } = record
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
    status.length > 32
  ) {
    return null
  }
  return { player_id, alias, role, status }
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
  return {
    id: record.id,
    name: record.name,
    phase: record.phase,
    revision,
    turn,
    rules,
    members,
    joined: record.joined,
  }
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
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request("/api/campaigns", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...csrfHeaders(),
      },
      body: JSON.stringify({ name, rules }),
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
