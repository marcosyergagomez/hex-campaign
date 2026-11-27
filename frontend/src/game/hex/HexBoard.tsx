import { useId, useRef } from "react"

import { useI18n } from "../../i18n/language"
import { BoardTools } from "./BoardTools"
import {
  markTint,
  NO_CLASHES,
  NO_PATHS,
  NO_PLAYERS,
  NO_SPOTS,
  NO_TOKENS,
  NO_TRACES,
  SIZE,
  type HexBoardProps,
  type OwnedCell,
  type Spot,
} from "./boardTypes"
import { HexTerrainLayer, useTerrainScene, type BoardPick } from "./HexTerrainLayer"
import { ClashLayer, OrderLayer } from "./OrderLayer"
import { ArtDefinitions } from "./TerrainArt"
import { TokenDefinitions } from "./tokens"
import { TokenLayer } from "./TokenLayer"
import { useBoardCamera } from "./useBoardCamera"
import { useBoardCaption } from "./useBoardCaption"
import { useBoardPointer } from "./useBoardPointer"
import { useHexPaint } from "./useHexPaint"
import "./board.css"

export type { BoardToken, TerritoryPlayer } from "./boardTypes"

const SAMPLES = ["rio", "lago", "playa", "pantano", "bosque", "montana", "desierto"]

export function HexStrip() {
  const cells = SAMPLES.map((ground, index) => ({
    q: index,
    r: 0,
    ground,
    road: false,
    bridge: false,
  }))
  return <HexBoard cells={cells} anchors={[]} />
}

export function HexBoard({
  cells,
  anchors,
  size = SIZE,
  players = NO_PLAYERS,
  unknown = NO_SPOTS,
  dimmed = NO_SPOTS,
  traces = NO_TRACES,
  clashes = NO_CLASHES,
  ghosts = NO_SPOTS,
  tokens = NO_TOKENS,
  tokensQuiet = false,
  marks = NO_SPOTS,
  markColor,
  tokenNotes,
  onCellClick,
  onPaint,
  orderPaths = NO_PATHS,
  tokenSpots,
  march = null,
  movableIds,
  selectedTokenId,
  focusSpot = null,
  spotlightId = null,
  mapTools = true,
  onOrderToken,
  onTokenOpen,
  onTokenInspect,
  onTokenDrop,
  spotAtRef,
}: HexBoardProps) {
  const { t } = useI18n()
  const boardId = useId().replaceAll(":", "")
  const sizeRef = useRef(size)
  sizeRef.current = size
  const scene = useTerrainScene({ cells, unknown, ghosts, anchors, size, players, boardId })
  const pointer = useBoardPointer({
    size,
    sizeRef,
    spotAtRef,
    movableIds,
    onOrderToken,
    onTokenDrop,
  })
  const camera = useBoardCamera({
    svgRef: pointer.svgRef,
    extentCount: scene.extent.length,
    focusSpot,
    mapTools,
    sizeRef,
  })
  const caption = useBoardCaption(players, tokenNotes)
  const byKey = useRef(new Map<string, OwnedCell | Spot>())
  byKey.current = new Map([...cells, ...ghosts].map((cell) => [`${cell.q},${cell.r}`, cell]))
  const { beginPaint } = useHexPaint(onPaint, pointer.svgRef, byKey, sizeRef)
  const pickRef = useRef<BoardPick>({ onCellClick, onPaint, beginPaint })
  pickRef.current = { onCellClick, onPaint, beginPaint }
  if (scene.extent.length === 0 || !scene.bounds) return null
  const { minX, minY, width, height } = scene.bounds
  const wide = scene.extent.length > 8

  return (
    <div className="hex-stage">
      <BoardTools
        shown={wide}
        zoom={camera.zoom}
        zoomOutDisabled={camera.zoomOutDisabled}
        zoomInDisabled={camera.zoomInDisabled}
        grid={camera.grid}
        showTerritories={camera.showTerritories}
        mapTools={mapTools}
        territoryCount={scene.territories.length}
        onZoomOut={camera.zoomOut}
        onFit={camera.fit}
        onZoomIn={camera.zoomIn}
        onToggleGrid={camera.toggleGrid}
        onToggleTerritories={camera.toggleTerritories}
      />
      <div
        ref={wide ? camera.viewportRef : undefined}
        className={wide ? "hex-viewport" : undefined}
        tabIndex={wide ? 0 : undefined}
        role="group"
        aria-label={t("mapsTitle")}
      >
        <svg
          ref={pointer.svgRef}
          className="hex-board"
          style={{
            width: `${camera.zoom * 100}%`,
            touchAction: onPaint || pointer.dragging ? "none" : undefined,
            ["--mark" as string]: markColor,
            ["--mark-fill" as string]: markColor ? markTint(markColor, 0.3) : undefined,
          }}
          onPointerMove={pointer.onPointerMove}
          onPointerUp={pointer.onPointerUp}
          viewBox={`${minX} ${minY} ${width} ${height}`}
          role="img"
          aria-label={t("mapsTitle")}
          data-picking={onCellClick || onPaint ? "true" : undefined}
        >
          <ArtDefinitions id={boardId} size={size} />
          {tokens.length > 0 ? <TokenDefinitions id={boardId} /> : null}
          <HexTerrainLayer
            scene={scene}
            grid={camera.grid}
            showTerritories={camera.showTerritories}
            marks={marks}
            pickRef={pickRef}
            onHover={caption.onHover}
          />
          <TokenLayer
            boardId={boardId}
            size={size}
            points={scene.points}
            placed={scene.placed}
            dimmed={dimmed}
            marks={marks}
            tokens={tokens}
            tokenSpots={tokenSpots}
            tokensQuiet={tokensQuiet}
            march={march}
            movableIds={movableIds}
            selectedTokenId={selectedTokenId}
            spotlightId={spotlightId}
            showTokenNote={caption.showTokenNote}
            tokenPress={pointer.tokenPress}
            tokenTap={pointer.tokenTap}
            onTokenOpen={onTokenOpen}
            onTokenInspect={onTokenInspect}
            routeLayer={<OrderLayer traces={traces} orderPaths={orderPaths} size={size} />}
            clashLayer={<ClashLayer clashes={clashes} size={size} />}
          />
        </svg>
      </div>
      <p ref={caption.captionRef} className="hex-caption" />
    </div>
  )
}
