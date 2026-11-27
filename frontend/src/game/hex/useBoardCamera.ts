import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react"

import { hexCenter } from "./geometry"
import type { FocusSpot } from "./boardTypes"

const ZOOMS = [0.5, 0.75, 1, 1.5, 2, 2.5, 3]

function adjacentZoom(current: number, direction: -1 | 1): number {
  const index = ZOOMS.findIndex((step) => step >= current - 0.001)
  const at = index === -1 ? ZOOMS.length - 1 : index
  return ZOOMS[Math.min(ZOOMS.length - 1, Math.max(0, at + direction))]
}

export function useBoardCamera({
  svgRef,
  extentCount,
  focusSpot,
  mapTools,
  sizeRef,
}: {
  svgRef: RefObject<SVGSVGElement | null>
  extentCount: number
  focusSpot: FocusSpot | null
  mapTools: boolean
  sizeRef: RefObject<number>
}) {
  const [zoom, setZoom] = useState(1)
  const [grid, setGrid] = useState(mapTools)
  const [showTerritories, setShowTerritories] = useState(mapTools)
  const viewportRef = useRef<HTMLDivElement>(null)
  const centeredZoom = useRef<number | null>(null)

  useEffect(() => {
    const viewport = viewportRef.current
    const board = svgRef.current
    if (!viewport || !board || centeredZoom.current === zoom) return
    const center = () => {
      if (board.scrollWidth === 0) return
      centeredZoom.current = zoom
      viewport.scrollLeft = Math.max(0, (board.scrollWidth - viewport.clientWidth) / 2)
      viewport.scrollTop = Math.max(0, (board.scrollHeight - viewport.clientHeight) / 2)
    }
    center()
    const frame = requestAnimationFrame(center)
    return () => cancelAnimationFrame(frame)
  }, [zoom, extentCount, svgRef])

  useLayoutEffect(() => {
    if (!focusSpot) return
    const viewport = viewportRef.current
    const svg = svgRef.current
    if (!viewport || !svg) return
    const local = hexCenter(focusSpot.q, focusSpot.r, sizeRef.current)
    const point = svg.createSVGPoint()
    point.x = local.x
    point.y = local.y
    const matrix = svg.getScreenCTM()
    if (!matrix) return
    const screen = point.matrixTransform(matrix)
    const box = viewport.getBoundingClientRect()
    viewport.scrollTo({
      left: Math.max(0, viewport.scrollLeft + screen.x - box.left - box.width / 2),
      top: Math.max(0, viewport.scrollTop + screen.y - box.top - box.height / 2),
      behavior: "smooth",
    })
  }, [focusSpot, sizeRef, svgRef])

  return {
    zoom,
    grid,
    showTerritories,
    viewportRef,
    zoomOutDisabled: zoom <= ZOOMS[0],
    zoomInDisabled: zoom >= ZOOMS[ZOOMS.length - 1],
    zoomOut: () => setZoom((value) => adjacentZoom(value, -1)),
    zoomIn: () => setZoom((value) => adjacentZoom(value, 1)),
    fit: () => setZoom(1),
    toggleGrid: () => setGrid((value) => !value),
    toggleTerritories: () => setShowTerritories((value) => !value),
  }
}
