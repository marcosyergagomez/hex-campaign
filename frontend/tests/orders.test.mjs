import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"
import ts from "typescript"

const source = await readFile(new URL("../src/game/hex/orders.ts", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
})
const {
  EXPLORER_MOVE_BONUS,
  EXPLORER_GAZE_BONUS,
  exitCostOf,
  moveBudget,
  routeTo,
  spotKey,
} = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputText).toString("base64")}`)

function plot(ground, extras = {}) {
  return { known: true, ground, road: false, bridge: false, ...extras }
}

function board(cells) {
  const plots = new Map()
  const keys = new Set()
  for (const cell of cells) {
    const key = spotKey(cell)
    keys.add(key)
    plots.set(key, plot(cell.ground, cell))
  }
  return { plots, board: keys, forts: new Set(), blocked: new Set() }
}

test("explorer bonuses match the campaign rules", () => {
  assert.equal(EXPLORER_MOVE_BONUS, 4)
  assert.equal(EXPLORER_GAZE_BONUS, 5)
  assert.equal(moveBudget(3, "army"), 3)
  assert.equal(moveBudget(3, "explorer"), 7)
})

test("deep woods can be ordered with movement 2 via a partial exit payment", () => {
  const deep = { q: 0, r: 0, ground: "bosque_profundo" }
  const plains = { q: 1, r: 0, ground: "llanura" }
  const world = board([deep, plains])
  assert.equal(exitCostOf(world.plots.get(spotKey(deep))), 3)
  const path = routeTo({
    origin: deep,
    path: [],
    target: plains,
    budget: 2,
    paid: 0,
    kind: "army",
    ...world,
  })
  assert.deepEqual(path, [{ q: 1, r: 0 }])
})

test("a carried abono finishes the deep woods exit when the rest is paid", () => {
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
  assert.deepEqual(path, [{ q: 1, r: 0 }])
})

test("a full plain march still spends one point per exit", () => {
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
  assert.deepEqual(path, [{ q: 1, r: 0 }, { q: 2, r: 0 }])
})
