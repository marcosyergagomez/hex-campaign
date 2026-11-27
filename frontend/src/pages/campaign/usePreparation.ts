import { useRef } from "react"

import {
  ApiError,
  applyFortMove,
  clearRoad,
  confirmCampaignPlacement,
  finishRoads,
  getCampaign,
  placeCampaignArmies,
  placeRoad,
  standCampaignArmy,
} from "../../api"
import { deployReach } from "../../game/hex/disk"
import { isImpassable } from "../../game/hex/terrainContract"
import { clientNotice } from "../../i18n/catalog"
import { presentError } from "../../presentError"
import { seatAroundFort } from "../seatAroundFort"
import { roadEdit } from "../RoadPreparation"
import type { BoardSelection } from "./useBoardSelection"
import type { CampaignSession } from "./useCampaignSession"
import { paintFort, prepOf, standSpots } from "./phase"

export function usePreparation(session: CampaignSession, selection: BoardSelection) {
  const fortMove = useRef({
    running: false,
    revision: 0,
    pending: null as null | {
      fortress: { q: number; r: number }
      armies: Record<string, { q: number; r: number }>
    },
  })
  const roadJob = useRef({
    running: false,
    revision: 0,
    queue: [] as { q: number; r: number; add: boolean }[],
  })
  const standJob = useRef({
    running: false,
    revision: 0,
    queue: [] as { id: string; q: number; r: number }[],
  })

  async function placeFort(cell: { q: number; r: number; owner_id?: string | null }) {
    const campaign = session.campaign
    if (!campaign?.you) return
    const you = campaign.you.player_id
    const known = campaign.hexes.find((hex) => hex.q === cell.q && hex.r === cell.r)
    if (!known?.known) return
    const owner = cell.owner_id ?? known.owner_id
    if (owner !== you) return
    const home = new Set(
      campaign.hexes.flatMap((hex) => (
        hex.known && hex.owner_id === you ? [`${hex.q},${hex.r}`] : []
      )),
    )
    const standable = new Set(
      campaign.hexes.flatMap((hex) => {
        if (!hex.known || hex.owner_id !== you || isImpassable(hex.ground)) return []
        return [`${hex.q},${hex.r}`]
      }),
    )
    for (const fort of campaign.fortresses) {
      if (fort.player_id !== you) standable.delete(`${fort.q},${fort.r}`)
    }
    const own = campaign.armies.filter((army) => army.player_id === campaign.you?.player_id && !army.destroyed)
    const spots = seatAroundFort({ q: cell.q, r: cell.r }, home, own, standable)
    if (!spots) {
      session.setErrors({ campaign: [clientNotice("prepFortFailed")] })
      return
    }
    const fortress = { q: cell.q, r: cell.r }
    session.setCampaign((current) => {
      const next = current ? paintFort(current, you, fortress, spots) : current
      if (next) session.campaignRef.current = next
      return next
    })
    const job = fortMove.current
    if (!job.running) job.revision = Math.max(job.revision, campaign.revision)
    job.pending = { fortress, armies: spots }
    if (job.running) return
    job.running = true
    session.setJob("fort", true)
    try {
      while (job.pending) {
        const next = job.pending
        job.pending = null
        const moved = await placeCampaignArmies(campaign.id, job.revision, next.fortress, next.armies)
        job.revision = moved.revision
        const queued = job.pending !== null
        if (!session.mounted.current) return
        session.setCampaign((current) => {
          if (!current || moved.revision < current.revision) return current
          if (queued) return { ...current, revision: moved.revision }
          return applyFortMove(current, moved)
        })
      }
      if (session.mounted.current) session.setErrors({})
    } catch (error: unknown) {
      job.pending = null
      if (session.mounted.current) session.setErrors(presentError(error, "prepFortFailed"))
      try {
        const fresh = await getCampaign(campaign.id)
        job.revision = fresh.revision
        session.accept(fresh, true)
      } catch {
        /* the banner already says the click failed */
      }
    } finally {
      job.running = false
      session.setJob("fort", false)
    }
  }

  function queueRoad(cell: { q: number; r: number }) {
    const current = session.campaignRef.current
    if (!current?.roads || !current.you) return
    const live = current.hexes.find((hex) => hex.q === cell.q && hex.r === cell.r)
    if (!live?.known) return
    const edit = roadEdit(current, { ...live, owner_id: live.owner_id })
    if (!edit) return
    const add = edit === "add"
    const laid = current.roads.laid + (add ? 1 : -1)
    const hexes = current.hexes.map((hex) => (
      hex.q === cell.q && hex.r === cell.r && hex.known ? { ...hex, road: add } : hex
    ))
    const next = {
      ...current,
      hexes,
      roads: { ...current.roads, laid, left: Math.max(0, current.roads.budget - laid) },
    }
    session.campaignRef.current = next
    session.setCampaign(next)
    roadJob.current.queue.push({ q: cell.q, r: cell.r, add })
    void drainRoads(current.id)
  }

  async function drainRoads(id: string) {
    const job = roadJob.current
    if (job.running) return
    job.running = true
    session.setJob("road", true)
    try {
      while (job.queue.length) {
        const next = job.queue.shift()
        if (!next) break
        const baseline = session.campaignRef.current
        if (!baseline) break
        const revision = job.revision || baseline.revision
        const saved = next.add
          ? await placeRoad(id, revision, next.q, next.r, baseline)
          : await clearRoad(id, revision, next.q, next.r, baseline)
        job.revision = saved.revision
        if (job.queue.length === 0) {
          session.campaignRef.current = saved
          if (session.mounted.current) session.setCampaign(saved)
        }
      }
      if (session.mounted.current) session.setErrors({})
    } catch (error: unknown) {
      job.queue = []
      if (session.mounted.current) session.setErrors(presentError(error, "campaignLoadFailed"))
      try {
        const fresh = await getCampaign(id)
        job.revision = fresh.revision
        session.campaignRef.current = fresh
        session.accept(fresh, true)
      } catch {
        /* the banner already says the click failed */
      }
    } finally {
      job.running = false
      session.setJob("road", false)
    }
  }

  async function finishRoadStep() {
    while (roadJob.current.running || roadJob.current.queue.length > 0) {
      await new Promise((resolve) => window.setTimeout(resolve, 40))
    }
    const current = session.campaignRef.current
    if (!current) return
    const revision = Math.max(current.revision, roadJob.current.revision)
    await session.applyCampaign(() => finishRoads(current.id, revision, current))
  }

  function queueStand(cell: { q: number; r: number }, armyId?: string) {
    const current = session.campaignRef.current
    const id = armyId ?? selection.selectedToken
    if (!current?.you || !id) return
    const army = current.armies.find((item) =>
      item.id === id && item.player_id === current.you?.player_id && !item.destroyed,
    )
    if (!army || (army.q === cell.q && army.r === cell.r)) return
    const fort = current.fortresses.find((item) => item.player_id === current.you?.player_id)
    if (!fort) return
    const allowed = standSpots(fort, current.hexes, deployReach(current.rules.map_size))
    if (!allowed.some((spot) => spot.q === cell.q && spot.r === cell.r)) return
    const next = {
      ...current,
      armies: current.armies.map((item) => (
        item.id === id ? { ...item, q: cell.q, r: cell.r } : item
      )),
    }
    session.campaignRef.current = next
    session.setCampaign(next)
    standJob.current.queue.push({ id, q: cell.q, r: cell.r })
    void drainStands(current.id)
  }

  async function drainStands(id: string) {
    const job = standJob.current
    if (job.running) return
    job.running = true
    session.setJob("stand", true)
    try {
      while (job.queue.length) {
        const next = job.queue.shift()
        if (!next) break
        const baseline = session.campaignRef.current
        if (!baseline) break
        const revision = job.revision || baseline.revision
        const saved = await standCampaignArmy(id, revision, next.id, next.q, next.r)
        job.revision = saved.revision
        if (job.queue.length === 0) {
          session.campaignRef.current = saved
          if (session.mounted.current) session.setCampaign(saved)
        }
      }
      if (session.mounted.current) session.setErrors({})
    } catch (error: unknown) {
      job.queue = []
      if (session.mounted.current) session.setErrors(presentError(error, "campaignLoadFailed"))
      try {
        const fresh = await getCampaign(id)
        job.revision = fresh.revision
        session.campaignRef.current = fresh
        session.accept(fresh, true)
      } catch {
        /* the banner already says the click failed */
      }
    } finally {
      job.running = false
      session.setJob("stand", false)
    }
  }

  async function saveFort() {
    const campaign = session.campaign
    if (!campaign || session.busy) return
    session.setBusy(true)
    try {
      while (fortMove.current.running) {
        await new Promise((resolve) => window.setTimeout(resolve, 40))
      }
      const revision = Math.max(campaign.revision, fortMove.current.revision)
      try {
        const saved = await confirmCampaignPlacement(campaign.id, revision)
        fortMove.current.revision = saved.revision
        session.accept(saved, true)
        if (session.mounted.current) session.setErrors({})
      } catch (error: unknown) {
        const fresh = await getCampaign(campaign.id).catch(() => null)
        if (!fresh || !session.mounted.current) throw error
        fortMove.current.revision = fresh.revision
        session.accept(fresh, true)
        if (prepOf(fresh) === "fort" && error instanceof ApiError && error.status === 409) {
          const saved = await confirmCampaignPlacement(campaign.id, fresh.revision)
          fortMove.current.revision = saved.revision
          session.accept(saved, true)
          if (session.mounted.current) session.setErrors({})
          return
        }
        if (prepOf(fresh) !== "fort") {
          if (session.mounted.current) session.setErrors({})
          return
        }
        throw error
      }
    } catch (error: unknown) {
      if (session.mounted.current) session.setErrors(presentError(error, "prepFortFailed"))
    } finally {
      if (session.mounted.current) session.setBusy(false)
    }
  }

  function dropPiece(id: string, cell: { q: number; r: number }) {
    selection.skipClick.current = true
    queueMicrotask(() => {
      selection.skipClick.current = false
    })
    selection.setSelectedToken(id)
    void placePiece(cell, id)
  }

  function placePiece(cell: { q: number; r: number }, armyId?: string) {
    queueStand(cell, armyId)
  }

  return { placeFort, queueRoad, finishRoadStep, saveFort, dropPiece, placePiece }
}

export type Preparation = ReturnType<typeof usePreparation>
