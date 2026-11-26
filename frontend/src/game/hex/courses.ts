/** Continuous strokes so a river, a shore and a ridge read across hex borders. */

export type Mark = { q: number; r: number; ground: string; x: number; y: number }

// Edge i of a pointy-top hex faces this axial step. Edge 0 looks east.
const EDGE_STEPS: readonly (readonly [number, number])[] = [
  [1, 0],
  [0, 1],
  [-1, 1],
  [-1, 0],
  [0, -1],
  [1, -1],
]

const WATER = new Set(["rio", "lago"])
const RIDGE = new Set(["montana", "montana_rocosa"])

export function roadPaths(
  cells: (Mark & { road: boolean })[],
  size: number,
  anchors: { q: number; r: number }[] = [],
): string[] {
  const forts = new Set(anchors.map(key))
  const roads = new Map(cells.filter((cell) => cell.road || forts.has(key(cell)))
    .map((cell) => [key(cell), cell]))
  const paths: string[] = []
  const connections = new Map<string, Set<string>>()
  for (const cell of [...roads.values()].sort((a, b) => a.q - b.q || a.r - b.r)) {
    if (!cell.road) continue
    const adjacent = linked(cell, roads)
    for (const other of adjacent) {
      if (other.road && key(cell) > key(other)) continue
      const from = connections.get(key(cell)) ?? new Set<string>()
      const to = connections.get(key(other)) ?? new Set<string>()
      // Adjacent road hexes can form a tiny triangle without being three separate routes.
      if ([...from].some((neighbor) => to.has(neighbor))) continue
      from.add(key(other))
      to.add(key(cell))
      connections.set(key(cell), from)
      connections.set(key(other), to)
      const dx = other.x - cell.x
      const dy = other.y - cell.y
      // Keep the road out of the fortress courtyard, whose normal exit still costs a point.
      const reach = other.road ? 1 : .72
      paths.push(`M${cell.x},${cell.y} Q${cell.x + dx * .5 - dy * .045},${cell.y + dy * .5 + dx * .045} ${cell.x + dx * reach},${cell.y + dy * reach}`)
    }
    if (!adjacent.length) {
      paths.push(`M${cell.x - size * .35},${cell.y} Q${cell.x},${cell.y - size * .1} ${cell.x + size * .35},${cell.y}`)
    }
  }
  return paths
}

export function terrainChains(cells: Mark[], grounds: Set<string>): string[] {
  const want = new Map<string, Mark>()
  for (const cell of cells) {
    if (grounds.has(cell.ground)) {
      want.set(key(cell), cell)
    }
  }
  const seen = new Set<string>()
  const paths: string[] = []
  const ordered = [...want.values()].sort((left, right) => left.q - right.q || left.r - right.r)
  for (const cell of ordered) {
    if (seen.has(key(cell))) {
      continue
    }
    const chain = walk(rewind(cell, want), want, seen)
    if (chain.length >= 2) {
      paths.push(chain.map((item) => `${item.x.toFixed(1)},${item.y.toFixed(1)}`).join(" "))
    }
  }
  return paths
}

export function shoreLines(cells: Mark[], size: number): string[] {
  const water = new Set(cells.filter((cell) => WATER.has(cell.ground)).map(key))
  const lines: string[] = []
  for (const cell of cells) {
    if (!water.has(key(cell))) {
      continue
    }
    for (let edge = 0; edge < EDGE_STEPS.length; edge += 1) {
      const [stepQ, stepR] = EDGE_STEPS[edge]
      if (water.has(`${cell.q + stepQ},${cell.r + stepR}`)) {
        continue
      }
      const start = corner(size, edge)
      const end = corner(size, edge + 1)
      const inset = 0.16
      lines.push(
        `${(cell.x + start.x * (1 - inset)).toFixed(1)},${(cell.y + start.y * (1 - inset)).toFixed(1)} ${(cell.x + end.x * (1 - inset)).toFixed(1)},${(cell.y + end.y * (1 - inset)).toFixed(1)}`,
      )
    }
  }
  return lines
}

export function riverChains(cells: Mark[]): string[] {
  return riverRuns(cells).map(run =>
    run.map(cell => `${cell.x.toFixed(1)},${cell.y.toFixed(1)}`).join(" "),
  )
}

type Point = { x: number; y: number }
type RiverPoint = Point & { cell: Mark | undefined }

function edgeKey(a: { q: number; r: number }, b: { q: number; r: number }): string {
  const left = key(a)
  const right = key(b)
  return left < right ? `${left}|${right}` : `${right}|${left}`
}

