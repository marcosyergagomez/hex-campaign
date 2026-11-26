import { useEffect, useMemo, useRef, useState, type FormEvent } from "react"
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
import { GROUND_LABEL } from "../game/hex/grounds"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"
import "../game/hex/board.css"

type Tool = "terrain" | "road" | "bridge" | "erase" | "add" | "remove" | "fort"

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
  cellsRef.current = cells
  anchorsRef.current = anchors

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
            const copy = await copyMapForEdit(detail.id)
            if (!current) return
            const drawn = await getMap(copy.id)
            if (!current) return
            setMapId(drawn.id)
            setName(drawn.name)
            setSize(drawn.size)
            setCells(drawn.cells)
            setAnchors(drawn.anchors)
            navigate(`/mapas/editor?id=${encodeURIComponent(drawn.id)}`, { replace: true })
          } else {
            setMapId(detail.id)
            setName(detail.name)
            setSize(detail.size)
            setCells(detail.cells)
            setAnchors(detail.anchors)
          }
        } else if (copyId) {
          const copy = await copyMapForEdit(copyId)
          if (!current) return
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

  function applyPaint(target: Axial) {
    if (size === null) return
    beginStroke()
    const spots = brushCells(target, areaBrush && tool !== "fort" && tool !== "add" && tool !== "remove")
    let nextCells = cellsRef.current.map(cell => ({ ...cell }))
    let nextAnchors = anchorsRef.current.map(spot => ({ ...spot }))
    const index = new Map(nextCells.map((cell, i) => [axialKey(cell), i]))
    const disk = diskCells(size)
    const inDisk = new Set(disk.map(axialKey))

    for (const spot of spots) {
      const key = axialKey(spot)
      if (tool === "add") {
        if (index.has(key) || !inDisk.has(key)) continue
        nextCells.push({ q: spot.q, r: spot.r, ground: "llanura", road: false, bridge: false })
        index.set(key, nextCells.length - 1)
        continue
      }
      const at = index.get(key)
      if (at === undefined) continue
      if (tool === "remove") {
        nextCells[at] = null as unknown as MapCell
        nextAnchors = nextAnchors.filter(item => axialKey(item) !== key)
        continue
      }
      if (tool === "fort") {
        const cell = nextCells[at]
        if (cell.ground === "lago" || cell.ground === "montana_rocosa" || cell.ground === "acantilado") {
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
      const cell = { ...nextCells[at] }
      if (tool === "erase") {
        cell.ground = "llanura"
        cell.road = false
        cell.bridge = false
      } else if (tool === "terrain") {
        cell.ground = ground
        if (ground === "lago" || ground === "montana_rocosa" || ground === "acantilado") {
          cell.road = false
          cell.bridge = false
          nextAnchors = nextAnchors.filter(item => axialKey(item) !== key)
        }
        if (ground === "rio" && cell.road) cell.bridge = true
      } else if (tool === "road") {
        cell.road = true
        if (cell.ground === "rio") cell.bridge = true
      } else if (tool === "bridge") {
        cell.bridge = true
        if (cell.ground !== "rio" && cell.ground !== "orilla") cell.ground = "rio"
      }
      nextCells[at] = cell
    }

    nextCells = nextCells.filter(Boolean)
    cellsRef.current = nextCells
    anchorsRef.current = nextAnchors
    setCells(nextCells)
    setAnchors(nextAnchors)
    setSavedNote(false)
  }

  function endStroke() {
    if (!strokeBase.current) return
    const base = strokeBase.current
    strokeBase.current = null
    setPast(history => [...history.slice(-40), base])
    setFuture([])
  }

  function undo() {
    setPast(history => {
      if (history.length === 0) return history
      const previous = history[history.length - 1]
      setFuture(stack => [cloneShot(cells, anchors), ...stack].slice(0, 41))
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
      setPast(history => [...history, cloneShot(cells, anchors)].slice(-41))
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

  const tools: { id: Tool; label: string }[] = [
    { id: "terrain", label: t("mapEditorToolTerrain") },
    { id: "road", label: t("mapEditorToolRoad") },
    { id: "bridge", label: t("mapEditorToolBridge") },
    { id: "erase", label: t("mapEditorToolErase") },
    { id: "add", label: t("mapEditorToolAdd") },
    { id: "remove", label: t("mapEditorToolRemove") },
    { id: "fort", label: t("mapEditorToolFort") },
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
        <div className="table-picks">
          {tables.map(table => (
            <button
              key={table.size}
              type="button"
              disabled={Boolean(mapId) && size !== table.size}
              className={size === table.size ? "table-pick is-selected" : "table-pick"}
              onClick={() => changeSize(table.size)}
            >
              <span>{t(table.key === "small" ? "tableSmall" : table.key === "medium" ? "tableMedium" : "tableLarge")}</span>
            </button>
          ))}
        </div>
        <p className="quiet">{t("mapEditorForts", { count: String(anchors.length) })}</p>
        <div className="map-editor-actions">
          <button type="button" className="button-quiet" disabled={past.length === 0} onClick={undo}>
            {t("mapEditorUndo")}
          </button>
          <button type="button" className="button-quiet" disabled={future.length === 0} onClick={redo}>
            {t("mapEditorRedo")}
          </button>
          <button type="submit" disabled={pending || size === null || cells.length === 0}>
            {pending ? t("mapEditorSaving") : t("mapEditorSave")}
          </button>
        </div>
      </form>

      <div className="map-editor-tools" role="toolbar" aria-label={t("mapEditorTitle")}>
        {tools.map(item => (
          <button
            key={item.id}
            type="button"
            className={tool === item.id ? "choice is-selected" : "choice"}
            onClick={() => setTool(item.id)}
          >
            {item.label}
          </button>
        ))}
        <button
          type="button"
          className={!areaBrush ? "choice is-selected" : "choice"}
          onClick={() => setAreaBrush(false)}
        >
          {t("mapEditorBrush1")}
        </button>
        <button
          type="button"
          className={areaBrush ? "choice is-selected" : "choice"}
          onClick={() => setAreaBrush(true)}
        >
          {t("mapEditorBrushArea")}
        </button>
      </div>

      {tool === "terrain" ? (
        <div className="map-editor-grounds" role="listbox" aria-label={t("mapEditorToolTerrain")}>
          {GROUNDS.map(item => (
            <button
              key={item}
              type="button"
              className={ground === item ? "choice is-selected" : "choice"}
              onClick={() => setGround(item)}
            >
              {t(GROUND_LABEL[item])}
            </button>
          ))}
        </div>
      ) : null}

      {cells.length > 0 ? (
        <div
          className="map-editor-board"
          onPointerUp={endStroke}
          onPointerCancel={endStroke}
          onPointerLeave={event => {
            if (event.buttons === 0) endStroke()
          }}
        >
          <HexBoard
            cells={cells}
            anchors={anchors}
            ghosts={ghosts}
            onPaint={spot => {
              applyPaint(spot)
            }}
          />
        </div>
      ) : (
        <p className="quiet">{t("loadingCampaigns")}</p>
      )}
    </section>
  )
}
