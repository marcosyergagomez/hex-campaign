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
  return terrainChains(cells, new Set(["rio"]))
}

type Point = { x: number; y: number }
type RiverPoint = Point & { cell: Mark | undefined }

function riverCourses(cells: Mark[], size: number): RiverPoint[][] {
  const byPosition = new Map(cells.map((cell) => [key(cell), cell]))
  const byCenter = new Map(cells.map((cell) => [`${cell.x.toFixed(1)},${cell.y.toFixed(1)}`, cell]))
  const courses = riverChains(cells).map((line) =>
    line.split(" ").map((point) => {
      const [x, y] = point.split(",").map(Number)
      const cell = byCenter.get(point)
      return { x: cell?.x ?? x, y: cell?.y ?? y, cell }
    }),
  )
  const isolated = cells.filter((cell) => cell.ground === "rio" && !EDGE_STEPS.some(
    ([q, r]) => byPosition.get(`${cell.q + q},${cell.r + r}`)?.ground === "rio",
  ))
  for (const cell of isolated) {
    courses.push([{ x: cell.x - size / 2, y: cell.y, cell }, { x: cell.x + size / 2, y: cell.y, cell }])
  }
  for (const course of courses) {
    for (const atStart of [false, true]) {
      const tip = course[atStart ? 0 : course.length - 1]
      if (!tip.cell) continue
      const cell = tip.cell
      const lake = EDGE_STEPS.map(([q, r]) => byPosition.get(`${cell.q + q},${cell.r + r}`))
        .find((other) => other?.ground === "lago")
      if (lake) {
        const point = { x: lake.x, y: lake.y, cell: lake }
        if (atStart) course.unshift(point)
        else course.push(point)
      } else if (course.length > 1) {
        const inside = course[atStart ? 1 : course.length - 2]
        const dx = tip.x - inside.x
        const dy = tip.y - inside.y
        const exits = EDGE_STEPS.filter(([q, r]) => !byPosition.has(`${cell.q + q},${cell.r + r}`))
        exits.sort(([aq, ar], [bq, br]) =>
          (bq + br / 2) * Math.sqrt(3) * dx + br * 1.5 * dy
          - ((aq + ar / 2) * Math.sqrt(3) * dx + ar * 1.5 * dy),
        )
        if (exits.length) {
          const [q, r] = exits[0]
          const point = { x: cell.x + size * Math.sqrt(3) * (q + r / 2),
            y: cell.y + size * 1.5 * r, cell: undefined }
          if (atStart) course.unshift(point)
          else course.push(point)
        }
      }
    }
  }
  return courses
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
  return riverCourses(cells, size).map((course) => {
    const samples: Point[] = []
    // Interpolate through the cell centres: bridges stay on the channel.
    for (let i = 0; i < course.length - 1; i += 1) {
      const a = course[Math.max(0, i - 1)]
      const b = course[i]
      const c = course[i + 1]
      const d = course[Math.min(course.length - 1, i + 2)]
      for (let step = 0; step < 12; step += 1) {
        const t = step / 12
        const interpolate = (v0: number, v1: number, v2: number, v3: number) =>
          .5 * ((2 * v1) + (-v0 + v2) * t
            + (2 * v0 - 5 * v1 + 4 * v2 - v3) * t * t
            + (-v0 + 3 * v1 - 3 * v2 + v3) * t * t * t)
        samples.push({ x: interpolate(a.x, b.x, c.x, d.x), y: interpolate(a.y, b.y, c.y, d.y) })
      }
    }
    samples.push(course[course.length - 1])
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
      return `M${[...left, ...right.reverse()].map((p) => `${p.x},${p.y}`).join(" L")} Z`
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
