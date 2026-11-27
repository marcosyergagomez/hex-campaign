import { isMessageKey } from "../i18n/catalog"
import { ApiError, csrfHeaders, readInt, request } from "./http"
import type { CampaignDetail, CampaignRules, CampaignSummary, IdentityOptions } from "./campaignTypes"
import { readDetailCampaign, readRoadMutation, readSummary } from "./readCampaign"

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
  description = "",
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
        description,
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

export type CampaignPulse = {
  revision: number
  phase: CampaignDetail["phase"]
}

export async function getCampaignPulse(id: string): Promise<CampaignPulse> {
  const data = await request(`/api/campaigns/${encodeURIComponent(id)}/pulse`, { method: "GET" })
  if (!data || typeof data !== "object") throw new ApiError(200, {})
  const record = data as Record<string, unknown>
  const revision = readInt(record.revision, 1, 1_000_000_000)
  const phase = record.phase
  if (
    revision === null ||
    typeof phase !== "string" ||
    !["recruiting", "placing", "preparing", "orders", "battles", "finished"].includes(phase)
  ) {
    throw new ApiError(200, {})
  }
  return { revision, phase: phase as CampaignDetail["phase"] }
}

export async function deleteCampaign(id: string, confirmName: string): Promise<void> {
  await request(`/api/campaigns/${encodeURIComponent(id)}/scrap`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...csrfHeaders(),
    },
    body: JSON.stringify({ confirm_name: confirmName }),
  })
}

export async function restoreCampaignMember(
  id: string,
  revision: number,
  playerId: string,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/restore`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...csrfHeaders(),
      },
      body: JSON.stringify({ revision, player_id: playerId }),
    }),
  )
  if (!campaign) {
    throw new ApiError(200, {})
  }
  return campaign
}

async function postCampaignAction(id: string, path: string, body: object): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(await request(`/api/campaigns/${encodeURIComponent(id)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(body),
  }))
  if (!campaign) throw new ApiError(200, {})
  return campaign
}

export async function describeCampaignArmy(
  id: string,
  revision: number,
  armyId: string,
  sheet: { name: string; commander: string; race: string; roster: string },
): Promise<CampaignDetail> {
  return postCampaignAction(id, `/armies/${encodeURIComponent(armyId)}`, {
    revision,
    ...sheet,
  })
}

export async function promoteCampaignMember(
  id: string, revision: number, playerId: string,
): Promise<CampaignDetail> {
  return postCampaignAction(id, "/admins", { revision, player_id: playerId })
}

export async function revertCampaignTurn(id: string, revision: number): Promise<CampaignDetail> {
  return postCampaignAction(id, "/revert", { revision })
}

export async function closeCampaignOrders(id: string, revision: number): Promise<CampaignDetail> {
  return postCampaignAction(id, "/orders/close", { revision })
}

export async function judgeCampaignBattle(
  id: string, battleId: string, revision: number, result: string,
): Promise<CampaignDetail> {
  return postCampaignAction(id, `/battles/${encodeURIComponent(battleId)}/judge`, { revision, result })
}

export async function expelCampaignMember(
  id: string,
  revision: number,
  playerId: string,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/expel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...csrfHeaders(),
      },
      body: JSON.stringify({ revision, player_id: playerId }),
    }),
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

export async function lockCampaignOrders(
  id: string,
  revision: number,
  orders: Record<string, { q: number; r: number }[]>,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(await request(`/api/campaigns/${encodeURIComponent(id)}/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ revision, orders }),
  }))
  if (!campaign) throw new ApiError(200, {})
  return campaign
}

export async function claimCampaignColor(
  id: string, revision: number, color: string,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(await request(`/api/campaigns/${encodeURIComponent(id)}/color`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ revision, color }),
  }))
  if (!campaign) throw new ApiError(200, {})
  return campaign
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

export async function markCampaignReady(
  id: string,
  revision: number,
  ready = true,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/ready`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision, ready }),
    }),
  )
  if (!campaign) throw new ApiError(200, {})
  return campaign
}

export async function startCampaign(
  id: string,
  revision: number,
  admins: string[] = [],
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision, admins }),
    }),
  )
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

export async function standCampaignArmy(
  id: string,
  revision: number,
  armyId: string,
  q: number,
  r: number,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/armies/${encodeURIComponent(armyId)}/stand`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision, q, r }),
    }),
  )
  if (!campaign) throw new ApiError(200, {})
  return campaign
}

export type FortMove = {
  revision: number
  fortresses: { player_id: string; q: number; r: number }[]
  armies: { id: string; q: number; r: number }[]
}

function readFortMove(value: unknown): FortMove | null {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  if (record.kind !== "fort_delta" || record.joined !== true) return null
  const revision = readInt(record.revision, 1, 1_000_000_000)
  if (revision === null || !Array.isArray(record.fortresses) || !Array.isArray(record.armies)) return null
  if (record.fortresses.length > 8 || record.armies.length > 32) return null
  const fortresses: FortMove["fortresses"] = []
  for (const item of record.fortresses) {
    if (!item || typeof item !== "object") return null
    const fort = item as Record<string, unknown>
    const q = readInt(fort.q, -64, 64)
    const r = readInt(fort.r, -64, 64)
    if (q === null || r === null || typeof fort.player_id !== "string" || fort.player_id.length > 64) return null
    fortresses.push({ player_id: fort.player_id, q, r })
  }
  const armies: FortMove["armies"] = []
  for (const item of record.armies) {
    if (!item || typeof item !== "object") return null
    const army = item as Record<string, unknown>
    const q = readInt(army.q, -64, 64)
    const r = readInt(army.r, -64, 64)
    if (q === null || r === null || typeof army.id !== "string" || army.id.length > 64) return null
    armies.push({ id: army.id, q, r })
  }
  return { revision, fortresses, armies }
}

export async function placeCampaignArmies(
  id: string,
  revision: number,
  fortress: { q: number; r: number },
  armies: Record<string, { q: number; r: number }>,
): Promise<FortMove> {
  const move = readFortMove(
    await request(`/api/campaigns/${encodeURIComponent(id)}/placement`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision, fortress, armies }),
    }),
  )
  if (!move) throw new ApiError(200, {})
  return move
}

export function applyFortMove(baseline: CampaignDetail, move: FortMove): CampaignDetail {
  if (move.revision < baseline.revision) return baseline
  const you = baseline.you?.player_id ?? ""
  const incoming = new Map(
    move.fortresses
      .filter((fort) => fort.player_id === you)
      .map((fort) => [fort.player_id, fort]),
  )
  const fortresses = baseline.fortresses.map((fort) => {
    const next = incoming.get(fort.player_id)
    if (!next) return fort
    incoming.delete(fort.player_id)
    return next.q === fort.q && next.r === fort.r ? fort : { ...fort, ...next }
  })
  const ownFort = you ? incoming.get(you) : undefined
  if (ownFort) fortresses.push(ownFort)
  const spots = new Map(move.armies.map((army) => [army.id, army]))
  const armies = baseline.armies.map((army) => {
    if (army.player_id !== you) return army
    const next = spots.get(army.id)
    if (!next || (army.q === next.q && army.r === next.r)) return army
    return { ...army, q: next.q, r: next.r }
  })
  return { ...baseline, revision: move.revision, fortresses, armies }
}

export async function confirmCampaignPlacement(id: string, revision: number): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/placement/ready`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision }),
    }),
  )
  if (!campaign) throw new ApiError(200, {})
  return campaign
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
