import { useEffect, useRef, useState, type FormEvent } from "react"

import { ApiError, type CampaignDetail, type IdentityOptions } from "../api"
import { Banner, SelectField } from "../form"
import { HexBoard, type BoardToken } from "../game/hex/HexBoard"
import { clientNotice } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

const PREVIEW = [
  { q: 0, r: 0, ground: "llanura" }, { q: 1, r: 0, ground: "bosque" },
  { q: 1, r: -1, ground: "bosque" }, { q: 0, r: -1, ground: "montana" },
  { q: -1, r: 0, ground: "llanura" }, { q: -1, r: 1, ground: "campo" },
  { q: 0, r: 1, ground: "llanura" },
].map((cell, index) => ({ ...cell, road: false, bridge: false, owner_id: index < 5 ? "preview" : null }))

const UNPAINTED = "#efe2b8"

export function PlayerIdentity({
  campaign,
  options,
  onSave,
  onClaim,
  onReady,
  busy = false,
}: {
  campaign: CampaignDetail
  options: IdentityOptions
  onSave: (faction: string, color: string) => Promise<void>
  onClaim: (color: string) => Promise<void>
  onReady?: (faction: string, color: string, ready: boolean) => Promise<void>
  busy?: boolean
}) {
  const { t } = useI18n()
  const [faction, setFaction] = useState(campaign.you?.faction ?? "")
  const [color, setColor] = useState(campaign.you?.color ?? "")
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  useEffect(() => {
    setFaction(campaign.you?.faction ?? "")
    setColor(campaign.you?.color ?? "")
  }, [campaign.you?.faction, campaign.you?.color])
  const takenBy = (value: string) => campaign.members.find(
    member => member.player_id !== campaign.you?.player_id && member.color === value,
  )
  const takenOwner = color ? takenBy(color) : undefined
  useEffect(() => {
    if (!takenOwner) return
    const saved = campaign.you?.color ?? ""
    setColor(saved && saved !== color ? saved : "")
    setSaved(false)
    setErrors(current => ({ ...current, color: [clientNotice("colorTaken")] }))
  }, [takenOwner, color, campaign.you?.color])
  const recruiting = campaign.phase === "recruiting"
  const editable = campaign.you?.status === "active" && campaign.phase !== "finished" &&
    (recruiting || (!campaign.you.faction && !campaign.you.color))
  async function submit(event: FormEvent) {
    event.preventDefault()
    const invalid: Record<string, string[]> = {}
    if (!faction) invalid.faction = [clientNotice("factionInvalid")]
    if (!color) invalid.color = [clientNotice("colorInvalid")]
    else if (takenBy(color)) invalid.color = [clientNotice("colorTaken")]
    setErrors(invalid)
    setSaved(false)
    if (Object.keys(invalid).length > 0) return
    setPending(true)
    try {
      await onSave(faction, color)
      if (mounted.current) setSaved(true)
    } catch (error: unknown) {
      // A stale revision already reloaded the campaign. The palette shows the
      // other player's colour with the cross; the "read it again" banner does not.
      if (mounted.current && !(error instanceof ApiError && error.status === 409)) {
        setErrors(presentError(error, "identitySaveFailed"))
      }
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  async function claim(next: string) {
    const previous = color
    setColor(next)
    setSaved(false)
    setErrors(current => {
      if (!current.color) return current
      const rest = { ...current }
      delete rest.color
      return rest
    })
    setPending(true)
    try {
      if (faction) await onSave(faction, next)
      else await onClaim(next)
    } catch (error: unknown) {
      if (!mounted.current) return
      if (error instanceof ApiError && error.status === 409) return
      setColor(previous)
      setErrors(presentError(error, "identitySaveFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  async function toggleReady(ready: boolean) {
    if (!onReady || pending || busy) return
    const invalid: Record<string, string[]> = {}
    if (ready && !faction) invalid.faction = [clientNotice("factionInvalid")]
    if (ready && !color) invalid.color = [clientNotice("colorInvalid")]
    else if (ready && takenBy(color)) invalid.color = [clientNotice("colorTaken")]
    setErrors(invalid)
    if (Object.keys(invalid).length > 0) return
    setPending(true)
    try {
      await onReady(faction, color, ready)
      if (mounted.current) setSaved(false)
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  const alias = campaign.you?.alias ?? ""
  const tokenColor = color || UNPAINTED
  const previewTokens: BoardToken[] = faction
    ? [
        {
          id: "preview-army",
          q: 0,
          r: 0,
          kind: "army",
          faction,
          color: tokenColor,
          label: `${alias} · ${t("unitArmy")}`,
        },
        {
          id: "preview-explorer",
          q: -1,
          r: 0,
          kind: "explorer",
          faction,
          color: tokenColor,
          label: `${alias} · ${t("unitExplorer")}`,
        },
      ]
    : []

  return (
    <section className="detail-panel player-identity" aria-labelledby="identity-title">
      <div className="identity-copy">
        <h2 id="identity-title">{t("identityTitle")}</h2>
        <p className="hint">{t(editable ? "identityHint" : "identityLocked")}</p>
        <form onSubmit={submit} noValidate>
          <SelectField
            label={t("identityRace")} name="faction" value={faction} error={errors.faction}
            disabled={pending || busy || !editable}
            options={[
              { value: "", label: t("choose") },
              ...options.factions.map(item => ({
                value: item.id,
                label: `${t(item.label)}${item.legacy ? ` · ${t("identityLegacy")}` : ""}`,
              })),
            ]}
            onChange={value => {
              setFaction(value)
              setSaved(false)
              if (campaign.you?.ready) void toggleReady(false)
            }}
          />
          <fieldset className="identity-palette" disabled={pending || busy || !editable}>
            <legend className="label-text">{t("identityColor")}</legend>
            <div className="identity-colors">
              {options.colors.map(item => {
                const owner = takenBy(item.value)
                return (
                  <label key={item.id} className={`identity-color${owner ? " is-taken" : ""}`}
                    title={owner ? t("identityTaken", { player: owner.alias }) : t(item.label)}>
                    <input type="radio" name="territory-color" value={item.value}
                      checked={color === item.value} disabled={Boolean(owner)}
                      onChange={() => { void claim(item.value) }} />
                    <span className="identity-swatch" style={{ backgroundColor: item.value }} aria-hidden="true">
                      {owner ? "×" : color === item.value ? "✓" : ""}
                    </span>
                    <span className="identity-color-name">{t(item.label)}</span>
                    {owner ? <span className="sr-only">{t("identityTaken", { player: owner.alias })}</span> : null}
                  </label>
                )
              })}
            </div>
          </fieldset>
          <Banner errors={errors} fields={Object.keys(errors).filter(key => key !== "faction")} />
          {editable && !recruiting ? (
            <button type="submit" disabled={pending || busy || !faction || !color || Boolean(takenBy(color))}>
              {pending ? t("identitySaving") : t("identitySave")}
            </button>
          ) : null}
          {saved ? <p className="quiet" role="status">{t("identitySaved")}</p> : null}
          {recruiting && onReady ? (
            <label className="check-row identity-ready">
              <input
                type="checkbox"
                checked={Boolean(campaign.you?.ready)}
                disabled={pending || busy || !faction || !color || Boolean(takenBy(color))}
                onChange={(event) => { void toggleReady(event.target.checked) }}
              />
              <span>{pending ? t("lobbyReadySaving") : t("lobbyReady")}</span>
            </label>
          ) : null}
          {campaign.you?.ready && recruiting ? (
            <p className="quiet" role="status">{t("lobbyReadyDone")}</p>
          ) : null}
        </form>
      </div>
      <figure className="identity-preview">
        <HexBoard
          cells={PREVIEW}
          anchors={[{ q: 0, r: 0 }]}
          players={[{ player_id: "preview", label: alias, color }]}
          tokens={previewTokens}
        />
        <figcaption>{t("identityPreview")}</figcaption>
      </figure>
    </section>
  )
}
