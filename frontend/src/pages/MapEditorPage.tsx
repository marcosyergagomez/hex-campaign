import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"

import {
  copyMapForEdit,
  getMap,
  listMapScales,
  saveDrawnMap,
  updateDrawnMap,
  type MapCell,
  type MapScale,
  type MapSize,
} from "../api"
import { Banner, Field } from "../form"
import { HexBoard } from "../game/hex/HexBoard"
import { axialKey, brushCells, diskCells, type Axial } from "../game/hex/disk"
import { GROUND_ART, GROUND_LABEL, GROUND_TIP } from "../game/hex/grounds"
import { isImpassable } from "../game/hex/terrainContract"
import { useI18n } from "../i18n/language"
import type { MessageKey } from "../i18n/catalog"
import { presentError } from "../presentError"
import {
  IconAddHex,
  IconBridge,
  IconBrush,
  IconBrushArea,
  IconErase,
  IconRedo,
  IconRemoveHex,
  IconRoad,
  IconUndo,
} from "./mapEditorIcons"
import "../game/hex/board.css"

type Tool = "terrain" | "road" | "bridge" | "erase" | "add" | "remove" | "fort"
type EditTool = "erase" | "add" | "remove"
type BuildTool = "fort" | "road" | "bridge"

type Snapshot = {
  cells: MapCell[]
  anchors: Axial[]
}

const GROUNDS = Object.keys(GROUND_LABEL)

function plainDisk(size: MapSize): MapCell[] {
  return diskCells(size).map(cell => ({
    ...cell,
    ground: "llanura",
    road: false,
    bridge: false,
  }))
}

function cloneShot(cells: MapCell[], anchors: Axial[]): Snapshot {
  return {
    cells: cells.map(cell => ({ ...cell })),
    anchors: anchors.map(spot => ({ ...spot })),
  }
}

