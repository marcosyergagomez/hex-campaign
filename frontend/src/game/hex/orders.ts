/** Plan a march the same way the server spends movement: you pay to leave a hex. */

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

const IMPASSABLE = new Set(["montana_rocosa", "lago", "acantilado"])
const EXIT: Record<string, number> = {
  llanura: 1,
  colina: 2,
  bosque: 2,
  bosque_profundo: 3,
  montana: 3,
  desierto: 1,
  tundra: 2,
  rio: 3,
  pantano: 3,
  playa: 1,
  mina: 1,
  campo: 1,
}

export function spotKey(spot: Spot): string {
  return `${spot.q},${spot.r}`
}

export function moveBudget(movement: number, kind: "army" | "explorer"): number {
  return movement + (kind === "explorer" ? 2 : 0)
}

/** How far a token sees from the ground it stands on. Mirrors the server. */
export function gazeReach(ground: string | undefined, explorer: boolean): number {
  const base = ground === "colina" ? 3 : ground === "montana" ? 4 : ground === "bosque_profundo" ? 0 : 2
  return base + (explorer ? 1 : 0)
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
  const extra = search(walked.at, walked.budget, walked.paid, input.target, input)
  if (!extra) return null
  return [...input.path, ...extra]
}

function adjacent(left: Spot, right: Spot): boolean {
  return STEPS.some((step) => left.q + step.q === right.q && left.r + step.r === right.r)
}

function exitCost(plot: OrderPlot | undefined): number {
  if (!plot?.known) return 1
  if (plot.road || plot.bridge) return 1
  return EXIT[plot.ground ?? ""] ?? 1
}

function refund(plot: OrderPlot | undefined): number {
  if (!plot?.known || !plot.road || !plot.ground) return 0
  return plot.ground === "llanura" || plot.ground === "playa" || plot.ground === "rio" ? 0 : 1
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
  return !(plot?.known && plot.ground && IMPASSABLE.has(plot.ground))
}

function walk(
  origin: Spot,
  path: Spot[],
  budget: number,
  paid: number,
  plots: Map<string, OrderPlot>,
): { at: Spot; budget: number; paid: number } | null {
  let at = origin
  for (const step of path) {
    if (!adjacent(at, step)) return null
    const stood = plots.get(spotKey(at))
    const cost = exitCost(stood)
    while (paid < cost) {
      if (budget <= 0) return null
      budget -= 1
      paid += 1
    }
    budget += refund(stood)
    paid = 0
    at = step
  }
  return { at, budget, paid }
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
      while (progress < cost) {
        if (left <= 0) {
          left = -1
          break
        }
        left -= 1
        progress += 1
      }
      if (left < 0) continue
      const path = [...node.path, next]
      if (next.q === target.q && next.r === target.r) return path
      if (input.blocked.has(spotKey(next))) continue
      const after = left + refund(stood)
      const mark = `${spotKey(next)}:${after}:0`
      if (seen.has(mark)) continue
      seen.add(mark)
      queue.push({ at: next, budget: after, paid: 0, path })
    }
  }
  return null
}
