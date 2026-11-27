/** Plan a march the same way the server spends movement: you pay to leave a hex. */

import {
  EXPLORER_GAZE_BONUS,
  EXPLORER_MOVE_BONUS,
  exitCostOfGround,
  gazeOf,
  isImpassable,
  roadRefundOf,
} from "./terrainContract"

export { EXPLORER_GAZE_BONUS, EXPLORER_MOVE_BONUS }

export type Spot = { q: number; r: number }

export type OrderPlot = {
  known: boolean
  ground?: string
  road?: boolean
  bridge?: boolean
}

const STEPS: Spot[] = [
  { q: 1, r: 0 },
  { q: 1, r: -1 },
  { q: 0, r: -1 },
  { q: -1, r: 0 },
  { q: -1, r: 1 },
  { q: 0, r: 1 },
]

export function spotKey(spot: Spot): string {
  return `${spot.q},${spot.r}`
}

export function moveBudget(movement: number, kind: "army" | "explorer"): number {
  return movement + (kind === "explorer" ? EXPLORER_MOVE_BONUS : 0)
}

/** How far a token sees from the ground it stands on. Mirrors the server. */
export function gazeReach(ground: string | undefined, explorer: boolean): number {
  return gazeOf(ground) + (explorer ? EXPLORER_GAZE_BONUS : 0)
}

/** Points to leave this hex. Unknown ground is treated as plain. */
export function exitCostOf(plot: OrderPlot | undefined): number {
  return exitCost(plot)
}

export function hexDistance(left: Spot, right: Spot): number {
  return (Math.abs(left.q - right.q) + Math.abs(left.q + left.r - right.q - right.r) + Math.abs(left.r - right.r)) / 2
}

export function routeTo(input: {
  origin: Spot
  path: Spot[]
  target: Spot
  budget: number
  paid: number
  kind: "army" | "explorer"
  plots: Map<string, OrderPlot>
  board: Set<string>
  forts: Set<string>
  blocked: Set<string>
}): Spot[] | null {
  const trail = [input.origin, ...input.path]
  const back = trail.findIndex((spot) => spot.q === input.target.q && spot.r === input.target.r)
  if (back >= 0) return input.path.slice(0, back)
  const walked = walk(input.origin, input.path, input.budget, input.paid, input.plots)
  if (!walked) return null
  if (walked.stuck) return null
  const extra = search(walked.at, walked.budget, walked.paid, input.target, input)
  if (!extra) return null
  return [...input.path, ...extra]
}

function adjacent(left: Spot, right: Spot): boolean {
  return STEPS.some((step) => left.q + step.q === right.q && left.r + step.r === right.r)
}

function exitCost(plot: OrderPlot | undefined): number {
  if (!plot?.known) return 1
  return exitCostOfGround(plot.ground, plot.road === true, plot.bridge === true)
}

export function roadRefund(plot: OrderPlot | undefined): number {
  if (!plot?.known) return 0
  return roadRefundOf(plot.ground, plot.road === true)
}

function blockedStep(spot: Spot, target: Spot, blocked: Set<string>): boolean {
  return blocked.has(spotKey(spot)) && !(spot.q === target.q && spot.r === target.r)
}

function legal(
  spot: Spot,
  target: Spot,
  kind: "army" | "explorer",
  plots: Map<string, OrderPlot>,
  board: Set<string>,
  forts: Set<string>,
  blocked: Set<string>,
): boolean {
  const key = spotKey(spot)
  if (!board.has(key) || blockedStep(spot, target, blocked)) return false
  if (kind === "explorer" && forts.has(key)) return false
  const plot = plots.get(key)
  return !(plot?.known && isImpassable(plot.ground))
}

function walk(
  origin: Spot,
  path: Spot[],
  budget: number,
  paid: number,
  plots: Map<string, OrderPlot>,
): { at: Spot; budget: number; paid: number; stuck: boolean } | null {
  let at = origin
  for (let index = 0; index < path.length; index += 1) {
    const step = path[index]
    if (!adjacent(at, step)) return null
    const stood = plots.get(spotKey(at))
    const cost = exitCost(stood)
    const last = index === path.length - 1
    while (paid < cost) {
      if (budget <= 0) {
        // Server keeps the intent and the partial abono; the army has not left yet.
        return last ? { at, budget: 0, paid, stuck: true } : null
      }
      budget -= 1
      paid += 1
    }
    budget += roadRefund(stood)
    paid = 0
    at = step
  }
  return { at, budget, paid, stuck: false }
}

/** How many ordered hexes this turn actually enters. The last one may stay unpaid. */
export function stepsEntered(
  origin: Spot,
  path: Spot[],
  budget: number,
  paid: number,
  plots: Map<string, OrderPlot>,
): number {
  if (path.length === 0) return 0
  const walked = walk(origin, path, budget, paid, plots)
  if (!walked) return 0
  return walked.stuck ? path.length - 1 : path.length
}

function search(
  start: Spot,
  budget: number,
  paid: number,
  target: Spot,
  input: {
    kind: "army" | "explorer"
    plots: Map<string, OrderPlot>
    board: Set<string>
    forts: Set<string>
    blocked: Set<string>
  },
): Spot[] | null {
  if (start.q === target.q && start.r === target.r) return []
  type Node = { at: Spot; budget: number; paid: number; path: Spot[] }
  const queue: Node[] = [{ at: start, budget, paid, path: [] }]
  const seen = new Set<string>([`${spotKey(start)}:${budget}:${paid}`])
  while (queue.length > 0) {
    const node = queue.shift()
    if (!node) break
    for (const step of STEPS) {
      const next = { q: node.at.q + step.q, r: node.at.r + step.r }
      if (!legal(next, target, input.kind, input.plots, input.board, input.forts, input.blocked)) {
        continue
      }
      const stood = input.plots.get(spotKey(node.at))
      const cost = exitCost(stood)
      let left = node.budget
      let progress = node.paid
      if (left <= 0 && progress < cost) continue
      while (progress < cost && left > 0) {
        left -= 1
        progress += 1
      }
      const path = [...node.path, next]
      if (progress < cost) {
        // Partial abono toward leaving: only valid as the final click this turn.
        if (next.q === target.q && next.r === target.r && (node.budget > 0 || node.paid > 0)) {
          return path
        }
        continue
      }
      if (next.q === target.q && next.r === target.r) return path
      if (input.blocked.has(spotKey(next))) continue
      const after = left + roadRefund(stood)
      const mark = `${spotKey(next)}:${after}:0`
      if (seen.has(mark)) continue
      seen.add(mark)
      queue.push({ at: next, budget: after, paid: 0, path })
    }
  }
  return null
}
