import { useMemo } from "react"

import { armyNeedsSheet, ownIndexes, toBoardTokens } from "../../game/hex/boardTokens"
import { exitCostOf, moveBudget, spotKey, stepsEntered, type Spot } from "../../game/hex/orders"
import { useI18n } from "../../i18n/language"
import { isKnownHex } from "../RoadPreparation"
import { placementMarks, prepOf, watchedDim } from "./phase"
import type { BoardSelection } from "./useBoardSelection"
import type { CampaignSession } from "./useCampaignSession"
import type { Orders } from "./useOrders"

export function useBoardView(
  session: CampaignSession,
  selection: BoardSelection,
  orders: Orders,
  filmPlaying: boolean,
) {
  const { t } = useI18n()
  const campaign = session.campaign
  const stage = campaign ? prepOf(campaign) : null
  const { orderPaths, ordering } = orders
  const { selectedToken } = selection

  const known = useMemo(
    () => (campaign ? campaign.hexes.filter(isKnownHex) : []),
    [campaign],
  )
  const unknown = useMemo(
    () => (campaign ? campaign.hexes.filter((cell) => !cell.known) : []),
    [campaign],
  )
  const players = useMemo(
    () => (campaign ? campaign.members.map((member) => ({
      player_id: member.player_id, color: member.color, label: member.alias,
    })) : []),
    [campaign],
  )
  const tokens = useMemo(
    () => (campaign ? toBoardTokens(campaign, t) : []),
    [campaign, t],
  )
  const drawnPaths = useMemo(() => {
    if (!campaign?.you) return []
    const own = campaign.armies.filter((army) => army.player_id === campaign.you?.player_id && army.q !== null && army.r !== null)
    const plots = new Map(campaign.hexes.map((cell) => [spotKey(cell), cell.known
      ? { known: true as const, ground: cell.ground, road: cell.road, bridge: cell.bridge }
      : { known: false as const }]))
    const line = (army: (typeof own)[number], path: Spot[]) => {
      if (army.q === null || army.r === null || path.length === 0) return []
      const origin = { q: army.q, r: army.r }
      return [{
        spots: [origin, ...path],
        selected: army.id === selectedToken,
        entered: stepsEntered(origin, path, moveBudget(campaign.rules.movement, army.kind), army.paid, plots),
      }]
    }
    if (ordering) return own.flatMap((army) => line(army, orderPaths[army.id] ?? []))
    if (campaign.you.orders_locked) return own.flatMap((army) => line(army, campaign.orders[army.id] ?? []))
    return []
  }, [campaign, ordering, orderPaths, selectedToken])
  const tokenNotes = useMemo(() => {
    if (!campaign?.you || campaign.phase !== "orders") return {}
    const notes: Record<string, string> = {}
    for (const army of campaign.armies) {
      if (army.player_id !== campaign.you.player_id || army.destroyed || army.q === null || army.r === null) {
        continue
      }
      const cell = campaign.hexes.find((hex) => hex.q === army.q && hex.r === army.r)
      const cost = exitCostOf(
        cell?.known
          ? { known: true, ground: cell.ground, road: cell.road, bridge: cell.bridge }
          : { known: false },
      )
      const list = army.kind === "army" && army.roster
        ? `\n${army.roster.length > 180 ? `${army.roster.slice(0, 180)}…` : army.roster}`
        : ""
      notes[army.id] = `${t("ordersPaidHint", {
        paid: String(army.paid),
        cost: String(cost),
        budget: String(moveBudget(campaign.rules.movement, army.kind)),
      })}${list}`
    }
    return notes
  }, [campaign, t])
  const movableIds = useMemo(() => new Set(
    campaign?.you && (ordering || stage === "armies")
      ? campaign.armies.flatMap((army) =>
        army.player_id === campaign.you?.player_id && !army.destroyed && army.q !== null ? [army.id] : [],
      )
      : [],
  ), [campaign, ordering, stage])
  const deployPieces = useMemo(() => {
    if (!campaign?.you || stage !== "armies") return []
    const marks = ownIndexes(campaign)
    const member = campaign.members.find((item) => item.player_id === campaign.you?.player_id)
    return campaign.armies.flatMap((army) => {
      if (army.player_id !== campaign.you?.player_id || army.destroyed) return []
      return [{
        id: army.id,
        kind: army.kind,
        faction: army.race || member?.faction || "",
        color: member?.color || "#c0a062",
        label: army.kind === "explorer" ? t("unitExplorer") : (army.commander || t("armyUnnamed")),
        mark: marks.get(army.id),
        placed: army.q !== null,
        attention: army.kind === "army" && armyNeedsSheet(army, campaign.rules.roster_required),
      }]
    })
  }, [campaign, stage, t])
  const watch = useMemo(() => {
    if (!campaign?.you) return null
    const you = campaign.you.player_id
    if (filmPlaying || !ordering) return null
    const spots = new Map<string, Spot>()
    for (const army of campaign.armies) {
      if (army.player_id !== you || army.destroyed || army.q === null || army.r === null) continue
      const path = orderPaths[army.id]
      spots.set(army.id, path && path.length > 0 ? path[path.length - 1] : { q: army.q, r: army.r })
    }
    return spots
  }, [campaign, filmPlaying, ordering, orderPaths])
  const dimmed = useMemo(
    () => (campaign ? watchedDim(campaign, watch) : []),
    [campaign, watch],
  )
  const shownTokens = useMemo(() => {
    if (!filmPlaying || !campaign) return tokens
    const ids = new Set(tokens.map((token) => token.id))
    const glimpsed = campaign.playback.moves.flatMap((move) => {
      if (ids.has(move.army_id)) return []
      return [{
        id: move.army_id,
        q: move.from.q,
        r: move.from.r,
        kind: move.kind ?? "army" as const,
        faction: move.faction ?? "",
        color: move.color || "#c0a062",
        label: move.name || t("unitArmy"),
      }]
    })
    return [...tokens, ...glimpsed]
  }, [campaign, filmPlaying, t, tokens])
  const locator = useMemo(() => {
    if (!campaign || stage === "fort" || stage === "roads") return []
    const you = campaign.you?.player_id
    return [...shownTokens].sort((left, right) => {
      const leftMine = campaign.armies.some((army) => army.id === left.id && army.player_id === you)
      const rightMine = campaign.armies.some((army) => army.id === right.id && army.player_id === you)
      if (leftMine !== rightMine) return leftMine ? -1 : 1
      return left.label.localeCompare(right.label, undefined, { sensitivity: "base" })
    })
  }, [campaign, shownTokens, stage])
  const traces = useMemo(() => {
    if (!campaign || filmPlaying) return []
    return campaign.playback.moves.flatMap((move) => {
      if (!move.lost) return []
      const spots = [move.from, ...move.steps]
      const unique = spots.filter((spot, index) => index === 0 || spot.q !== spots[index - 1].q || spot.r !== spots[index - 1].r)
      return unique.length > 0 ? [{ spots: unique, color: move.color || "#c0a062" }] : []
    })
  }, [campaign, filmPlaying])
  const lostNames = traces.length === 0 || !campaign
    ? ""
    : campaign.playback.moves
      .filter((move) => move.lost)
      .map((move) => move.name || t("unitArmy"))
      .join(", ")
  const marks = useMemo(
    () => (campaign ? placementMarks(campaign) : []),
    [campaign],
  )
  const clashes = useMemo(() => {
    if (!campaign || filmPlaying) return []
    const pairs: { from: Spot; to: Spot }[] = []
    for (const battle of campaign.battles) {
      if (battle.result !== null || battle.reverted || battle.army_ids.length < 2) continue
      const placed = battle.army_ids.flatMap((id) => {
        const army = campaign.armies.find((item) => item.id === id && !item.destroyed && item.q !== null && item.r !== null)
        if (!army || army.q === null || army.r === null) return []
        const rest = { q: army.q, r: army.r }
        return [{ spot: rest, rest }]
      })
      if (placed.length < 2) continue
      pairs.push({ from: placed[0].spot, to: placed[1].spot })
    }
    return pairs
  }, [campaign, filmPlaying])

  return {
    stage,
    known,
    unknown,
    players,
    drawnPaths,
    tokenNotes,
    movableIds,
    deployPieces,
    dimmed,
    shownTokens,
    locator,
    traces,
    lostNames,
    clashes,
    marks,
  }
}

export type BoardView = ReturnType<typeof useBoardView>
