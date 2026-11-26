/** Pointy-top axial hexes. Size is the distance from the center to a vertex. */

export function hexCenter(q: number, r: number, size: number): { x: number; y: number } {
  return {
    x: size * Math.sqrt(3) * (q + r / 2),
    y: size * 1.5 * r,
  }
}

export function hexRound(q: number, r: number): { q: number; r: number } {
  const s = -q - r
  let rq = Math.round(q)
  let rr = Math.round(r)
  let rs = Math.round(s)
  const dq = Math.abs(rq - q)
  const dr = Math.abs(rr - r)
  const ds = Math.abs(rs - s)
  if (dq > dr && dq > ds) rq = -rr - rs
  else if (dr > ds) rr = -rq - rs
  return { q: rq, r: rr }
}

export function axialFromPixel(x: number, y: number, size: number): { q: number; r: number } {
  const q = ((Math.sqrt(3) / 3) * x - (1 / 3) * y) / size
  const r = ((2 / 3) * y) / size
  return hexRound(q, r)
}

export function hexPoints(size: number): string {
  return Array.from({ length: 6 }, (_, index) => {
    const angle = (Math.PI / 3) * index - Math.PI / 6
    const x = size * Math.cos(angle)
    const y = size * Math.sin(angle)
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(" ")
}