/** Path pieces between endpoints/junctions so branches meet instead of leaving gaps. */
function riverRuns(cells: Mark[]): Mark[][] {
  const want = new Map<string, Mark>()
  for (const cell of cells) {
    if (cell.ground === "rio") want.set(key(cell), cell)
  }
  const degree = (cell: Mark) => linked(cell, want).length
  const used = new Set<string>()
  const runs: Mark[][] = []
  const ordered = [...want.values()].sort((left, right) => left.q - right.q || left.r - right.r)

  function walkArm(start: Mark, first: Mark): Mark[] {
    const run = [start, first]
    used.add(edgeKey(start, first))
    let previous = start
    let current = first
    while (degree(current) === 2) {
      const next = linked(current, want).find(item => key(item) !== key(previous))
      if (!next || used.has(edgeKey(current, next))) break
      used.add(edgeKey(current, next))
      run.push(next)
      previous = current
      current = next
    }
    return run
  }

  for (const cell of ordered) {
    if (degree(cell) === 0) continue
    if (degree(cell) === 2) continue
    for (const next of linked(cell, want)) {
      if (used.has(edgeKey(cell, next))) continue
      runs.push(walkArm(cell, next))
    }
  }

  for (const cell of ordered) {
    for (const next of linked(cell, want)) {
      if (used.has(edgeKey(cell, next))) continue
      const run = walkArm(cell, next)
      while (true) {
        const head = run[0]
        const tail = run[run.length - 1]
        if (key(head) === key(tail) && run.length > 2) break
        const prev = run[run.length - 2]
        const step = linked(tail, want).find(
          item => key(item) !== key(prev) && !used.has(edgeKey(tail, item)),
        )
        if (!step) break
        used.add(edgeKey(tail, step))
        run.push(step)
        if (key(step) === key(head)) break
      }
      runs.push(run)
    }
  }

  return runs
}

function riverCourses(cells: Mark[], size: number): RiverPoint[][] {
  const byPosition = new Map(cells.map(cell => [key(cell), cell]))
  const courses: RiverPoint[][] = riverRuns(cells).map(run =>
    run.map(cell => ({ x: cell.x, y: cell.y, cell })),
  )
  const isolated = cells.filter(cell =>
    cell.ground === "rio"
    && !EDGE_STEPS.some(([q, r]) => byPosition.get(`${cell.q + q},${cell.r + r}`)?.ground === "rio"),
  )
  for (const cell of isolated) {
    courses.push([
      { x: cell.x - size * Math.sqrt(3) / 2, y: cell.y, cell },
      { x: cell.x + size * Math.sqrt(3) / 2, y: cell.y, cell },
    ])
  }
  for (const course of courses) {
    for (const atStart of [false, true]) {
      const tip = course[atStart ? 0 : course.length - 1]
      if (!tip.cell) continue
      const cell = tip.cell
      const riverAround = EDGE_STEPS
        .map(([q, r]) => byPosition.get(`${cell.q + q},${cell.r + r}`))
        .filter((other): other is Mark => other?.ground === "rio")
      // Junction tips are shared by another arm; do not stretch them past the meeting point.
      if (riverAround.length >= 2) continue
      const lake = EDGE_STEPS.map(([q, r]) => byPosition.get(`${cell.q + q},${cell.r + r}`))
        .find(other => other?.ground === "lago")
      if (lake) {
        const point = { x: lake.x, y: lake.y, cell: lake }
        if (atStart) course.unshift(point)
        else course.push(point)
        continue
      }
      if (course.length < 2) continue
      const inside = course[atStart ? 1 : course.length - 2]
      const dx = tip.x - inside.x
      const dy = tip.y - inside.y
      const exits = EDGE_STEPS.filter(([q, r]) => !byPosition.has(`${cell.q + q},${cell.r + r}`))
      exits.sort(([aq, ar], [bq, br]) =>
        (bq + br / 2) * Math.sqrt(3) * dx + br * 1.5 * dy
        - ((aq + ar / 2) * Math.sqrt(3) * dx + ar * 1.5 * dy),
      )
      let point: RiverPoint
      if (exits.length) {
        const [q, r] = exits[0]
        point = {
          x: cell.x + size * Math.sqrt(3) * (q + r / 2),
          y: cell.y + size * 1.5 * r,
          cell: undefined,
        }
      } else {
        // Interior mouth against land: reach the rim of the tip hex, not a blunt centre cap.
        const length = Math.hypot(dx, dy) || 1
        const reach = size * Math.sqrt(3) / 2
        point = {
          x: tip.x + dx / length * reach,
          y: tip.y + dy / length * reach,
          cell: undefined,
        }
      }
      if (atStart) course.unshift(point)
      else course.push(point)
    }
  }
  return courses
}