export function MapEditorPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const editId = params.get("id")
  const copyId = params.get("copy")
  const sizeParam = params.get("size")

  const [tables, setTables] = useState<MapScale[]>([])
  const [size, setSize] = useState<MapSize | null>(null)
  const [name, setName] = useState("")
  const [mapId, setMapId] = useState<string | null>(editId)
  const [cells, setCells] = useState<MapCell[]>([])
  const [anchors, setAnchors] = useState<Axial[]>([])
  const [tool, setTool] = useState<Tool>("terrain")
  const [ground, setGround] = useState("bosque")
  const [areaBrush, setAreaBrush] = useState(false)
  const [pending, setPending] = useState(false)
  const [savedNote, setSavedNote] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [past, setPast] = useState<Snapshot[]>([])
  const [future, setFuture] = useState<Snapshot[]>([])
  const strokeBase = useRef<Snapshot | null>(null)
  const cellsRef = useRef<MapCell[]>([])
  const anchorsRef = useRef<Axial[]>([])
  const paintQueue = useRef<Axial[]>([])
  const paintFrame = useRef<number | null>(null)
  const paintOpts = useRef({ tool, ground, areaBrush, size })
  cellsRef.current = cells
  anchorsRef.current = anchors
  paintOpts.current = { tool, ground, areaBrush, size }
  const diskKeys = useMemo(
    () => (size === null ? null : new Set(diskCells(size).map(axialKey))),
    [size],
  )

  useEffect(() => {
    let current = true
    listMapScales()
      .then(async scales => {
        if (!current) return
        setTables(scales)
        if (editId) {
          const detail = await getMap(editId)
          if (!current) return
          if (detail.generated) {
            // Never copy on GET of a generated id: refresh would spawn duplicates.
            navigate(`/mapas/editor?copy=${encodeURIComponent(detail.id)}`, { replace: true })
            return
          }
          setMapId(detail.id)
          setName(detail.name)
          setSize(detail.size)
          setCells(detail.cells)
          setAnchors(detail.anchors)
        } else if (copyId) {
          const cacheKey = `hex-map-copy:${copyId}`
          const cached = sessionStorage.getItem(cacheKey)
          if (cached) {
            navigate(`/mapas/editor?id=${encodeURIComponent(cached)}`, { replace: true })
            return
          }
          const copy = await copyMapForEdit(copyId)
          if (!current) return
          // Persist as soon as the server copy exists so a refresh cannot mint another.
          sessionStorage.setItem(cacheKey, copy.id)
          const drawn = await getMap(copy.id)
          if (!current) return
          setMapId(drawn.id)
          setName(drawn.name)
          setSize(drawn.size)
          setCells(drawn.cells)
          setAnchors(drawn.anchors)
          navigate(`/mapas/editor?id=${encodeURIComponent(drawn.id)}`, { replace: true })
        } else {
          const chosen = scales.find(item => String(item.size) === sizeParam)?.size
            ?? scales[0]?.size
            ?? null
          setSize(chosen)
          if (chosen !== null) setCells(plainDisk(chosen))
          setName("")
          setMapId(null)
          setAnchors([])
        }
      })
      .catch((error: unknown) => {
        if (current) setErrors(presentError(error, "mapUnknown"))
      })
    return () => {
      current = false
    }
  }, [editId, copyId, sizeParam, navigate])

  const present = useMemo(() => new Set(cells.map(axialKey)), [cells])
  const ghosts = useMemo(() => {
    if (size === null || tool !== "add") return []
    return diskCells(size).filter(cell => !present.has(axialKey(cell)))
  }, [size, tool, present])

  function pushHistory(nextCells: MapCell[], nextAnchors: Axial[]) {
    const base = strokeBase.current ?? cloneShot(cells, anchors)
    setPast(history => [...history.slice(-40), base])
    setFuture([])
    strokeBase.current = null
    setCells(nextCells)
    setAnchors(nextAnchors)
    setSavedNote(false)
  }

  function beginStroke() {
    if (!strokeBase.current) {
      strokeBase.current = cloneShot(cellsRef.current, anchorsRef.current)
    }
  }

  function applyPaintBatch(targets: Axial[]) {
    const { tool: active, ground: soil, areaBrush: area, size: board } = paintOpts.current
    if (board === null || targets.length === 0 || !diskKeys) return
    beginStroke()
    const nextCells: (MapCell | null)[] = cellsRef.current.slice()
    let nextAnchors = anchorsRef.current
    const index = new Map(nextCells.map((cell, i) => cell ? [axialKey(cell), i] as const : null).filter((item): item is readonly [string, number] => item !== null))
    const widen = area && active !== "fort" && active !== "add" && active !== "remove"

    for (const target of targets) {
      for (const spot of brushCells(target, widen)) {
        const key = axialKey(spot)
        if (active === "add") {
          if (index.has(key) || !diskKeys.has(key)) continue
          nextCells.push({ q: spot.q, r: spot.r, ground: "llanura", road: false, bridge: false })
          index.set(key, nextCells.length - 1)
          continue
        }
        const at = index.get(key)
        if (at === undefined) continue
        if (active === "remove") {
          nextCells[at] = null
          nextAnchors = nextAnchors.filter(item => axialKey(item) !== key)
          continue
        }
        const stored = nextCells[at]
        if (!stored) continue
        if (active === "fort") {
          if (isImpassable(stored.ground)) {
            continue
          }
          const exists = nextAnchors.some(item => axialKey(item) === key)
          nextAnchors = exists
            ? nextAnchors.filter(item => axialKey(item) !== key)
            : nextAnchors.length >= 4
              ? nextAnchors
              : [...nextAnchors, { q: spot.q, r: spot.r }]
          continue
        }
        const cell = { ...stored }
        if (active === "erase") {
          cell.ground = "llanura"
          cell.road = false
          cell.bridge = false
        } else if (active === "terrain") {
          cell.ground = soil
          if (isImpassable(soil)) {
            cell.road = false
            cell.bridge = false
            nextAnchors = nextAnchors.filter(item => axialKey(item) !== key)
          }
          if (soil === "rio" && cell.road) cell.bridge = true
        } else if (active === "road") {
          cell.road = true
          if (cell.ground === "rio") cell.bridge = true
        } else if (active === "bridge") {
          cell.bridge = true
          if (cell.ground !== "rio") cell.ground = "rio"
        }
        nextCells[at] = cell
      }
    }

    const kept = nextCells.filter((cell): cell is MapCell => cell !== null)
    cellsRef.current = kept
    anchorsRef.current = nextAnchors
    setCells(kept)
    setAnchors(nextAnchors)
    setSavedNote(false)
  }

  const flushPaint = useCallback(() => {
    paintFrame.current = null
    const batch = paintQueue.current
    paintQueue.current = []
    if (batch.length) applyPaintBatch(batch)
  }, [diskKeys])

  const queuePaint = useCallback((spots: Axial[]) => {
    if (!spots.length) return
    paintQueue.current.push(...spots)
    if (paintFrame.current !== null) return
    paintFrame.current = requestAnimationFrame(flushPaint)
  }, [flushPaint])

  function endStroke() {
    if (paintFrame.current !== null) {
      cancelAnimationFrame(paintFrame.current)
      paintFrame.current = null
    }
    if (paintQueue.current.length) {
      const batch = paintQueue.current
      paintQueue.current = []
      applyPaintBatch(batch)
    }
    if (!strokeBase.current) return
    const base = strokeBase.current
    strokeBase.current = null
    setPast(history => [...history.slice(-40), base])
    setFuture([])
  }
  const endStrokeRef = useRef(endStroke)
  endStrokeRef.current = endStroke

  useEffect(() => {
    const up = () => endStrokeRef.current()
    window.addEventListener("pointerup", up)
    window.addEventListener("pointercancel", up)
    return () => {
      window.removeEventListener("pointerup", up)
      window.removeEventListener("pointercancel", up)
      if (paintFrame.current !== null) cancelAnimationFrame(paintFrame.current)
    }
  }, [])

  function undo() {
    setPast(history => {
      if (history.length === 0) return history
      const previous = history[history.length - 1]
      setFuture(stack => [
        cloneShot(cellsRef.current, anchorsRef.current),
        ...stack,
      ].slice(0, 41))
      cellsRef.current = previous.cells
      anchorsRef.current = previous.anchors
      setCells(previous.cells)
      setAnchors(previous.anchors)
      setSavedNote(false)
      return history.slice(0, -1)
    })
  }

  function redo() {
    setFuture(stack => {
      if (stack.length === 0) return stack
      const [next, ...rest] = stack
      setPast(history => [
        ...history,
        cloneShot(cellsRef.current, anchorsRef.current),
      ].slice(-41))
      cellsRef.current = next.cells
      anchorsRef.current = next.anchors
      setCells(next.cells)
      setAnchors(next.anchors)
      setSavedNote(false)
      return rest
    })
  }

  function changeSize(next: MapSize) {
    if (next === size || mapId) return
    pushHistory(plainDisk(next), [])
    setSize(next)
  }

  async function onSave(event: FormEvent) {
    event.preventDefault()
    if (size === null || cells.length === 0) return
    setPending(true)
    setErrors({})
    try {
      const trimmed = name.trim()
      if (!trimmed) throw new Error("name")
      const saved = mapId
        ? await updateDrawnMap(mapId, trimmed, size, cells, anchors)
        : await saveDrawnMap(trimmed, size, cells, anchors)
      setMapId(saved.id)
      setName(saved.name)
      setSavedNote(true)
      navigate(`/mapas/editor?id=${encodeURIComponent(saved.id)}`, { replace: true })
    } catch (error) {
      if (error instanceof Error && error.message === "name") {
        setErrors({ name: [t("fieldRequired")] })
      } else {
        setErrors(presentError(error, "rulesInvalid"))
      }
    } finally {
      setPending(false)
    }
  }

  const editTools: {
    id: EditTool
    label: MessageKey
    tip: MessageKey
    icon: typeof IconErase
  }[] = [
    { id: "erase", label: "mapEditorToolErase", tip: "mapEditorTipErase", icon: IconErase },
    { id: "add", label: "mapEditorToolAdd", tip: "mapEditorTipAdd", icon: IconAddHex },
    { id: "remove", label: "mapEditorToolRemove", tip: "mapEditorTipRemove", icon: IconRemoveHex },
  ]

  const buildings: {
    id: BuildTool
    label: MessageKey
    tip: MessageKey
    art?: string
    Icon?: typeof IconRoad
  }[] = [
    { id: "fort", label: "mapEditorToolFort", tip: "mapEditorTipFort", art: "/terrain/fortaleza.jpg" },
    { id: "road", label: "mapEditorToolRoad", tip: "mapEditorTipRoad", Icon: IconRoad },
    { id: "bridge", label: "mapEditorToolBridge", tip: "mapEditorTipBridge", Icon: IconBridge },
  ]

  return (
    <section className="map-editor">
      <header className="stage stage-short">
        <img className="stage-photo" src="/campaign-seal.jpg" alt="" />
        <div className="stage-copy">
          <div>
            <p className="mark">{t("mapEditorNav")}</p>
            <h1>{t("mapEditorTitle")}</h1>
            <p>{t("mapEditorLead")}</p>
          </div>
          <Link className="text-link" to="/mapas">{t("mapEditorBack")}</Link>
        </div>
      </header>

      <Banner errors={errors} fields={["form", "map", "rules", "name", "origin", "csrf", "session"]} />
      {savedNote ? <p className="quiet" role="status">{t("mapEditorSaved")}</p> : null}

      <form className="map-editor-bar" onSubmit={onSave}>
        <Field label={t("mapName")} name="editor-map-name" value={name} onChange={setName} />
        <div className="map-size-field">
          <span className="map-size-label" id="editor-map-size">{t("mapEditorSize")}</span>
          <div className="map-size-picks" role="group" aria-labelledby="editor-map-size">
            {tables.map(table => {
              const label = t(
                table.key === "small" ? "sizeSmall" : table.key === "medium" ? "sizeMedium" : "sizeLarge",
              )
              const full = t(
                table.key === "small" ? "tableSmall" : table.key === "medium" ? "tableMedium" : "tableLarge",
              )
              return (
                <button
                  key={table.size}
                  type="button"
                  disabled={Boolean(mapId) && size !== table.size}
                  className={size === table.size ? "map-size-pick is-selected" : "map-size-pick"}
                  title={full}
                  aria-pressed={size === table.size}
                  onClick={() => changeSize(table.size)}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>
        <p className="map-editor-forts quiet">{t("mapEditorForts", { count: String(anchors.length) })}</p>
        <div className="map-editor-actions">
          <button type="submit" disabled={pending || size === null || cells.length === 0}>
            {pending ? t("mapEditorSaving") : t("mapEditorSave")}
          </button>
        </div>
      </form>

      <div className="map-editor-tools" role="toolbar" aria-label={t("mapEditorTitle")}>
        {editTools.map(item => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              className={tool === item.id ? "map-tool-btn is-selected" : "map-tool-btn"}
              title={`${t(item.label)}. ${t(item.tip)}`}
              aria-label={t(item.label)}
              aria-pressed={tool === item.id}
              onClick={() => setTool(item.id)}
            >
              <Icon className="map-tool-icon" />
            </button>
          )
        })}
        <span className="map-tool-sep" aria-hidden="true" />
        <button
          type="button"
          className={!areaBrush ? "map-tool-btn is-selected" : "map-tool-btn"}
          title={`${t("mapEditorBrush1")}. ${t("mapEditorTipBrush1")}`}
          aria-label={t("mapEditorBrush1")}
          aria-pressed={!areaBrush}
          onClick={() => setAreaBrush(false)}
        >
          <IconBrush className="map-tool-icon" />
        </button>
        <button
          type="button"
          className={areaBrush ? "map-tool-btn is-selected" : "map-tool-btn"}
          title={`${t("mapEditorBrushArea")}. ${t("mapEditorTipBrushArea")}`}
          aria-label={t("mapEditorBrushArea")}
          aria-pressed={areaBrush}
          onClick={() => setAreaBrush(true)}
        >
          <IconBrushArea className="map-tool-icon" />
        </button>
        <span className="map-tool-sep" aria-hidden="true" />
        <button
          type="button"
          className="map-tool-btn"
          title={`${t("mapEditorUndo")}. ${t("mapEditorTipUndo")}`}
          aria-label={t("mapEditorUndo")}
          disabled={past.length === 0}
          onClick={undo}
        >
          <IconUndo className="map-tool-icon" />
        </button>
        <button
          type="button"
          className="map-tool-btn"
          title={`${t("mapEditorRedo")}. ${t("mapEditorTipRedo")}`}
          aria-label={t("mapEditorRedo")}
          disabled={future.length === 0}
          onClick={redo}
        >
          <IconRedo className="map-tool-icon" />
        </button>
      </div>

      <div className="map-editor-body">
        <aside className="map-editor-palette" aria-label={t("mapEditorTerrains")}>
          <p className="map-palette-title">{t("mapEditorTerrains")}</p>
          {GROUNDS.map(item => (
            <button
              key={item}
              type="button"
              className={tool === "terrain" && ground === item ? "map-ground-swatch is-selected" : "map-ground-swatch"}
              title={`${t(GROUND_LABEL[item])}. ${t(GROUND_TIP[item])}`}
              aria-label={t(GROUND_LABEL[item])}
              aria-pressed={tool === "terrain" && ground === item}
              onClick={() => {
                setTool("terrain")
                setGround(item)
              }}
            >
              <img src={GROUND_ART[item]} alt="" />
              <span>{t(GROUND_LABEL[item])}</span>
            </button>
          ))}
        </aside>

        {cells.length > 0 ? (
          <div className="map-editor-board">
            <HexBoard
              cells={cells}
              anchors={anchors}
              ghosts={ghosts}
              onPaint={queuePaint}
            />
          </div>
        ) : (
          <p className="quiet">{t("loadingCampaigns")}</p>
        )}

        <aside className="map-editor-palette map-editor-buildings" aria-label={t("mapEditorBuildings")}>
          <p className="map-palette-title">{t("mapEditorBuildings")}</p>
          {buildings.map(item => (
            <button
              key={item.id}
              type="button"
              className={tool === item.id ? "map-ground-swatch is-selected" : "map-ground-swatch"}
              title={`${t(item.label)}. ${t(item.tip)}`}
              aria-label={t(item.label)}
              aria-pressed={tool === item.id}
              onClick={() => setTool(item.id)}
            >
              {item.art ? <img src={item.art} alt="" /> : null}
              {item.Icon ? <item.Icon className="map-build-art" /> : null}
              <span>{t(item.label)}</span>
            </button>
          ))}
        </aside>
      </div>
    </section>
  )
}
