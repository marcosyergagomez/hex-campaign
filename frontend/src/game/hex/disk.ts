/** Pointy-top axial disk helpers for the map editor. */

import { hexRound } from "./geometry"

const STEPS: readonly [number, number][] = [
  [1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1],
]

export type Axial = { q: number; r: number }

export function diskRadius(size: number): number | null {
  for (let radius = 2; radius <= 64; radius += 1) {
    if (1 + 3 * radius * (radius + 1) === size) return radius
  }
  return null
}

export function axialKey(cell: Axial): string {
  return `${cell.q},${cell.r}`
}

export function diskCells(size: number): Axial[] {
  const radius = diskRadius(size)
  if (radius === null) return []
  const cells: Axial[] = []
  for (let q = -radius; q <= radius; q += 1) {
    for (let r = -radius; r <= radius; r += 1) {
      if ((Math.abs(q) + Math.abs(q + r) + Math.abs(r)) / 2 <= radius) {
        cells.push({ q, r })
      }
    }
  }
  return cells
}

export function neighbors(cell: Axial): Axial[] {
  return STEPS.map(([dq, dr]) => ({ q: cell.q + dq, r: cell.r + dr }))
}

export function brushCells(cell: Axial, area: boolean): Axial[] {
  if (!area) return [cell]
  return [cell, ...neighbors(cell)]
}

export function hexDistance(a: Axial, b: Axial): number {
  return (Math.abs(a.q - b.q) + Math.abs(a.q + a.r - b.q - b.r) + Math.abs(a.r - b.r)) / 2
}

/** Inclusive axial line so fast strokes do not skip hexes between samples. */
export function hexLine(a: Axial, b: Axial): Axial[] {
  const n = hexDistance(a, b)
  if (n === 0) return [{ q: a.q, r: a.r }]
  const line: Axial[] = []
  for (let i = 0; i <= n; i += 1) {
    const t = i / n
    line.push(hexRound(a.q + (b.q - a.q) * t, a.r + (b.r - a.r) * t))
  }
  return line
}
