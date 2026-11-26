import type { CampaignArmy } from "../api"

type Spot = { q: number; r: number }

const STEPS: Spot[] = [
  { q: 1, r: 0 },
  { q: 1, r: -1 },
  { q: 0, r: -1 },
  { q: -1, r: 0 },
  { q: -1, r: 1 },
  { q: 0, r: 1 },
]

function key(spot: Spot): string {
  return `${spot.q},${spot.r}`
}

function nearestFree(
  origin: Spot,
  taken: Set<string>,
  home: Set<string>,
  standable: Set<string>,
): Spot | null {
  const queue = [origin]
  const seen = new Set<string>([key(origin)])
  while (queue.length > 0) {
    const current = queue.shift()
    if (!current) break
    for (const step of STEPS) {
      const next = { q: current.q + step.q, r: current.r + step.r }
      const id = key(next)
      if (seen.has(id) || !home.has(id)) continue
      seen.add(id)
      queue.push(next)
      if (!taken.has(id) && standable.has(id)) return next
    }
  }
  return null
}

/** Fortress click seats each army on a different home hex, and the explorer beside them. */
export function seatAroundFort(
  fort: Spot,
  home: Set<string>,
  armies: CampaignArmy[],
  standable: Set<string> = home,
): Record<string, Spot> | null {
  const fortKey = key(fort)
  if (!home.has(fortKey)) return null
  const taken = new Set<string>([fortKey])
  const spots: Record<string, Spot> = {}
  const fighters = armies.filter((army) => army.kind === "army" && !army.destroyed)
  const explorers = armies.filter((army) => army.kind === "explorer" && !army.destroyed)
  fighters.forEach((army, index) => {
    if (index === 0) {
      spots[army.id] = fort
      return
    }
    const next = nearestFree(fort, taken, home, standable)
    if (!next) return
    taken.add(key(next))
    spots[army.id] = next
  })
  if (Object.keys(spots).length !== fighters.length) return null
  for (const explorer of explorers) {
    const next = nearestFree(fort, taken, home, standable)
    if (!next) return null
    taken.add(key(next))
    spots[explorer.id] = next
  }
  return spots
}
