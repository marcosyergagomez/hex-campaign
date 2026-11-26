import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"

import {
  ApiError,
  generateMap,
  getMap,
  listMapScales,
  listMaps,
  type MapScale,
  type MapSize,
  type SavedMap,
  type SavedMapDetail,
} from "../api"
import { HexBoard, HexStrip } from "../game/hex/HexBoard"
import { Banner, Field, SelectField } from "../form"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"
import "../game/hex/board.css"

const TABLE_LABELS = { small: "tableSmall", medium: "tableMedium", large: "tableLarge" } as const

export function MapsPage() {
  const { t } = useI18n()
  const [name, setName] = useState("")
  const [size, setSize] = useState<MapSize | null>(null)
  const [tables, setTables] = useState<MapScale[]>([])
  const [seats, setSeats] = useState(2)
  const [maps, setMaps] = useState<SavedMap[]>([])
  const [chart, setChart] = useState<SavedMapDetail | null>(null)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const openTicket = useRef(0)

  useEffect(() => {
    let current = true
    Promise.all([listMaps(), listMapScales()])
      .then(([rows, scales]) => {
        if (current) {
          setMaps(rows)
          setTables(scales)
          setSize(scales[0].size)
          setSeats(scales[0].recommend)
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setErrors(presentError(error, "campaignCreateFailed"))
        }
      })
    return () => {
      current = false
    }
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setErrors({})
    try {
      if (size === null || !tables.some(table => table.size === size && table.seats.includes(seats))) {
        throw new ApiError(422, {})
      }
      const created = await generateMap(name.trim(), size, seats)
      setMaps((current) => [created, ...current.filter((item) => item.id !== created.id)])
      setChart(null)
      setName("")
    } catch (error) {
      setErrors(presentError(error, "rulesInvalid"))
    } finally {
      setPending(false)
    }
  }

  async function openMap(id: string) {
    const ticket = openTicket.current + 1
    openTicket.current = ticket
    setErrors({})
    try {
      const detail = await getMap(id)
      if (ticket === openTicket.current) {
        setChart(detail)
      }
    } catch (error) {
      if (ticket === openTicket.current) {
        setErrors(presentError(error, "mapUnknown"))
      }
    }
  }

  return (
    <section className="map-studio">
      <header className="stage stage-short">
        <img className="stage-photo" src="/campaign-seal.jpg" alt="" />
        <div className="stage-copy">
          <p className="mark">{t("mapsNav")}</p>
          <h1>{t("mapsTitle")}</h1>
          <p>{t("mapsLead")}</p>
          <Link className="text-link" to="/campanas/nueva">
            {t("newCampaign")}
          </Link>
        </div>
      </header>
      <div className="map-studio-body">
        <form className="wizard-panel map-studio-form" onSubmit={onSubmit}>
          <Banner errors={errors} fields={["form", "map", "rules", "name"]} />
          <Field label={t("mapName")} name="map-name" value={name} onChange={setName} />
          <SelectField
            label={t("mapSeats")}
            name="seats"
            value={String(seats)}
            options={[
              { value: "2", label: "2" },
              { value: "3", label: "3" },
              { value: "4", label: "4" },
            ]}
            onChange={(value) => {
              const next = Number(value)
              setSeats(next)
              setSize((current) => {
                const table = tables.find((item) => item.size === current)
                if (table && table.seats.includes(next)) {
                  return current
                }
                return tables.find((item) => item.recommend === next)?.size
                  ?? tables.find((item) => item.seats.includes(next))?.size ?? null
              })
            }}
          />
          <div className="table-picks">
            {tables.map((table) => {
              const allowed = table.seats.includes(seats)
              return (
                <button
                  key={table.size}
                  type="button"
                  disabled={!allowed}
                  className={size === table.size ? "table-pick is-selected" : "table-pick"}
                  onClick={() => setSize(table.size)}
                >
                  <span>
                    {t(TABLE_LABELS[table.key])}
                    {table.recommend === seats ? (
                      <small>{t("tableRecommended", { seats: String(seats) })}</small>
                    ) : null}
                    <small>{t("mapHomeArea", { count: String(table.home_size) })}</small>
                  </span>
                  <strong>{table.size}</strong>
                </button>
              )
            })}
          </div>
          <button type="submit" disabled={pending || size === null || name.trim().length === 0}>
            {pending ? t("generatingMap") : t("generateMap")}
          </button>
        </form>
        <div className="map-studio-board">
          <HexStrip />
          {chart ? (
            <HexBoard cells={chart.cells} anchors={chart.anchors} />
          ) : (
            <div className="hex-stage hex-stage-empty">
              <p className="hex-caption">{t("mapsLead")}</p>
            </div>
          )}
          <ul className="map-strip">
            {maps.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={chart?.id === item.id ? "map-chip is-selected" : "map-chip"}
                  onClick={() => openMap(item.id)}
                >
                  <span>{item.name}</span>
                  <small>
                    {item.size}
                    {item.seats ? ` · ${item.seats}` : ""}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