function sampleRiver(course: RiverPoint[]): Point[] {
  if (course.length === 0) return []
  if (course.length === 1) return [{ x: course[0].x, y: course[0].y }]
  const samples: Point[] = []
  // Centripetal Catmull-Rom keeps 60° hex bends from looping back on themselves.
  for (let i = 0; i < course.length - 1; i += 1) {
    const p0 = course[Math.max(0, i - 1)]
    const p1 = course[i]
    const p2 = course[i + 1]
    const p3 = course[Math.min(course.length - 1, i + 2)]
    const tj = (t: number, a: Point, b: Point) => {
      const dist = Math.hypot(b.x - a.x, b.y - a.y) || 1e-6
      return t + Math.sqrt(dist)
    }
    const t0 = 0
    const t1 = tj(t0, p0, p1)
    const t2 = tj(t1, p1, p2)
    const t3 = tj(t2, p2, p3)
    for (let step = 0; step < 12; step += 1) {
      const t = t1 + (t2 - t1) * (step / 12)
      const a1 = (t1 - t) / (t1 - t0 || 1e-6)
      const a2 = (t - t0) / (t1 - t0 || 1e-6)
      const b1 = (t2 - t) / (t2 - t1 || 1e-6)
      const b2 = (t - t1) / (t2 - t1 || 1e-6)
      const c1 = (t3 - t) / (t3 - t2 || 1e-6)
      const c2 = (t - t2) / (t3 - t2 || 1e-6)
      const d0 = { x: a1 * p0.x + a2 * p1.x, y: a1 * p0.y + a2 * p1.y }
      const d1 = { x: b1 * p1.x + b2 * p2.x, y: b1 * p1.y + b2 * p2.y }
      const d2 = { x: c1 * p2.x + c2 * p3.x, y: c1 * p2.y + c2 * p3.y }
      const e0x = ((t2 - t) / (t2 - t0 || 1e-6)) * d0.x + ((t - t0) / (t2 - t0 || 1e-6)) * d1.x
      const e0y = ((t2 - t) / (t2 - t0 || 1e-6)) * d0.y + ((t - t0) / (t2 - t0 || 1e-6)) * d1.y
      const e1x = ((t3 - t) / (t3 - t1 || 1e-6)) * d1.x + ((t - t1) / (t3 - t1 || 1e-6)) * d2.x
      const e1y = ((t3 - t) / (t3 - t1 || 1e-6)) * d1.y + ((t - t1) / (t3 - t1 || 1e-6)) * d2.y
      samples.push({
        x: ((t2 - t) / (t2 - t1 || 1e-6)) * e0x + ((t - t1) / (t2 - t1 || 1e-6)) * e1x,
        y: ((t2 - t) / (t2 - t1 || 1e-6)) * e0y + ((t - t1) / (t2 - t1 || 1e-6)) * e1y,
      })
    }
  }
  samples.push({ x: course[course.length - 1].x, y: course[course.length - 1].y })
  return samples
}

export function riverPaths(cells: Mark[], size: number): string[] {
  return riverCourses(cells, size).map((course) => {
    let path = `M${course[0].x},${course[0].y}`
    for (let i = 1; i < course.length - 1; i += 1) {
      const here = course[i]
      const next = course[i + 1]
      path += ` Q${here.x},${here.y} ${(here.x + next.x) / 2},${(here.y + next.y) / 2}`
    }
    const last = course[course.length - 1]
    return `${path} L${last.x},${last.y}`
  })
}

export function lakeOutlines(cells: Mark[], size: number): string[] {
  return terrainOutlines(cells, size, new Set(["lago"]))
}

export function terrainOutlines(cells: Mark[], size: number, grounds: Set<string>): string[] {
  return cellOutlines(cells.filter((cell) => grounds.has(cell.ground)), size)
}

export function territoryOutlines(cells: (Mark & { owner_id?: string | null })[], size: number) {
  const owners = [...new Set(cells.flatMap(cell => cell.owner_id ? [cell.owner_id] : []))].sort()
  return owners.map(owner_id => {
    const region = cells.filter(cell => cell.owner_id === owner_id)
    return {
      owner_id,
      outline: cellOutlines(region, size).join(" "),
      clip: cellOutlines(region, size, false).join(" "),
    }
  })
}

