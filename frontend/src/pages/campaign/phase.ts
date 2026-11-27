import type { CampaignDetail, Victory, Visibility } from "../../api"
import { deployReach } from "../../game/hex/disk"
import { gazeReach, hexDistance, spotKey, type Spot } from "../../game/hex/orders"
import { isImpassable } from "../../game/hex/terrainContract"
import type { MessageKey } from "../../i18n/catalog"
import type { LiveSeat } from "../../liveEvents"
import { isKnownHex } from "../RoadPreparation"

export const PHASE_KEYS: Record<CampaignDetail["phase"], MessageKey> = {
  recruiting: "phaseRecruiting",
  placing: "phasePlacing",
  preparing: "phasePreparing",
  orders: "phaseOrders",
  battles: "phaseBattles",
  finished: "phaseFinished",
}

export function paintSeats(
  current: CampaignDetail | null,
  revision: number,
  seats: LiveSeat[],
): CampaignDetail | null {
  if (!current || revision < current.revision) return current
  const byId = new Map(seats.map((seat) => [seat.player_id, seat]))
  const apply = (member: CampaignDetail["members"][number]) => {
    const seat = byId.get(member.player_id)
    if (!seat || (member.color === seat.color && member.ready === seat.ready)) return member
    return { ...member, color: seat.color, ready: seat.ready }
  }
  const members = current.members.map(apply)
  const you = current.you ? apply(current.you) : current.you
  if (members.every((member, index) => member === current.members[index]) && you === current.you) {
    return current
  }
  // The event revision belongs to a document that has not arrived yet.
  // Stamping it now makes that document look old, and the map stays stale.
  return { ...current, members, you }
}

export function statusKey(phase: CampaignDetail["phase"]): MessageKey {
  if (phase === "finished") return "statusFinished"
  if (phase === "orders" || phase === "battles") return "statusRunning"
  return "statusPrepared"
}

export function visibilityKey(value: Visibility) {
  if (value === "full") return "visibilityFull" as const
  if (value === "total") return "visibilityTotal" as const
  if (value === "charted") return "visibilityCharted" as const
  if (value === "home") return "visibilityHome" as const
  if (value === "adjacent") return "visibilityAdjacent" as const
  return "visibilityAnonymous" as const
}

export function victoryKey(value: Victory) {
  if (value === "armies") return "victoryArmies" as const
  if (value === "fortress") return "victoryFortress" as const
  return "victoryEither" as const
}

export function standSpots(fort: Spot, hexes: CampaignDetail["hexes"], reach: number): Spot[] {
  return hexes.flatMap((cell) => {
    if (!cell.known || isImpassable(cell.ground)) return []
    if (hexDistance(cell, fort) > reach) return []
    return [{ q: cell.q, r: cell.r }]
  })
}

export function paintFort(
  campaign: CampaignDetail,
  playerId: string,
  fortress: { q: number; r: number },
  spots: Record<string, { q: number; r: number }>,
): CampaignDetail {
  const known = campaign.fortresses.some((fort) => fort.player_id === playerId)
  const fortresses = known
    ? campaign.fortresses.map((fort) => (
      fort.player_id === playerId ? { ...fort, q: fortress.q, r: fortress.r } : fort
    ))
    : [...campaign.fortresses, { player_id: playerId, ...fortress }]
  const armies = campaign.armies.map((army) => {
    const spot = spots[army.id]
    return spot ? { ...army, q: spot.q, r: spot.r } : army
  })
  return { ...campaign, fortresses, armies }
}

export function prepOf(campaign: CampaignDetail): "fort" | "roads" | "armies" | "waiting" | null {
  if (
    campaign.prep === "fort" ||
    campaign.prep === "roads" ||
    campaign.prep === "armies" ||
    campaign.prep === "waiting"
  ) {
    return campaign.prep
  }
  if (campaign.phase === "placing" || (campaign.phase === "preparing" && campaign.fort_open)) return "fort"
  if (campaign.phase === "preparing" && !campaign.naming) return "roads"
  if (campaign.naming) return "armies"
  return null
}

export function placementMarks(campaign: CampaignDetail): Spot[] {
  const you = campaign.you?.player_id
  if (!you) return []
  const stage = prepOf(campaign)
  if (stage === "fort") {
    if (campaign.lobby_ready.includes(you)) return []
    return campaign.hexes.flatMap((cell) => {
      if (!cell.known || cell.owner_id !== you || isImpassable(cell.ground)) return []
      return [{ q: cell.q, r: cell.r }]
    })
  }
  if (stage !== "armies") return []
  const fort = campaign.fortresses.find((item) => item.player_id === you)
  return fort ? standSpots(fort, campaign.hexes, deployReach(campaign.rules.map_size)) : []
}

export function watchedDim(campaign: CampaignDetail, watch: Map<string, Spot> | null): Spot[] {
  if (campaign.rules.visibility === "full" || campaign.rules.visibility === "total") return []
  const you = campaign.you?.player_id
  if (!you || watch === null) {
    return campaign.hexes.flatMap((cell) => cell.known && !cell.sight ? [{ q: cell.q, r: cell.r }] : [])
  }
  const known = campaign.hexes.filter(isKnownHex)
  const groundAt = new Map(known.map((cell) => [spotKey(cell), cell.ground]))
  const eyes = campaign.armies.flatMap((army) => {
    if (army.player_id !== you || army.destroyed || army.q === null || army.r === null) return []
    const at = watch.get(army.id) ?? { q: army.q, r: army.r }
    return [{ at, reach: gazeReach(groundAt.get(spotKey(at)), army.kind === "explorer") }]
  })
  return known.flatMap((cell) => {
    if (cell.owner_id === you) return []
    if (eyes.some((eye) => hexDistance(cell, eye.at) <= eye.reach)) return []
    return [{ q: cell.q, r: cell.r }]
  })
}
