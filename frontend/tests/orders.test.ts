import { describe, expect, it } from "vitest"

import { EXPLORER_GAZE_BONUS, EXPLORER_MOVE_BONUS, exitCostOf, moveBudget, routeTo, spotKey } from "../src/game/hex/orders"

function plot(ground: string, extras: { road?: boolean; bridge?: boolean } = {}) {
  return { known: true, ground, road: false, bridge: false, ...extras }
}

function board(cells: { q: number; r: number; ground: string; road?: boolean; bridge?: boolean }[]) {
  const plots = new Map()
  const keys = new Set<string>()
  for (const cell of cells) {
    const key = spotKey(cell)
    keys.add(key)
    plots.set(key, plot(cell.ground, cell))
  }
  return { plots, board: keys, forts: new Set<string>(), blocked: new Set<string>() }
}

describe("order planning", () => {
  it("explorer bonuses match the campaign rules", () => {
    expect(EXPLORER_MOVE_BONUS).toBe(4)
    expect(EXPLORER_GAZE_BONUS).toBe(5)
    expect(moveBudget(3, "army")).toBe(3)
    expect(moveBudget(3, "explorer")).toBe(7)
  })

  it("deep woods can be ordered with movement 2 via a partial exit payment", () => {
    const deep = { q: 0, r: 0, ground: "bosque_profundo" }
    const plains = { q: 1, r: 0, ground: "llanura" }
    const world = board([deep, plains])
    expect(exitCostOf(world.plots.get(spotKey(deep)))).toBe(3)
    const path = routeTo({
      origin: deep,
      path: [],
      target: plains,
      budget: 2,
      paid: 0,
      kind: "army",
      ...world,
    })
    expect(path).toEqual([{ q: 1, r: 0 }])
  })

  it("a carried abono finishes the deep woods exit when the rest is paid", () => {
    const deep = { q: 0, r: 0, ground: "bosque_profundo" }
    const plains = { q: 1, r: 0, ground: "llanura" }
    const world = board([deep, plains])
    const path = routeTo({
      origin: deep,
      path: [],
      target: plains,
      budget: 2,
      paid: 2,
      kind: "army",
      ...world,
    })
    expect(path).toEqual([{ q: 1, r: 0 }])
  })

  it("a full plain march still spends one point per exit", () => {
    const a = { q: 0, r: 0, ground: "llanura" }
    const b = { q: 1, r: 0, ground: "llanura" }
    const c = { q: 2, r: 0, ground: "llanura" }
    const world = board([a, b, c])
    const path = routeTo({
      origin: a,
      path: [],
      target: c,
      budget: 2,
      paid: 0,
      kind: "army",
      ...world,
    })
    expect(path).toEqual([{ q: 1, r: 0 }, { q: 2, r: 0 }])
  })
})
