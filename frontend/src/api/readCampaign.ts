import { GROUND_LABEL } from "../game/hex/grounds"
import { isMessageKey } from "../i18n/catalog"
import { ALIAS, CONTROL, readInt } from "./http"
import {
  isMapSize,
  isPhase,
  isPlacement,
  isVictory,
  isVisibility,
  type CampaignArmy,
  type CampaignBattle,
  type CampaignDetail,
  type CampaignHex,
  type CampaignMember,
  type CampaignRules,
  type CampaignSummary,
  type ChronicleEntry,
  type ChronicleSpot,
  type RoadPrep,
} from "./campaignTypes"

function readRules(value: unknown): CampaignRules | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const seats = readInt(record.seats, 2, 4)
  const armies = readInt(record.armies, 1, 2)
  const movement = readInt(record.movement, 1, 5)
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
    roster_required: record.roster_required === true,
  }
}

export function readSummary(value: unknown): CampaignSummary | null {
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
  const ready = record.ready === true
  const orders_locked = record.orders_locked === true
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
  return { player_id, alias, role, status, faction, color, ready, orders_locked }
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
  const sight = (value as { sight?: unknown }).sight !== false
  return {
    ...spot, known: true, ground: value.ground, road: value.road, bridge: value.bridge,
    owner_id: value.owner_id === null ? null : String(value.owner_id),
    sight,
  }
}

export function readDetailCampaign(value: unknown): CampaignDetail | null {
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
    typeof record.description !== "string" ||
    record.description.length > 15000 ||
    CONTROL.test(record.description.replaceAll("\n", "").replaceAll("\t", "")) ||
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
  const armies: CampaignArmy[] = []
  if (record.joined) {
    // Recruiting seals the atlas (empty hexes). Drawn atlases may keep a subset later.
    if (!you || !Array.isArray(record.hexes) ||
      (record.hexes.length < 1 && record.phase !== "recruiting") ||
      record.hexes.length > rules.map_size ||
      !Array.isArray(record.fortresses) || record.fortresses.length > 8 ||
      !Array.isArray(record.armies) || record.armies.length > 32) return null
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
        !hexes.some(cell => cell.q === spot.q && cell.r === spot.r)) return null
      fortresses.push({ ...spot, player_id: value.player_id })
    }
    for (const value of record.armies) {
      const army = readCampaignArmy(value, members)
      if (!army) return null
      armies.push(army)
    }
  }
  const road_ready = readIdList(record.road_ready)
  const lobby_ready = readIdList(record.lobby_ready)
  const prep_done = readIdList(record.prep_done)
  const prep = readPrep(record.prep)
  const roads = readRoadPrep(record.roads)
  if (road_ready === null || lobby_ready === null || prep_done === null ||
    (record.phase === "preparing" && record.joined && roads === null && prep !== "fort")) {
    return null
  }
  return {
    id: record.id,
    name: record.name,
    description: record.description,
    phase: record.phase,
    revision,
    turn,
    rules,
    members,
    joined: record.joined,
    you,
    hexes,
    fortresses,
    armies,
    battles: readBattles(record.battles, members),
    orders: readOrders(record.orders),
    playback: readPlayback(record.playback),
    chronicle: record.phase === "finished" ? readChronicle(record.chronicle) : [],
    road_ready: road_ready ?? [],
    lobby_ready: lobby_ready ?? [],
    naming: record.naming === true,
    fort_open: record.fort_open === true,
    prep_done: prep_done ?? [],
    prep,
    roads: record.phase === "preparing" ? roads : null,
  }
}

function readOrders(value: unknown): CampaignDetail["orders"] {
  if (!value || typeof value !== "object") return {}
  const orders: CampaignDetail["orders"] = {}
  for (const [id, path] of Object.entries(value as Record<string, unknown>)) {
    if (!readLabel(id, 64) || !Array.isArray(path) || path.length > 64) continue
    const steps: { q: number; r: number }[] = []
    let valid = true
    for (const step of path) {
      const spot = readSpot(step)
      if (!spot) {
        valid = false
        break
      }
      steps.push(spot)
    }
    if (valid) orders[id] = steps
  }
  return orders
}

