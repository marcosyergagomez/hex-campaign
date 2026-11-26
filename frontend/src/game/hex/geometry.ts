/** Pointy-top axial hexes. Size is the distance from the center to a vertex. */

export function hexCenter(q: number, r: number, size: number): { x: number; y: number } {
  return {
    x: size * Math.sqrt(3) * (q + r / 2),
    y: size * 1.5 * r,
  }
}

export function hexPoints(size: number): string {
  return Array.from({ length: 6 }, (_, index) => {
    const angle = (Math.PI / 3) * index - Math.PI / 6
    const x = size * Math.cos(angle)
    const y = size * Math.sin(angle)
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(" ")
}
