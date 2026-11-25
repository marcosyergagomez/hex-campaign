import { useEffect, useRef, useState, type FormEvent } from "react"

import type { CampaignDetail, IdentityOptions } from "../api"
import { Banner, SelectField } from "../form"
import { HexBoard } from "../game/hex/HexBoard"
import { clientNotice } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

const PREVIEW = [
  { q: 0, r: 0, ground: "llanura" }, { q: 1, r: 0, ground: "bosque" },
  { q: 1, r: -1, ground: "bosque" }, { q: 0, r: -1, ground: "montana" },
  { q: -1, r: 0, ground: "llanura" }, { q: -1, r: 1, ground: "campo" },
  { q: 0, r: 1, ground: "llanura" },
].map((cell, index) => ({ ...cell, road: false, bridge: false, owner_id: index < 5 ? "preview" : null }))

export function PlayerIdentity({ campaign, options, onSave }: {
  campaign: CampaignDetail
  options: IdentityOptions
  onSave: (faction: string, color: string) => Promise<void>
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
  const editable = campaign.you?.status === "active" && campaign.phase !== "finished" &&
    (campaign.phase === "recruiting" || (!campaign.you.faction && !campaign.you.color))
  const takenBy = (value: string) => campaign.members.find(
    member => member.player_id !== campaign.you?.player_id && member.color === value,
  )

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
      if (mounted.current) setErrors(presentError(error, "identitySaveFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  return (
    <section className="detail-panel player-identity" aria-labelledby="identity-title">
      <div className="identity-copy">
        <h2 id="identity-title">{t("identityTitle")}</h2>
        <p className="hint">{t(editable ? "identityHint" : "identityLocked")}</p>
        <form onSubmit={submit} noValidate>
          <SelectField
            label={t("identityRace")} name="faction" value={faction} error={errors.faction}
            disabled={pending || !editable}
            options={[
              { value: "", label: t("choose") },
              ...options.factions.map(item => ({
                value: item.id,
                label: `${t(item.label)}${item.legacy ? ` · ${t("identityLegacy")}` : ""}`,
              })),
            ]}
            onChange={value => { setFaction(value); setSaved(false) }}
          />
          <fieldset className="identity-palette" disabled={pending || !editable}>
            <legend className="label-text">{t("identityColor")}</legend>
            <div className="identity-colors">
              {options.colors.map(item => {
                const owner = takenBy(item.value)
                return (
                  <label key={item.id} className={`identity-color${owner ? " is-taken" : ""}`}
                    title={owner ? t("identityTaken", { player: owner.alias }) : t(item.label)}>
                    <input type="radio" name="territory-color" value={item.value}
                      checked={color === item.value} disabled={Boolean(owner)}
                      onChange={() => { setColor(item.value); setSaved(false) }} />
                    <span className="identity-swatch" style={{ backgroundColor: item.value }} aria-hidden="true">
                      {color === item.value ? "✓" : ""}
                    </span>
                    <span>{t(item.label)}</span>
                    {owner ? <span className="sr-only">{t("identityTaken", { player: owner.alias })}</span> : null}
                  </label>
                )
              })}
            </div>
          </fieldset>
          <Banner errors={errors} fields={Object.keys(errors).filter(key => key !== "faction")} />
          {editable ? (
            <button type="submit" disabled={pending || !faction || !color || Boolean(takenBy(color))}>
              {t(pending ? "identitySaving" : "identitySave")}
            </button>
          ) : null}
          {saved ? <p className="quiet" role="status">{t("identitySaved")}</p> : null}
        </form>
      </div>
      <figure className="identity-preview">
        <HexBoard cells={PREVIEW} anchors={[{ q: 0, r: 0 }]}
          players={[{ player_id: "preview", label: campaign.you?.alias ?? "", color }]} />
        <figcaption>{t("identityPreview")}</figcaption>
      </figure>
    </section>
  )
}
