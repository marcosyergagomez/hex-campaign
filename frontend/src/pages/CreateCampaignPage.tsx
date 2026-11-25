import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"

import {
  createCampaign,
  DEFAULT_CAMPAIGN_RULES,
  listMaps,
  type CampaignRules,
  type Placement,
  type SavedMap,
  type Victory,
  type Visibility,
} from "../api"
import { Banner, Field, SelectField } from "../form"
import { clientNotice } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

type Step = 1 | 2 | 3

export function CreateCampaignPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const [step, setStep] = useState<Step>(1)
  const [name, setName] = useState("")
  const [rules, setRules] = useState<CampaignRules>(DEFAULT_CAMPAIGN_RULES)
  const [maps, setMaps] = useState<SavedMap[]>([])
  const [mapId, setMapId] = useState("")
  const [blind, setBlind] = useState(true)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    listMaps()
      .then((rows) => {
        if (current) {
          setMaps(rows)
        }
      })
      .catch(() => {
        if (current) {
          setMaps([])
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
    setPending(true)
    setErrors({})
    try {
      const chosen = maps.find((item) => item.id === mapId)
      const next = chosen
        ? {
            ...rules,
            map_size: chosen.size,
            seats: chosen.seats ?? rules.seats,
            visibility: terrainVisibility(rules.visibility),
          }
        : rules
      const created = await createCampaign(
        name.trim(),
        next,
        chosen && chosen.generated ? { id: chosen.id, blind } : chosen ? { id: chosen.id, blind: false } : undefined,
      )
      if (!mounted.current) {
        return
      }
      navigate(`/campanas/${created.id}`, { replace: true })
    } catch (error) {
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
        <Banner errors={errors} fields={["form", "campaign", "map", "rules", "origin", "csrf", "session"]} />

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
            <SelectField
              label={t("mapsTitle")}
              name="map"
              value={mapId}
              hint={t("mapsLead")}
              options={[
                { value: "", label: t("mapNone") },
                ...maps.map((item) => ({ value: item.id, label: item.name })),
              ]}
              onChange={(value) => {
                setMapId(value)
                const chosen = maps.find((item) => item.id === value)
                if (!chosen) {
                  const plainSize =
                    rules.map_size === 19 || rules.map_size === 37 || rules.map_size === 61
                  const plainSight =
                    rules.visibility === "full" ||
                    rules.visibility === "adjacent" ||
                    rules.visibility === "anonymous"
                  patchRules({
                    map_size: plainSize ? rules.map_size : 19,
                    visibility: plainSight ? rules.visibility : "full",
                  })
                  return
                }
                patchRules({
                  map_size: chosen.size,
                  seats: chosen.seats ?? rules.seats,
                  visibility: terrainVisibility(rules.visibility),
                })
              }}
            />
            {maps.some((item) => item.id === mapId && item.generated) ? (
              <label className="check-line">
                <input
                  type="checkbox"
                  checked={blind}
                  onChange={(event) => setBlind(event.target.checked)}
                />
                {t("mapBlind")}
              </label>
            ) : null}
            <SelectField
              label={t("ruleSeats")}
              name="seats"
              value={String(rules.seats)}
              hint={t("ruleSeatsHint")}
              disabled={maps.some((item) => item.id === mapId && item.seats != null)}
              options={[
                { value: "2", label: "2" },
                { value: "3", label: "3" },
                { value: "4", label: "4" },
              ]}
              onChange={(value) => patchRules({ seats: Number(value) })}
            />
            <fieldset className="choice-set" disabled={mapId !== ""}>
              <legend className="label-text">{t("ruleMapSize")}</legend>
              <p className="hint">{t("ruleMapSizeHint")}</p>
              <div className="choice-grid">
                {(mapId
                  ? [rules.map_size]
                  : ([19, 37, 61] as const)
                ).map((size) => (
                  <button
                    key={size}
                    type="button"
                    className={rules.map_size === size ? "choice is-selected" : "choice"}
                    onClick={() => patchRules({ map_size: size })}
                  >
                    <strong>{size}</strong>
                    <span>{t("hexesLabel")}</span>
                  </button>
                ))}
              </div>
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
              options={[
                { value: "1", label: "1" },
                { value: "2", label: "2" },
              ]}
              onChange={(value) => patchRules({ armies: Number(value) })}
            />
            <SelectField
              label={t("ruleMovement")}
              name="movement"
              value={String(rules.movement)}
              hint={t("ruleMovementHint")}
              options={[
                { value: "1", label: "1" },
                { value: "2", label: "2" },
                { value: "3", label: "3" },
              ]}
              onChange={(value) => patchRules({ movement: Number(value) })}
            />
            <fieldset className="choice-set">
              <legend className="label-text">{t("ruleVisibility")}</legend>
              <p className="hint">{t("ruleVisibilityHint")}</p>
              <div className="choice-grid choice-grid-wide">
                {(mapId
                  ? ([
                      ["total", "visibilityTotal"],
                      ["charted", "visibilityCharted"],
                      ["home", "visibilityHome"],
                    ] as const)
                  : ([
                      ["full", "visibilityFull"],
                      ["adjacent", "visibilityAdjacent"],
                      ["anonymous", "visibilityAnonymous"],
                    ] as const)
                ).map(([value, labelKey]) => (
                  <button
                    key={value}
                    type="button"
                    className={rules.visibility === value ? "choice is-selected" : "choice"}
                    onClick={() => patchRules({ visibility: value })}
                  >
                    {t(labelKey)}
                  </button>
                ))}
              </div>
            </fieldset>
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
                  {t("ruleMapSize")}: {rules.map_size}
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