function readPlayback(value: unknown): CampaignDetail["playback"] {
  if (!value || typeof value !== "object") return { turn: 0, moves: [] }
  const record = value as Record<string, unknown>
  const turn = readInt(record.turn, 0, 1_000_000) ?? 0
  if (!Array.isArray(record.moves)) return { turn, moves: [] }
  const moves: CampaignDetail["playback"]["moves"] = []
  for (const item of record.moves) {
    if (!item || typeof item !== "object") continue
    const row = item as Record<string, unknown>
    const army_id = readLabel(row.army_id, 64)
    const from = readSpot(row.from)
    if (!army_id || !from || !Array.isArray(row.steps) || row.steps.length > 64) continue
    const steps: { q: number; r: number }[] = []
    let valid = true
    for (const step of row.steps) {
      const spot = readSpot(step)
      if (!spot) {
        valid = false
        break
      }
      steps.push(spot)
    }
    if (!valid || steps.length === 0) continue
    const move: CampaignDetail["playback"]["moves"][number] = { army_id, from, steps }
    const costs = readHopCosts(row.costs, steps.length)
    if (costs) move.costs = costs
    if (row.lost === true) {
      move.lost = true
      move.kind = row.kind === "explorer" ? "explorer" : "army"
      move.faction = readLabel(row.faction, 40) ?? ""
      move.color = typeof row.color === "string" && /^#[0-9a-f]{6}$/.test(row.color) ? row.color : ""
      move.name = typeof row.name === "string" && row.name.length <= 40 ? row.name : ""
    }
    moves.push(move)
  }
  return { turn, moves }
}

function readHopCosts(value: unknown, hops: number): number[] | undefined {
  if (!Array.isArray(value) || value.length !== hops) return undefined
  const costs: number[] = []
  for (const item of value) {
    const cost = readInt(item, 1, 3)
    if (cost === null) return undefined
    costs.push(cost)
  }
  return costs
}

function readCampaignArmy(value: unknown, members: CampaignMember[]): CampaignArmy | null {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  const id = readLabel(record.id, 64)
  const kind = record.kind === "explorer" || record.kind === "army" ? record.kind : null
  const q = record.q === null ? null : readInt(record.q, -64, 64)
  const r = record.r === null ? null : readInt(record.r, -64, 64)
  if (!id || !kind || typeof record.anonymous !== "boolean") return null
  if (record.q !== null && q === null) return null
  if (record.r !== null && r === null) return null
  if (record.anonymous) {
    return {
      id,
      player_id: null,
      name: "",
      commander: "",
      roster: "",
      q,
      r,
      kind,
      race: "",
      anonymous: true,
      destroyed: false,
      paid: 0,
    }
  }
  const player_id = readLabel(record.player_id, 64)
  const name = typeof record.name === "string" && record.name.length <= 40 ? record.name : null
  const commander = typeof record.commander === "string" && record.commander.length <= 40 ? record.commander : ""
  const roster = typeof record.roster === "string" && record.roster.length <= 2000 ? record.roster : ""
  const race = typeof record.race === "string" && record.race.length <= 40 ? record.race : ""
  if (!player_id || name === null || typeof record.destroyed !== "boolean") return null
  if (!members.some(member => member.player_id === player_id)) return null
  return {
    id,
    player_id,
    name,
    commander,
    roster,
    q,
    r,
    kind,
    race,
    anonymous: false,
    destroyed: record.destroyed,
    paid: readInt(record.paid, 0, 99) ?? 0,
  }
}

function readPrep(value: unknown): CampaignDetail["prep"] {
  if (value === "fort" || value === "roads" || value === "armies" || value === "waiting") return value
  return null
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

function readBattles(value: unknown, members: CampaignMember[]): CampaignBattle[] {
  if (!Array.isArray(value)) return []
  const battles: CampaignBattle[] = []
  for (const item of value) {
    if (!item || typeof item !== "object") continue
    const row = item as Record<string, unknown>
    const id = readLabel(row.id, 64)
    const spot = readSpot(row)
    if (!id || !spot || !Array.isArray(row.players) || row.players.length > 8) continue
    const players = row.players.flatMap((player) =>
      typeof player === "string" && members.some((member) => member.player_id === player) ? [player] : [],
    )
    if (players.length === 0) continue
    const result = row.result === null
      ? null
      : typeof row.result === "string" && (row.result === "draw" || players.includes(row.result))
        ? row.result
        : null
    battles.push({
      id,
      q: spot.q,
      r: spot.r,
      army_ids: Array.isArray(row.army_ids)
        ? row.army_ids.flatMap((armyId) =>
          typeof armyId === "string" && armyId.length > 0 && armyId.length <= 64 ? [armyId] : [],
        )
        : [],
      players,
      result,
      reverted: row.reverted === true,
      due: row.due === true,
      conflict: row.conflict === true,
    })
  }
  return battles
}

export function readRoadMutation(value: unknown, baseline: CampaignDetail): CampaignDetail | null {
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
    naming: typeof record.naming === "boolean" ? record.naming : baseline.naming,
    fort_open: typeof record.fort_open === "boolean" ? record.fort_open : baseline.fort_open,
    prep_done: Array.isArray(record.prep_done)
      ? (readIdList(record.prep_done) ?? baseline.prep_done)
      : baseline.prep_done,
    prep: record.prep === undefined ? baseline.prep : readPrep(record.prep),
    roads: record.phase === "preparing" ? roads : null,
    hexes,
    chronicle: record.phase === "finished" ? baseline.chronicle : [],
  }
}
