import { useLayoutEffect, useRef, type RefObject } from "react"

import { hexCenter } from "./geometry"
import { HOP_MS, type MarchPath } from "./useMarchFilm"

/** Moves token nodes along a resolved march. The schedule lives in useMarchFilm. */
export function useMarchGlide(
  layer: RefObject<SVGGElement | null>,
  march: MarchPath[] | null,
  marchKey: string,
  size: number,
) {
  const marchRef = useRef(march)
  const keyRef = useRef(marchKey)
  const sizeRef = useRef(size)
  marchRef.current = march
  keyRef.current = marchKey
  sizeRef.current = size
  const clock = useRef<{ key: string; started: number } | null>(null)
  useLayoutEffect(() => {
    const host = layer.current
    const moves = marchRef.current
    const key = keyRef.current
    const hex = sizeRef.current
    if (!host || !moves || moves.length === 0 || !key) {
      clock.current = null
      return
    }
    if (clock.current?.key !== key) clock.current = { key, started: performance.now() }
    const started = clock.current.started
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const tracks = moves.flatMap((move) => {
      const node = host.querySelector<SVGGElement>(`[data-token="${CSS.escape(move.id)}"]`)
      if (!node || move.spots.length === 0) return []
      const costs = move.costs.length === move.spots.length - 1
        ? move.costs
        : move.spots.slice(0, -1).map(() => 1)
      return [{
        node,
        points: move.spots.map((spot) => hexCenter(spot.q, spot.r, hex)),
        costs,
      }]
    })
    const place = (node: SVGGElement, x: number, y: number) => {
      node.setAttribute("transform", `translate(${x} ${y})`)
    }
    const draw = (now: number) => {
      let running = false
      const elapsed = now - started
      for (const track of tracks) {
        const points = track.costs.reduce((sum, cost) => sum + Math.max(1, cost), 0)
        const span = Math.max(HOP_MS, points * HOP_MS)
        const progress = reduced ? 1 : Math.min(1, elapsed / span)
        const point = pointOnPath(track.points, track.costs, progress)
        place(track.node, point.x, point.y)
        if (progress < 1) running = true
      }
      return running
    }
    if (!draw(performance.now())) return
    let frame = 0
    const loop = (now: number) => {
      if (draw(now)) frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(frame)
  })
}

function pointOnPath(
  points: { x: number; y: number }[],
  costs: number[],
  progress: number,
): { x: number; y: number } {
  const last = points[points.length - 1]
  if (points.length === 1 || progress <= 0) return points[0]
  if (progress >= 1) return last
  const weights = costs.length === points.length - 1 ? costs : points.slice(0, -1).map(() => 1)
  const total = weights.reduce((sum, cost) => sum + Math.max(1, cost), 0)
  let remain = progress * total
  for (let index = 0; index < weights.length; index += 1) {
    const weight = Math.max(1, weights[index])
    if (remain <= weight || index === weights.length - 1) {
      const rest = Math.min(1, remain / weight)
      const from = points[index]
      const to = points[index + 1]
      return {
        x: from.x + (to.x - from.x) * rest,
        y: from.y + (to.y - from.y) * rest,
      }
    }
    remain -= weight
  }
  return last
}
