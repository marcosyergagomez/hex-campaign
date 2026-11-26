import { useEffect, useState } from "react"

import type { CampaignDetail } from "../../api"
import type { Spot } from "./orders"

export const STEP_MS = 680

const filmHolds = new Set<string>()
const filmListeners = new Set<() => void>()

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

/** Replay the resolved march once per turn, from the hex each token left. */
export function useMarchFilm(campaign: CampaignDetail | null): {
  playing: boolean
  spots: Record<string, Spot> | null
} {
  const moves = campaign?.playback.moves ?? []
  const max = moves.reduce((longest, move) => Math.max(longest, move.steps.length), 0)
  const signature = campaign
    ? `${campaign.id}:${campaign.playback.turn}:${moves.length}:${max}`
    : ""
  const storageKey = campaign && campaign.playback.turn > 0
    ? `hex-march:${campaign.id}:${campaign.playback.turn}`
    : ""
  const seen = storageKey !== "" && sessionStorage.getItem(storageKey) === "1"
  // Abonos sin cambio de hex no deben bloquear la mesa con una película vacía.
  const wanted = Boolean(
    campaign && campaign.playback.turn > 0 && moves.length > 0 && max > 0 && !seen,
  )
  const [play, setPlay] = useState({ key: "", frame: 0, done: "" })
  if (wanted && play.key !== signature) {
    setPlay({ key: signature, frame: 0, done: "" })
  }
  const playing = wanted && play.done !== signature
  const frame = play.key === signature ? play.frame : 0

  useEffect(() => {
    if (!playing || max === 0 || frame >= max) return
    const timer = window.setTimeout(() => {
      setPlay((current) =>
        current.key === signature ? { ...current, frame: current.frame + 1 } : current,
      )
    }, STEP_MS)
    return () => window.clearTimeout(timer)
  }, [playing, frame, max, signature])

  useEffect(() => {
    if (!playing || !storageKey || frame < max) return
    sessionStorage.setItem(storageKey, "1")
    setPlay((current) => (current.key === signature ? { ...current, done: signature } : current))
  }, [playing, frame, max, storageKey, signature])

  if (!playing) return { playing: false, spots: null }
  const spots: Record<string, Spot> = {}
  for (const move of moves) {
    const index = Math.min(frame, move.steps.length) - 1
    spots[move.army_id] = index < 0 ? move.from : move.steps[index]
  }
  return { playing: true, spots }
}
