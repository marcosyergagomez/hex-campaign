import { useEffect, useRef, useState } from "react"

import { ApiError, getCampaign, lockCampaignOrders } from "../../api"
import {
  moveBudget,
  routeTo,
  spotKey,
  type Spot,
} from "../../game/hex/orders"
import { presentError } from "../../presentError"
import type { BoardSelection } from "./useBoardSelection"
import type { CampaignSession } from "./useCampaignSession"

export function useOrders(session: CampaignSession, selection: BoardSelection, filmPlaying: boolean) {
  const [orderPaths, setOrderPaths] = useState<Record<string, Spot[]>>({})
  const orderPathsRef = useRef(orderPaths)
  orderPathsRef.current = orderPaths
  const lastAim = useRef("")
  const worldRef = useRef<{
    campaign: NonNullable<CampaignSession["campaign"]>
    plots: Map<string, { known: true; ground: string; road: boolean; bridge: boolean } | { known: false }>
    board: Set<string>
    forts: Set<string>
  } | null>(null)
  const [locking, setLocking] = useState(false)
  const campaign = session.campaign
  const ordering = Boolean(
    campaign &&
      campaign.phase === "orders" &&
      campaign.you?.status === "active" &&
      !campaign.you.orders_locked &&
      !filmPlaying,
  )

  useEffect(() => {
    lastAim.current = ""
    setOrderPaths({})
    selection.setSelectedToken(null)
  }, [campaign?.id, campaign?.turn, selection.setSelectedToken])

  function plan(armyId: string, target: Spot) {
    const current = session.campaign
    if (!current?.you) return
    const aim = `${armyId}:${target.q},${target.r}`
    let world = worldRef.current
    if (world?.campaign !== current) {
      world = {
        campaign: current,
        plots: new Map(current.hexes.map((cell) => [spotKey(cell), cell.known
          ? { known: true as const, ground: cell.ground, road: cell.road, bridge: cell.bridge }
          : { known: false as const }])),
        board: new Set(current.hexes.map(spotKey)),
        forts: new Set(current.fortresses.map(spotKey)),
      }
      worldRef.current = world
      lastAim.current = ""
    }
    if (lastAim.current === aim) return
    lastAim.current = aim
    const army = current.armies.find((item) => item.id === armyId && item.player_id === current.you?.player_id)
    if (!army || army.q === null || army.r === null || army.destroyed) return
    const plots = world.plots
    const board = world.board
    const forts = world.forts
    const blocked = new Set(
      current.armies.flatMap((item) => {
        if (item.kind !== "army" || item.player_id === army.player_id || item.destroyed) return []
        if (item.q === null || item.r === null) return []
        return [spotKey({ q: item.q, r: item.r })]
      }),
    )
    const next = routeTo({
      origin: { q: army.q, r: army.r },
      path: orderPathsRef.current[armyId] ?? [],
      target,
      budget: moveBudget(current.rules.movement, army.kind),
      paid: army.paid,
      kind: army.kind,
      plots,
      board,
      forts,
      blocked,
    })
    if (!next) return
    const taken = new Set(
      current.armies.flatMap((item) => {
        if (item.id === armyId || item.kind !== "army" || item.player_id !== army.player_id) return []
        const path = orderPathsRef.current[item.id]
        if (item.q === null || item.r === null) return []
        const end = path && path.length > 0 ? path[path.length - 1] : { q: item.q, r: item.r }
        return [spotKey(end)]
      }),
    )
    if (next.length > 0 && army.kind === "army" && taken.has(spotKey(next[next.length - 1]))) return
    setOrderPaths((paths) => {
      const previous = paths[armyId] ?? []
      if (sameSpots(previous, next)) return paths
      return { ...paths, [armyId]: next }
    })
  }

  async function lockTurn() {
    const current = session.campaign
    if (!current?.you || locking || session.busy) return
    const orders: Record<string, Spot[]> = {}
    for (const army of current.armies) {
      if (army.player_id !== current.you.player_id || army.destroyed || army.q === null) continue
      orders[army.id] = orderPaths[army.id] ?? []
    }
    const campaignId = current.id
    let revision = current.revision
    setLocking(true)
    session.setBusy(true)
    try {
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          session.accept(await lockCampaignOrders(campaignId, revision, orders))
          if (session.mounted.current) session.setErrors({})
          return
        } catch (error: unknown) {
          if (!(error instanceof ApiError) || error.status !== 409 || attempt === 1) throw error
          const fresh = await getCampaign(campaignId)
          session.accept(fresh, true)
          if (fresh.revision === revision) throw error
          revision = fresh.revision
        }
      }
    } catch (error: unknown) {
      if (session.mounted.current) session.setErrors(presentError(error, "ordersFailed"))
    } finally {
      if (session.mounted.current) {
        setLocking(false)
        session.setBusy(false)
      }
    }
  }

  return { orderPaths, ordering, locking, plan, lockTurn }
}

function sameSpots(left: Spot[], right: Spot[]): boolean {
  if (left.length !== right.length) return false
  for (let index = 0; index < left.length; index += 1) {
    if (left[index].q !== right[index].q || left[index].r !== right[index].r) return false
  }
  return true
}

export type Orders = ReturnType<typeof useOrders>
