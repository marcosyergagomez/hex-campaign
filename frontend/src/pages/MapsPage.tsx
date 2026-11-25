import { useEffect, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"

import {
  generateMap,
  getMap,
  listMaps,
  type MapSize,
  type SavedMap,
  type SavedMapDetail,
} from "../api"
import { Banner, Field, SelectField } from "../form"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

export function MapsPage() {
  const { t } = useI18n()
  const [name, setName] = useState("")
  const [size, setSize] = useState<MapSize>(19)
  const [seats, setSeats] = useState(2)
  const [maps, setMaps] = useState<SavedMap[]>([])
  const [chart, setChart] = useState<SavedMapDetail | null>(null)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    let current = true
    listMaps()
      .then((rows) => {
        if (current) {
          setMaps(rows)
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
    setErrors({})
    try {
      setChart(await getMap(id))
    } catch (error) {
      setErrors(presentError(error, "mapUnknown"))
    }
  }

  return (
    <section className="wizard">
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
      <form className="wizard-panel" onSubmit={onSubmit}>
        <Banner errors={errors} fields={["form", "map", "rules", "name"]} />
        <div className="wizard-fields">
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
            onChange={(value) => setSeats(Number(value))}
          />
          <div className="choice-grid">
            {([19, 37, 61] as const).map((option) => (
              <button
                key={option}
                type="button"
                className={size === option ? "choice is-selected" : "choice"}
                onClick={() => setSize(option)}
              >
                {option}
              </button>
            ))}
          </div>
          <button type="submit" disabled={pending || name.trim().length === 0}>
            {pending ? t("generatingMap") : t("generateMap")}
          </button>
        </div>
      </form>
      <ul className="campaign-list">
        {maps.map((item) => (
          <li key={item.id}>
            <button type="button" className="campaign-card" onClick={() => openMap(item.id)}>
              <span className="campaign-card-body">
                <span className="campaign-card-name">{item.name}</span>
                <span className="campaign-card-meta">
                  {item.size}
                  {item.seats ? ` · ${item.seats}` : ""}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {chart ? <Atlas chart={chart} /> : null}
    </section>
  )
}

function Atlas({ chart }: { chart: SavedMapDetail }) {
  const forts = new Set(chart.anchors.map((spot) => `${spot.q},${spot.r}`))
  const placed = chart.cells.map((cell) => ({
    cell,
    x: (cell.q + cell.r / 2) * 46,
    y: cell.r * 40,
  }))
  const minX = Math.min(...placed.map((item) => item.x))
  const minY = Math.min(...placed.map((item) => item.y))
  const width = Math.max(...placed.map((item) => item.x)) - minX + 78
  const height = Math.max(...placed.map((item) => item.y)) - minY + 48
  return (
    <div className="atlas" style={{ width, height }}>
      {placed.map(({ cell, x, y }) => (
        <span
          key={`${cell.q},${cell.r}`}
          className={forts.has(`${cell.q},${cell.r}`) ? "atlas-cell is-fort" : "atlas-cell"}
          style={{ left: x - minX, top: y - minY }}
          title={cell.ground}
        >
          {cell.ground}
        </span>
      ))}
    </div>
  )
}
