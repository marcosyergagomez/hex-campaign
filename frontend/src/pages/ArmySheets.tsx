import { useEffect, useState } from "react"
import { createPortal } from "react-dom"

import { describeCampaignArmy, type CampaignArmy, type CampaignDetail } from "../api"
import { Field } from "../form"
import { useI18n } from "../i18n/language"

/** Read-only sheets once preparation has closed. */
export function ArmyRosterPanel({ campaign }: { campaign: CampaignDetail }) {
  const { t } = useI18n()
  const rows = campaign.armies.filter(
    (army) => army.kind === "army" && !army.anonymous && (army.commander || army.roster),
  )
  if (rows.length === 0) return null
  return (
    <article className="detail-panel">
      <h2>{t("armySheetsTitle")}</h2>
      <ul className="detail-list">
        {rows.map((army) => {
          const member = campaign.members.find((item) => item.player_id === army.player_id)
          return (
            <li key={army.id}>
              <strong>{member?.alias ?? army.commander}</strong>
              {army.commander ? ` · ${army.commander}` : ""}
              {army.roster ? <p className="army-roster">{army.roster}</p> : null}
            </li>
          )
        })}
      </ul>
    </article>
  )
}

export function ArmyModal({
  campaign,
  armyId,
  busy = false,
  onClose,
  onSave,
}: {
  campaign: CampaignDetail
  armyId: string
  busy?: boolean
  onClose: () => void
  onSave: (action: () => Promise<CampaignDetail>) => Promise<void>
}) {
  const { t } = useI18n()
  const army = campaign.armies.find((item) => item.id === armyId && item.kind === "army" && !item.anonymous)
  const mine = army?.player_id === campaign.you?.player_id
  const editing = Boolean(
    mine &&
    !army?.destroyed &&
    (campaign.prep === "armies" || (campaign.phase === "preparing" && campaign.naming)),
  )
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])
  if (!army) return null

  return createPortal(
    <div className="army-modal" onMouseDown={onClose}>
      <div
        className="army-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="army-dialog-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <img className="army-dialog-art" src="/army-standard.jpg" alt="" />
        <div className="army-dialog-body">
          <p className="army-dialog-kicker" id={army.commander.trim() ? undefined : "army-dialog-title"}>
            {t("armySheetsTitle")}
          </p>
          {army.commander.trim() ? (
            <h2 id="army-dialog-title">{army.commander.trim()}</h2>
          ) : null}
          {editing ? null : <p className="army-dialog-lead">{t("armyModalReadOnly")}</p>}
          {editing ? (
            <ArmyEditor
              campaignId={campaign.id}
              revision={campaign.revision}
              army={army}
              rosterRequired={campaign.rules.roster_required}
              busy={busy}
              onSave={onSave}
              onClose={onClose}
            />
          ) : (
            <>
              <p className="army-dialog-name">{army.commander.trim() || t("armyUnnamed")}</p>
              <p className="army-dialog-list">{army.roster || t("armyRosterEmpty")}</p>
              <button type="button" onClick={onClose}>{t("armyModalClose")}</button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}

function ArmyEditor({
  campaignId,
  revision,
  army,
  rosterRequired,
  busy,
  onSave,
  onClose,
}: {
  campaignId: string
  revision: number
  army: CampaignArmy
  rosterRequired: boolean
  busy: boolean
  onSave: (action: () => Promise<CampaignDetail>) => Promise<void>
  onClose: () => void
}) {
  const { t } = useI18n()
  const [commander, setCommander] = useState(army.commander)
  const [roster, setRoster] = useState(army.roster)
  useEffect(() => {
    setCommander(army.commander)
    setRoster(army.roster)
  }, [army.commander, army.roster, army.id])

  return (
    <form
      className="army-sheet"
      onSubmit={(event) => {
        event.preventDefault()
        const nextCommander = commander.trim()
        const nextRoster = roster.trim()
        void onSave(() =>
          describeCampaignArmy(campaignId, revision, army.id, {
            name: nextCommander || army.name,
            commander: nextCommander,
            race: army.race,
            roster: nextRoster,
          }),
        ).then(onClose)
      }}
    >
      <Field
        label={t("armyCommander")}
        name={`commander-${army.id}`}
        value={commander}
        required
        disabled={busy}
        onChange={setCommander}
      />
      <label className="field" htmlFor={`roster-${army.id}`}>
        <span>
          {t("armyRoster")} ({rosterRequired ? t("armyRosterRequiredShort") : t("armyRosterOptional")})
        </span>
        <textarea
          id={`roster-${army.id}`}
          name={`roster-${army.id}`}
          value={roster}
          maxLength={2000}
          rows={6}
          disabled={busy}
          required={rosterRequired}
          onChange={(event) => setRoster(event.target.value)}
        />
      </label>
      <div className="army-dialog-actions">
        <button type="button" className="button-quiet" onClick={onClose}>{t("armyModalClose")}</button>
        <button type="submit" disabled={busy || commander.trim().length === 0}>
          {t("armySheetSave")}
        </button>
      </div>
    </form>
  )
}
