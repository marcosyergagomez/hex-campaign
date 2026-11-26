import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"
import ts from "typescript"

// Use the project's compiler so these geometry tests also run before Node's TS support.
const source = await readFile(new URL("../src/game/hex/courses.ts", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
})
const { riverPaths, riverShapes, lakeOutlines, roadPaths, territoryOutlines } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled.outputText).toString("base64")}`
)

function mark(q, r, ground, size = 28) {
  return { q, r, ground, x: size * Math.sqrt(3) * (q + r / 2), y: size * 1.5 * r }
}

test("territories merge neighbouring hexes but never absorb neutral or other players' cells", () => {
  const cells = [
    { ...mark(0, 0, "bosque"), owner_id: "red" },
    { ...mark(1, 0, "montana"), owner_id: "red" },
    { ...mark(0, 1, "llanura"), owner_id: "blue" },
    { ...mark(1, -1, "campo"), owner_id: null },
  ]
  const regions = territoryOutlines(cells, 28)
  assert.equal(regions.length, 2)
  const red = regions.find(region => region.owner_id === "red")
  assert.equal((red.outline.match(/M/g) ?? []).length, 1)
  assert.equal((red.outline.match(/Q/g) ?? []).length, 10)
  assert.equal((red.clip.match(/L/g) ?? []).length, 9)
  assert.deepEqual(territoryOutlines(cells.map(({ owner_id, ...cell }) => cell), 28), [])
})

test("territory clips preserve neutral holes, detached regions and scaling", () => {
  const ring = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1], [5, 0]]
  for (const size of [14, 28, 42]) {
    const cells = ring.map(([q, r]) => ({ ...mark(q, r, "llanura", size), owner_id: "one" }))
    const [region] = territoryOutlines(cells, size)
    assert.equal((region.clip.match(/M/g) ?? []).length, 3)
    assert.equal((region.outline.match(/M/g) ?? []).length, 3)
    const area = region.clip.split("Z").filter(part => part.trim()).reduce((total, path) => {
      const points = [...path.matchAll(/[ML]([-\d.e+]+),([-\d.e+]+)/g)].map(
        match => [Number(match[1]), Number(match[2])],
      )
      return total + points.reduce((sum, [x, y], i) => {
        const [nx, ny] = points[(i + 1) % points.length]
        return sum + x * ny - nx * y
      }, 0) / 2
    }, 0)
    assert.ok(Math.abs(Math.abs(area) - 7 * 3 * Math.sqrt(3) / 2 * size ** 2) < 1e-6)
  }
})

test("a river joins both lakes and scales with the board", () => {
  for (const size of [14, 28, 42]) {
    const cells = [
      mark(-1, 0, "lago", size), mark(0, 0, "rio", size),
      mark(1, 0, "rio", size), mark(2, 0, "lago", size),
    ]
    const paths = riverPaths(cells, size)
    assert.equal(paths.length, 1)
    assert.ok(paths[0].startsWith(`M${cells[0].x},0`))
    assert.ok(paths[0].endsWith(`L${cells[3].x},0`))
    assert.ok(!paths[0].includes("NaN"))
  }
})

test("a manually placed single river remains visible", () => {
  const paths = riverPaths([mark(0, 0, "rio")], 28)
  assert.equal(paths.length, 1)
  assert.notEqual(paths[0].split(" L")[0].slice(1), paths[0].split(" L")[1])
})

test("lake shores merge shared edges but preserve islands and separate lakes", () => {
  for (const size of [14, 28, 42]) {
    assert.equal(lakeOutlines([mark(0, 0, "lago", size), mark(1, 0, "lago", size)], size).length, 1)
    const ring = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]]
      .map(([q, r]) => mark(q, r, "lago", size))
    assert.equal(lakeOutlines(ring, size).length, 2)
    assert.equal(lakeOutlines([...ring].reverse(), size).length, 2)
    assert.equal(lakeOutlines([mark(-8, 3, "lago", size), mark(8, -3, "lago", size)], size).length, 2)
  }
})

test("riverbanks vary in width, remain reproducible and scale proportionally", () => {
  const cells = [mark(0, 0, "rio"), mark(1, 0, "rio"), mark(2, -1, "rio"), mark(3, -1, "lago")]
  const shapes = riverShapes(cells, 28)
  assert.deepEqual(shapes, riverShapes([...cells].reverse(), 28))
  const shape = shapes[0]
  assert.ok(Math.max(...shape.widths) / Math.min(...shape.widths) > 1.3)
  for (const path of [shape.banks, shape.channel, shape.current]) {
    assert.ok(path.endsWith(" Z"))
    assert.ok(!/NaN|Infinity/.test(path))
  }
  const small = riverShapes(cells.map(c => mark(c.q, c.r, c.ground, 14)), 14)[0]
  assert.deepEqual(small.widths, shape.widths.map(width => width / 2))
})

test("river mouths on the map boundary continue past the last cell instead of ending in a cap", () => {
  const cells = [mark(0, 0, "lago"), mark(1, 0, "rio"), mark(2, 0, "rio")]
  const channel = riverShapes(cells, 28)[0].channel
  const xs = [...channel.matchAll(/(?:M|L)([-\d.e+]+),/g)].map(match => Number(match[1]))
  assert.ok(Math.max(...xs) > cells[2].x + 28)
})

test("river branches share the junction instead of leaving a gap", () => {
  // Arms on non-adjacent bearings so the junction is a true Y, not a triangle.
  const cells = [
    mark(0, 0, "rio"),
    mark(1, 0, "rio"),
    mark(-1, 1, "rio"),
    mark(0, -1, "rio"),
  ]
  const shapes = riverShapes(cells, 28)
  assert.equal(shapes.length, 3)
  const junction = cells[0]
  for (const shape of shapes) {
    const points = [...shape.channel.matchAll(/(?:M|L)([-\d.e+]+),([-\d.e+]+)/g)].map(
      match => [Number(match[1]), Number(match[2])],
    )
    // Ribbon outline is offset from the centreline by the channel width.
    assert.ok(points.some(([x, y]) => Math.hypot(x - junction.x, y - junction.y) < 28 * 0.45))
  }
})

test("a sharp hex bend stays near the corridor instead of looping wide", () => {
  const size = 28
  const riverAt = new Set(["0,0", "1,0", "1,1"])
  const cells = []
  for (let q = -1; q <= 2; q += 1) {
    for (let r = -1; r <= 2; r += 1) {
      cells.push(mark(q, r, riverAt.has(`${q},${r}`) ? "rio" : "llanura", size))
    }
  }
  const river = cells.filter(cell => cell.ground === "rio")
  const channel = riverShapes(cells, size)[0].channel
  const points = [...channel.matchAll(/(?:M|L)([-\d.e+]+),([-\d.e+]+)/g)].map(
    match => [Number(match[1]), Number(match[2])],
  )
  const segments = [[river[0], river[1]], [river[1], river[2]]]
  for (const [x, y] of points) {
    let lateral = Infinity
    for (const [a, b] of segments) {
      const dx = b.x - a.x
      const dy = b.y - a.y
      const len2 = dx * dx + dy * dy || 1
      const t = ((x - a.x) * dx + (y - a.y) * dy) / len2
      if (t < 0 || t > 1) continue
      lateral = Math.min(lateral, Math.hypot(x - (a.x + dx * t), y - (a.y + dy * t)))
    }
    if (lateral === Infinity) continue
    // Ignore the ribbon half-width; fail only on true spline overshoot.
    assert.ok(lateral < size * 0.55, `sample drifted ${lateral} from the river corridor`)
  }
})

test("roads draw every arm of a junction, but never connect through ordinary ground", () => {
  const cells = [[0, 0], [1, 0], [-1, 1], [0, -1]]
    .map(([q, r]) => ({ ...mark(q, r, "bosque"), road: true }))
  cells.push({ ...mark(0, 1, "llanura"), road: false })
  assert.equal(roadPaths(cells, 28).length, 3)
  assert.deepEqual(roadPaths(cells, 28), roadPaths([...cells].reverse(), 28))
  const lone = [{ ...mark(0, 0, "montana"), road: true }, cells[4]]
  assert.equal(roadPaths(lone, 28).length, 1)
  assert.ok(!roadPaths(lone, 28)[0].includes("NaN"))
})

test("a road approaches a fortress without painting a road through its courtyard", () => {
  const fort = { ...mark(0, 0, "llanura"), road: false }
  const road = { ...mark(1, 0, "bosque"), road: true }
  const paths = roadPaths([fort, road], 28, [fort])
  assert.equal(paths.length, 1)
  const endpoint = paths[0].split(" ").at(-1).split(",").map(Number)
  assert.ok(endpoint[0] > fort.x)
  assert.ok(endpoint[0] < road.x)
})

test("roads avoid triangular meshes while preserving junctions and longer loops", () => {
  const triangle = [[0, 0], [1, 0], [0, 1]]
    .map(([q, r]) => ({ ...mark(q, r, "bosque"), road: true }))
  const paths = roadPaths(triangle, 28)
  assert.equal(paths.length, 2)
  assert.deepEqual(paths, roadPaths([...triangle].reverse(), 28))
  for (const cell of triangle) {
    assert.ok(paths.some(path => path.startsWith(`M${cell.x},${cell.y} `)
      || path.endsWith(` ${cell.x},${cell.y}`)))
  }
  const loop = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]]
    .map(([q, r]) => ({ ...mark(q, r, "llanura"), road: true }))
  assert.equal(roadPaths(loop, 28).length, 6)
})
