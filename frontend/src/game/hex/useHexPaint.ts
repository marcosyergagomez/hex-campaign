import { useCallback, useEffect, useRef, type MutableRefObject, type RefObject } from "react"

import type { MapCell } from "../../api"
import { hexLine } from "./disk"
import { axialFromPixel } from "./geometry"

type Spot = { q: number; r: number }
type Paintable = MapCell | Spot

/** Freehand painting for the map editor. Isolated from HexBoard rendering. */
export function useHexPaint(
  onPaint: ((cells: Paintable[]) => void) | undefined,
  svgRef: RefObject<SVGSVGElement | null>,
  byKey: MutableRefObject<Map<string, Paintable>>,
  sizeRef: MutableRefObject<number>,
) {
  const painting = useRef(false)
  const painted = useRef(new Set<string>())
  const lastHex = useRef<Spot | null>(null)
  const onPaintRef = useRef(onPaint)
  onPaintRef.current = onPaint

  const emitPaint = useCallback((batch: Paintable[]) => {
    if (!batch.length || !onPaintRef.current) return
    onPaintRef.current(batch)
  }, [])

  const paintStroke = useCallback((target: Spot, bridgeFromLast: boolean) => {
    if (!onPaintRef.current || !painting.current) return
    const origin = bridgeFromLast ? lastHex.current : null
    lastHex.current = { q: target.q, r: target.r }
    const line = origin ? hexLine(origin, target) : [target]
    const batch: Paintable[] = []
    for (const spot of line) {
      const key = `${spot.q},${spot.r}`
      if (painted.current.has(key)) continue
      const cell = byKey.current.get(key)
      if (!cell) continue
      painted.current.add(key)
      batch.push(cell)
    }
    emitPaint(batch)
  }, [byKey, emitPaint])

  const paintAt = useCallback((clientX: number, clientY: number) => {
    if (!onPaintRef.current || !painting.current) return
    const svg = svgRef.current
    if (!svg) return
    const matrix = svg.getScreenCTM()
    if (!matrix) return
    const point = svg.createSVGPoint()
    point.x = clientX
    point.y = clientY
    const local = point.matrixTransform(matrix.inverse())
    const axial = axialFromPixel(local.x, local.y, sizeRef.current)
    if (!byKey.current.has(`${axial.q},${axial.r}`)) return
    paintStroke(axial, true)
  }, [byKey, paintStroke, sizeRef, svgRef])

  const endPaint = useCallback(() => {
    painting.current = false
    painted.current.clear()
    lastHex.current = null
  }, [])

  const beginPaint = useCallback((cell: Paintable) => {
    painting.current = true
    painted.current.clear()
    lastHex.current = null
    paintStroke(cell, false)
  }, [paintStroke])

  useEffect(() => {
    if (!onPaint) return
    const move = (event: PointerEvent) => {
      if (!painting.current) return
      if (event.buttons !== 0 && (event.buttons & 1) === 0) return
      paintAt(event.clientX, event.clientY)
    }
    const up = () => endPaint()
    window.addEventListener("pointermove", move)
    window.addEventListener("pointerup", up)
    window.addEventListener("pointercancel", up)
    return () => {
      window.removeEventListener("pointermove", move)
      window.removeEventListener("pointerup", up)
      window.removeEventListener("pointercancel", up)
    }
  }, [onPaint, paintAt, endPaint])

  return { beginPaint }
}
