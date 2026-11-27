import { useCallback, useEffect, useMemo, useState } from "react"

import type { CampaignDetail, CampaignHex } from "../../api"
import { exitCostOf, spotKey, type Spot } from "./orders"

/** Milliseconds spent paying one movement point. A harder exit takes longer. */
export const HOP_MS = 440

const filmHolds = new Set<string>()
const filmListeners = new Set<() => void>()

export type MarchPath = { id: string; spots: Spot[]; costs: number[] }

export function battleFilmHeld(campaignId: string): boolean {
  return filmHolds.has(campaignId)
}

export function subscribeBattleFilm(listener: () => void): () => void {
  filmListeners.add(listener)
  return () => {
    filmListeners.delete(listener)
  }
}

export function setBattleFilm(campaignId: string, playing: boolean): void {
  const held = filmHolds.has(campaignId)
  if (playing) filmHolds.add(campaignId)
  else filmHolds.delete(campaignId)
  if (held !== filmHolds.has(campaignId)) {
    for (const listener of filmListeners) listener()
  }
}

export function marchMs(costs: number[]): number {
  const points = costs.reduce((sum, cost) => sum + Math.max(1, cost), 0)
  return points * HOP_MS
}

function leaveCosts(spots: Spot[], hexes: CampaignHex[]): number[] {
  const plots = new Map(hexes.map((cell) => [
    spotKey(cell),
    cell.known
      ? { known: true as const, ground: cell.ground, road: cell.road, bridge: cell.bridge }
      : { known: false as const },
  ]))
  return spots.slice(0, -1).map((spot) => exitCostOf(plots.get(spotKey(spot))))
}

function trail(from: Spot, steps: Spot[]): Spot[] {
  const spots: Spot[] = []
  for (const spot of [from, ...steps]) {
    const prev = spots[spots.length - 1]
    if (prev && prev.q === spot.q && prev.r === spot.r) continue
    spots.push(spot)
  }
  return spots
}

/** Replay the resolved march once per turn, from the hex each token left. */
export function useMarchFilm(campaign: CampaignDetail | null): {
  playing: boolean
  paths: MarchPath[] | null
  canReplay: boolean
  replay: () => void
} {
  const turn = campaign?.playback.turn ?? 0
  const moves = campaign?.playback.moves
  const hexes = campaign?.hexes
  const paths = useMemo(() => {
    if (!moves || !hexes) return []
    return moves.flatMap((move) => {
      const spots = trail(move.from, move.steps)
      if (spots.length < 2) return []
      const costs = move.costs && move.costs.length === spots.length - 1
        ? move.costs
        : leaveCosts(spots, hexes)
      return [{ id: move.army_id, spots, costs }]
    })
  }, [moves, hexes])
  const signature = campaign && paths.length > 0
    ? `${campaign.id}:${turn}:${paths.map((path) => `${path.id}:${path.spots.length}`).join(",")}`
    : ""
  const storageKey = signature ? `hex-march:${signature}` : ""
  const seen = storageKey !== "" && sessionStorage.getItem(storageKey) === "1"
  const wanted = signature !== "" && !seen
  const [play, setPlay] = useState({ key: "", done: "" })
  if (wanted && play.key !== signature) {
    setPlay({ key: signature, done: "" })
  }
  const playing = wanted && play.done !== signature
  const duration = paths.reduce((longest, path) => Math.max(longest, marchMs(path.costs)), 0)

  useEffect(() => {
    if (!playing || !storageKey) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const timer = window.setTimeout(() => {
      sessionStorage.setItem(storageKey, "1")
      setPlay((current) => (current.key === signature ? { ...current, done: signature } : current))
    }, reduced ? 32 : duration + 32)
    return () => window.clearTimeout(timer)
  }, [playing, duration, storageKey, signature])

  const replay = useCallback(() => {
    if (!signature) return
    setPlay((current) => {
      if (current.key === signature && current.done !== signature) return current
      if (storageKey) sessionStorage.removeItem(storageKey)
      return { key: signature, done: "" }
    })
  }, [signature, storageKey])

  if (!playing) return { playing: false, paths: null, canReplay: signature !== "", replay }
  return { playing: true, paths, canReplay: false, replay }
}
