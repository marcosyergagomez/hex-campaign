import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"

import {
  createCampaign,
  DEFAULT_CAMPAIGN_RULES,
  deleteMap,
  generateMap,
  listMapScales,
  listMaps,
  type CampaignRules,
  type MapScale,
  type Placement,
  type SavedMap,
  type Victory,
  type Visibility,
} from "../api"
import { Banner, Field, SelectField, TextAreaField } from "../form"
import { clientNotice } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

type Step = 1 | 2 | 3
type MapMode = "auto" | "pick"

const SIZE_WORDS = { small: "sizeSmall", medium: "sizeMedium", large: "sizeLarge" } as const

export function CreateCampaignPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const [step, setStep] = useState<Step>(1)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [rules, setRules] = useState<CampaignRules>({
    ...DEFAULT_CAMPAIGN_RULES,
    visibility: "home",
  })
  const [tables, setTables] = useState<MapScale[]>([])
  const [maps, setMaps] = useState<SavedMap[]>([])
  const [mapMode, setMapMode] = useState<MapMode>("auto")
  const [mapId, setMapId] = useState("")
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    Promise.all([listMaps(), listMapScales()])
      .then(([rows, scales]) => {
        if (!current) return
        setMaps(rows.filter((item) => item.generated))
        setTables(scales)
        const first = scales[0]
        setRules((currentRules) => ({
          ...currentRules,
          map_size: first.size,
          seats: Math.min(currentRules.seats, first.recommend),
          movement: recommendedMovement(first.key),
          visibility: terrainVisibility(currentRules.visibility),
        }))
      })
      .catch((error: unknown) => {
        if (current) {
          setMaps([])
          setTables([])
          setErrors(presentError(error, "campaignLoadFailed"))
        }
      })
    return () => {
      current = false
      mounted.current = false
    }
  }, [])

  function patchRules(patch: Partial<CampaignRules>) {
    setRules((current) => ({ ...current, ...patch }))
  }

  function goNext() {
    setErrors({})
    if (step === 1) {
      const trimmed = name.trim()
      if (!trimmed) {
        setErrors({ name: [clientNotice("fieldRequired")] })
        return
      }
      if (trimmed.length > 120) {
        setErrors({ name: [clientNotice("campaignNameTooLong")] })
        return
      }
      if (description.length > 15000) {
        setErrors({ description: [clientNotice("campaignDescriptionTooLong")] })
        return
      }
      if (mapMode === "pick" && !mapId) {
        setErrors({ map: [clientNotice("fieldRequired")] })
        return
      }
      if (mapMode === "auto" && !tables.some((table) => table.size === rules.map_size)) {
        setErrors({ map: [clientNotice("fieldRequired")] })
        return
      }
      setName(trimmed)
      setStep(2)
      return
    }
    if (step === 2) {
      setStep(3)
    }
  }

  function goBack() {
    setErrors({})
    if (step === 2) {
      setStep(1)
    } else if (step === 3) {
      setStep(2)
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (step !== 3) {
      goNext()
      return
    }
    if (mapMode === "auto" && !tables.some((table) => table.size === rules.map_size)) {
      setErrors({ map: [clientNotice("fieldRequired")] })
      return
    }
    setPending(true)
    setErrors({})
    let generatedId: string | null = null
    try {
      let chosen = maps.find((item) => item.id === mapId)
      if (mapMode === "auto") {
        chosen = await generateMap(name.trim(), rules.map_size, rules.seats)
        generatedId = chosen.id
      }
      if (!chosen) {
        setErrors({ map: [clientNotice("fieldRequired")] })
        return
      }
      const next: CampaignRules = {
        ...rules,
        map_size: chosen.size,
        seats: chosen.seats ?? rules.seats,
        visibility: terrainVisibility(rules.visibility),
      }
      const created = await createCampaign(
        name.trim(),
        next,
        { id: chosen.id, blind: false },
        description,
      )
      generatedId = null
      if (!mounted.current) {
        return
      }
      navigate(`/campanas/${created.id}`, { replace: true })
    } catch (error) {
      if (generatedId) {
        try {
          await deleteMap(generatedId)
        } catch {
          /* keep the create error below */
        }
      }
      if (mounted.current) {
        setErrors(presentError(error, "campaignCreateFailed"))
      }
    } finally {
      if (mounted.current) {
        setPending(false)
      }
    }
  }

  const showHold = rules.victory === "fortress" || rules.victory === "either"
  const generatedMaps = maps.filter((item) => {
    if (mapMode !== "pick") return true
    return item.size === rules.map_size
  })
  const sizeOptions = tables.filter((table) => table.seats.includes(rules.seats))

  return (
    <section className="wizard">
      <header className="stage stage-short">
        <img className="stage-photo" src="/campaign-seal.jpg" alt="" />
        <div className="stage-copy">
          <div>
            <p className="mark">{t("newCampaign")}</p>
            <h1>{t("createCampaignTitle")}</h1>
            <p>{t("createCampaignLead")}</p>
            <p>{t("createLimitHint")}</p>
          </div>
          <Link className="text-link" to="/campanas">
            {t("backToCampaigns")}
          </Link>
        </div>
      </header>

      <ol className="wizard-steps" aria-label={t("wizardSteps")}>
        <li className={step === 1 ? "is-current" : step > 1 ? "is-done" : undefined}>
          <span className="wizard-step-index">1</span>
          <span>{t("stepTable")}</span>
        </li>
        <li className={step === 2 ? "is-current" : step > 2 ? "is-done" : undefined}>
          <span className="wizard-step-index">2</span>
          <span>{t("stepWar")}</span>
        </li>
        <li className={step === 3 ? "is-current" : undefined}>
          <span className="wizard-step-index">3</span>
          <span>{t("stepTime")}</span>
        </li>
      </ol>

      <form className="wizard-panel" onSubmit={onSubmit} noValidate>
        <Banner errors={errors} />

        {step === 1 ? (
          <div className="wizard-fields">
            <h2>{t("stepTable")}</h2>
            <Field
              label={t("campaignName")}
              name="name"
              value={name}
              hint={t("campaignNameHint")}
              error={errors.name}
              onChange={setName}
            />
            <TextAreaField
              label={t("campaignDescription")}
              name="description"
              value={description}
              hint={t("campaignDescriptionHint")}
              error={errors.description}
              maxLength={15000}
              rows={10}
              onChange={setDescription}
            />
            <SelectField
              label={t("ruleSeats")}
              name="seats"
              value={String(rules.seats)}
              hint={t("ruleSeatsHint")}
              options={[
                { value: "2", label: "2" },
                { value: "3", label: "3" },
                { value: "4", label: "4" },
              ]}
              onChange={(value) => {
                const seats = Number(value)
                const fit = tables.find((table) => table.size === rules.map_size && table.seats.includes(seats))
                  ?? tables.find((table) => table.seats.includes(seats))
                patchRules({
                  seats,
                  ...(fit
                    ? { map_size: fit.size, movement: recommendedMovement(fit.key) }
                    : {}),
                })
                if (mapMode === "pick") {
                  setMapId("")
                }
              }}
            />
            <fieldset className="choice-set">
              <legend className="label-text">{t("ruleMap")}</legend>
              <p className="hint">{t("ruleMapHint")}</p>
              <div className="choice-grid">
                {([
                  ["auto", "mapModeAuto"],
                  ["pick", "mapModePick"],
                ] as const).map(([value, labelKey]) => (
                  <button
                    key={value}
                    type="button"
                    className={mapMode === value ? "choice is-selected" : "choice"}
                    onClick={() => {
                      setMapMode(value)
                      setMapId("")
                    }}
                  >
                    {t(labelKey)}
                  </button>
                ))}
              </div>
              <p className="hint">{t("ruleMapSizeHint")}</p>
              <div className="choice-grid">
                {(sizeOptions.length ? sizeOptions : tables).map((table) => (
                  <button
                    key={table.key}
                    type="button"
                    className={rules.map_size === table.size ? "choice is-selected" : "choice"}
                    onClick={() => {
                      patchRules({
                        map_size: table.size,
                        movement: recommendedMovement(table.key),
                      })
                      setMapId("")
                    }}
                  >
                    <strong>{t(SIZE_WORDS[table.key])}</strong>
                  </button>
                ))}
              </div>
              {mapMode === "pick" ? (
                <SelectField
                  label={t("mapPickLabel")}
                  name="map"
                  value={mapId}
                  hint={t("mapPickHint")}
                  error={errors.map}
                  options={[
                    { value: "", label: t("mapPickPlaceholder") },
                    ...generatedMaps.map((item) => ({ value: item.id, label: item.name })),
                  ]}
                  onChange={(value) => {
                    setMapId(value)
                    const chosen = maps.find((item) => item.id === value)
                    if (!chosen) return
                    const scale = tables.find((table) => table.size === chosen.size)
                    patchRules({
                      map_size: chosen.size,
                      seats: chosen.seats ?? rules.seats,
                      movement: recommendedMovement(scale?.key ?? "small"),
                      visibility: terrainVisibility(rules.visibility),
                    })
                  }}
                />
              ) : null}
            </fieldset>
            <SelectField
              label={t("rulePlacement")}
              name="placement"
              value={rules.placement}
              hint={t("rulePlacementHint")}
              options={[
                { value: "app", label: t("placementApp") },
                { value: "players", label: t("placementPlayers") },
              ]}
              onChange={(value) => patchRules({ placement: value as Placement })}
            />
          </div>
        ) : null}

        {step === 2 ? (
          <div className="wizard-fields">
            <h2>{t("stepWar")}</h2>
            <SelectField
              label={t("ruleArmies")}
              name="armies"
              value={String(rules.armies)}
              hint={t("ruleArmiesHint")}
              options={[1, 2].map((n) => ({ value: String(n), label: String(n) }))}
              onChange={(value) => patchRules({ armies: Number(value) })}
            />
            <label className="check-row">
              <input
                type="checkbox"
                checked={rules.roster_required}
                onChange={(event) => patchRules({ roster_required: event.target.checked })}
              />
              <span>
                <strong>{t("ruleRosterRequired")}</strong>
                <span className="field-note">{t("ruleRosterRequiredHint")}</span>
              </span>
            </label>
            <SelectField
              label={t("ruleMovement")}
              name="movement"
              value={String(rules.movement)}
              hint={t("ruleMovementHint", {
                recommended: String(recommendedMovement(
                  tables.find((table) => table.size === rules.map_size)?.key ?? "small",
                )),
              })}
              options={[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: String(n) }))}
              onChange={(value) => patchRules({ movement: Number(value) })}
            />
            <SelectField
              label={t("ruleVisibility")}
              name="visibility"
              value={terrainVisibility(rules.visibility)}
              hint={t("ruleVisibilityHint")}
              options={[
                { value: "total", label: t("visibilityTotal") },
                { value: "charted", label: t("visibilityCharted") },
                { value: "home", label: t("visibilityHome") },
              ]}
              onChange={(value) => patchRules({ visibility: value as Visibility })}
            />
            <SelectField
              label={t("ruleVictory")}
              name="victory"
              value={rules.victory}
              hint={t("ruleVictoryHint")}
              options={[
                { value: "armies", label: t("victoryArmies") },
                { value: "fortress", label: t("victoryFortress") },
                { value: "either", label: t("victoryEither") },
              ]}
              onChange={(value) => patchRules({ victory: value as Victory })}
            />
            {showHold ? (
              <SelectField
                label={t("ruleHoldTurns")}
                name="hold_turns"
                value={String(rules.hold_turns)}
                hint={t("ruleHoldTurnsHint")}
                options={[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => ({
                  value: String(n),
                  label: String(n),
                }))}
                onChange={(value) => patchRules({ hold_turns: Number(value) })}
              />
            ) : null}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="wizard-fields">
            <h2>{t("stepTime")}</h2>
            <SelectField
              label={t("ruleOrderDays")}
              name="order_days"
              value={String(rules.order_days)}
              hint={t("ruleOrderDaysHint")}
              options={dayOptions()}
              onChange={(value) => patchRules({ order_days: Number(value) })}
            />
            <SelectField
              label={t("ruleBattleDays")}
              name="battle_days"
              value={String(rules.battle_days)}
              hint={t("ruleBattleDaysHint")}
              options={dayOptions()}
              onChange={(value) => patchRules({ battle_days: Number(value) })}
            />
            <SelectField
              label={t("ruleMissedTurns")}
              name="missed_turns"
              value={String(rules.missed_turns)}
              hint={t("ruleMissedTurnsHint")}
              options={[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: String(n) }))}
              onChange={(value) => patchRules({ missed_turns: Number(value) })}
            />
            <div className="summary-panel">
              <h3>{t("reviewTitle")}</h3>
              <p>
                <strong>{name.trim()}</strong>
              </p>
              <ul>
                <li>
                  {t("ruleSeats")}: {rules.seats}
                </li>
                <li>
                  {t("ruleMap")}: {t(mapMode === "auto" ? "mapModeAuto" : "mapModePick")}
                  {" · "}
                  {sizeLabel(tables, rules.map_size, t)}
                </li>
                <li>
                  {t("ruleVisibility")}: {t(visibilityKey(rules.visibility))}
                </li>
                <li>
                  {t("ruleVictory")}: {t(victoryKey(rules.victory))}
                </li>
              </ul>
            </div>
          </div>
        ) : null}

        <div className="wizard-actions">
          {step > 1 ? (
            <button type="button" className="button-secondary" onClick={goBack} disabled={pending}>
              {t("wizardBack")}
            </button>
          ) : (
            <span />
          )}
          {step < 3 ? (
            <button type="submit">{t("wizardNext")}</button>
          ) : (
            <button type="submit" disabled={pending}>
              {pending ? t("creatingCampaign") : t("createCampaignSubmit")}
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

function dayOptions() {
  return [1, 2, 3, 5, 7, 10, 14, 21, 30].map((n) => ({ value: String(n), label: String(n) }))
}

function sizeLabel(
  tables: MapScale[],
  size: number,
  t: (key: "sizeSmall" | "sizeMedium" | "sizeLarge") => string,
) {
  const key = tables.find((table) => table.size === size)?.key
  return key ? t(SIZE_WORDS[key]) : String(size)
}

function recommendedMovement(key: MapScale["key"] | "small"): number {
  if (key === "medium") return 4
  if (key === "large") return 5
  return 3
}

function visibilityKey(value: Visibility) {
  if (value === "full" || value === "total") {
    return value === "total" ? ("visibilityTotal" as const) : ("visibilityFull" as const)
  }
  if (value === "charted") {
    return "visibilityCharted" as const
  }
  if (value === "home") {
    return "visibilityHome" as const
  }
  if (value === "adjacent") {
    return "visibilityAdjacent" as const
  }
  return "visibilityAnonymous" as const
}

function terrainVisibility(value: Visibility): Visibility {
  if (value === "total" || value === "charted" || value === "home") {
    return value
  }
  return "home"
}

function victoryKey(value: Victory) {
  if (value === "armies") {
    return "victoryArmies" as const
  }
  if (value === "fortress") {
    return "victoryFortress" as const
  }
  return "victoryEither" as const
}
