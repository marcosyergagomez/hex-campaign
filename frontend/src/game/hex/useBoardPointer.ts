import { useEffect, useRef, useState, type PointerEvent, type RefObject } from "react"

import { axialFromPixel } from "./geometry"
import type { Spot } from "./boardTypes"

export type TokenPress = { id: string; x: number; y: number; armed: boolean }

export type TokenTap = { id: string; at: number }

export function useBoardPointer({
  size,
  sizeRef,
  spotAtRef,
  movableIds,
  onOrderToken,
  onTokenDrop,
}: {
  size: number
  sizeRef: RefObject<number>
  spotAtRef?: { current: ((clientX: number, clientY: number) => Spot | null) | null }
  movableIds?: ReadonlySet<string>
  onOrderToken?: (id: string, spot: Spot, phase: "down" | "move") => void
  onTokenDrop?: (id: string, spot: Spot) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const dragToken = useRef<string | null>(null)
  const tokenPress = useRef<TokenPress | null>(null)
  const tokenTap = useRef<TokenTap | null>(null)
  const [dragging, setDragging] = useState(false)

  function hexFromEvent(event: PointerEvent<SVGElement>): Spot | null {
    const svg = svgRef.current
    if (!svg) return null
    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY
    const matrix = svg.getScreenCTM()
    if (!matrix) return null
    const local = point.matrixTransform(matrix.inverse())
    return axialFromPixel(local.x, local.y, size)
  }

  useEffect(() => {
    if (!spotAtRef) return
    spotAtRef.current = (clientX, clientY) => {
      const svg = svgRef.current
      if (!svg) return null
      const rect = svg.getBoundingClientRect()
      if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) {
        return null
      }
      const point = svg.createSVGPoint()
      point.x = clientX
      point.y = clientY
      const matrix = svg.getScreenCTM()
      if (!matrix) return null
      const local = point.matrixTransform(matrix.inverse())
      return axialFromPixel(local.x, local.y, sizeRef.current)
    }
    return () => {
      spotAtRef.current = null
    }
  }, [spotAtRef, sizeRef])

  function onPointerMove(event: PointerEvent<SVGElement>) {
    const start = tokenPress.current
    if (start && !start.armed && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) {
      if (movableIds?.has(start.id) && (onOrderToken || onTokenDrop)) {
        start.armed = true
        dragToken.current = start.id
        setDragging(true)
        svgRef.current?.setPointerCapture(event.pointerId)
        if (onOrderToken) {
          const at = hexFromEvent(event)
          if (at) onOrderToken(start.id, at, "down")
        }
      }
    }
    const id = dragToken.current
    if (!id || !onOrderToken) return
    const spot = hexFromEvent(event)
    if (spot) onOrderToken(id, spot, "move")
  }

  function onPointerUp(event: PointerEvent<SVGElement>) {
    const id = dragToken.current
    const spot = id && onTokenDrop ? hexFromEvent(event) : null
    const moved = tokenPress.current?.armed === true
    dragToken.current = null
    tokenPress.current = null
    setDragging(false)
    if (id && spot && onTokenDrop && moved) onTokenDrop(id, spot)
  }

  return { svgRef, dragging, tokenPress, tokenTap, onPointerMove, onPointerUp }
}