function cellOutlines(cells: Mark[], size: number, rounded = true): string[] {
  const water = new Set(cells.map(key))
  const pointKey = (point: Point) => `${Math.round(point.x * 1000)},${Math.round(point.y * 1000)}`
  const edges = new Map<string, { start: Point; end: Point }>()
  for (const cell of cells) {
    if (!water.has(key(cell))) continue
    EDGE_STEPS.forEach(([q, r], index) => {
      if (water.has(`${cell.q + q},${cell.r + r}`)) return
      const a = corner(size, index)
      const b = corner(size, index + 1)
      const start = { x: cell.x + a.x, y: cell.y + a.y }
      edges.set(pointKey(start), { start, end: { x: cell.x + b.x, y: cell.y + b.y } })
    })
  }
  const outlines: string[] = []
  while (edges.size) {
    const first = edges.values().next().value
    if (!first) break
    const points: Point[] = []
    let edge: typeof first | undefined = first
    while (edge) {
      points.push(edge.start)
      edges.delete(pointKey(edge.start))
      edge = edges.get(pointKey(edge.end))
    }
    if (!rounded) {
      outlines.push(`${points.map((point, i) => `${i === 0 ? "M" : "L"}${point.x},${point.y}`).join(" ")} Z`)
      continue
    }
    const between = (a: Point, b: Point) => `${(a.x + b.x) / 2},${(a.y + b.y) / 2}`
    let path = `M${between(points[0], points[points.length - 1])}`
    points.forEach((point, i) => {
      const next = points[(i + 1) % points.length]
      path += ` Q${point.x},${point.y} ${between(point, next)}`
    })
    outlines.push(`${path} Z`)
  }
  return outlines
}

export type RiverShape = { banks: string; channel: string; current: string; widths: number[] }

export function riverShapes(cells: Mark[], size: number): RiverShape[] {
  return riverCourses(cells, size).map(course => {
    const samples = sampleRiver(course)
    const phase = (course[0].x + course[0].y) / size
    const widths = samples.map((_, i) =>
      size * (.27 + .065 * Math.sin(i * .24 + phase) + .025 * Math.sin(i * 1.17 + phase)),
    )
    const ribbon = (factor: number) => {
      const left: Point[] = []
      const right: Point[] = []
      samples.forEach((point, i) => {
        const before = samples[Math.max(0, i - 1)]
        const after = samples[Math.min(samples.length - 1, i + 1)]
        const length = Math.hypot(after.x - before.x, after.y - before.y) || 1
        const nx = -(after.y - before.y) / length
        const ny = (after.x - before.x) / length
        const w = widths[i] * factor
        left.push({ x: point.x + nx * w, y: point.y + ny * w })
        right.push({ x: point.x - nx * w, y: point.y - ny * w })
      })
      return `M${[...left, ...right.reverse()].map(p => `${p.x},${p.y}`).join(" L")} Z`
    }
    return { banks: ribbon(1.35), channel: ribbon(1), current: ribbon(.48), widths }
  })
}

export function ridgeChains(cells: Mark[]): string[] {
  return terrainChains(cells, RIDGE)
}

function walk(start: Mark, want: Map<string, Mark>, seen: Set<string>): Mark[] {
  const chain = [start]
  seen.add(key(start))
  let previous: Mark | null = null
  let current = start
  for (;;) {
    const next = linked(current, want).find((item) => item !== previous && !seen.has(key(item)))
    if (!next) {
      return chain
    }
    chain.push(next)
    seen.add(key(next))
    previous = current
    current = next
  }
}

function rewind(cell: Mark, want: Map<string, Mark>): Mark {
  let current = cell
  let previous: Mark | null = null
  const guard = new Set<string>()
  while (!guard.has(key(current))) {
    guard.add(key(current))
    const around = linked(current, want)
    if (around.length <= 1) {
      return current
    }
    const next = around.find((item) => item !== previous)
    if (!next) {
      return current
    }
    previous = current
    current = next
  }
  return cell
}

function linked<T extends Mark>(cell: Mark, want: Map<string, T>): T[] {
  const found: T[] = []
  for (const [stepQ, stepR] of EDGE_STEPS) {
    const other = want.get(`${cell.q + stepQ},${cell.r + stepR}`)
    if (other) {
      found.push(other)
    }
  }
  return found
}

function corner(size: number, index: number): { x: number; y: number } {
  const angle = (Math.PI / 3) * (index % 6) - Math.PI / 6
  return { x: size * Math.cos(angle), y: size * Math.sin(angle) }
}

function key(cell: { q: number; r: number }): string {
  return `${cell.q},${cell.r}`
}
