import { useEffect, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"

import { ApiError, getCampaign, identityOptions, saveIdentity, type CampaignDetail, type IdentityOptions } from "../api"
import { Chronicle } from "./Chronicle"
import { PlayerIdentity } from "./PlayerIdentity"
import { Banner } from "../form"
import { HexBoard } from "../game/hex/HexBoard"
import { clientNotice, type MessageKey } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

const PHASE_KEYS: Record<CampaignDetail["phase"], MessageKey> = {
  recruiting: "phaseRecruiting",
  placing: "phasePlacing",
  orders: "phaseOrders",
  battles: "phaseBattles",
  finished: "phaseFinished",
}

export function CampaignDetailPage() {
  const { t } = useI18n()
  const { id = "" } = useParams()
  const mounted = useRef(true)
  const routeId = useRef(id)
  routeId.current = id
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null)
  const [options, setOptions] = useState<IdentityOptions | null>(null)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    if (!id) {
      setErrors({ campaign: [clientNotice("campaignNotFound")] })
      return
    }
    Promise.all([getCampaign(id), identityOptions()])
      .then(([found, choices]) => {
        if (current) {
          setCampaign(found)
          setOptions(choices)
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setErrors(presentError(error, "campaignLoadFailed"))
        }
      })
    return () => {
      current = false
      mounted.current = false
    }
  }, [id])

  async function saveBanner(faction: string, color: string) {
    if (!campaign) throw new Error("Campaign not loaded")
    try {
      const updated = await saveIdentity(campaign.id, campaign.revision, faction, color)
      if (mounted.current && routeId.current === updated.id) setCampaign(updated)
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        const current = await getCampaign(campaign.id)
        if (mounted.current && routeId.current === current.id) setCampaign(current)
      }
      throw error
    }
  }

  if (!campaign && Object.keys(errors).length === 0) {
    return <p className="quiet">{t("loadingCampaign")}</p>
  }

  return (
    <section className="campaign-detail">
      <header className="stage">
        <img className="stage-photo" src="/campaign-fortress.jpg" alt="" />
        <div className="stage-copy">
          <div>
            <p className="mark">{t("campaignDetail")}</p>
            <h1>{campaign?.name ?? t("campaignDetail")}</h1>
            {campaign ? <p>{t(PHASE_KEYS[campaign.phase])}</p> : null}
          </div>
          <Link className="text-link" to="/campanas">
            {t("backToCampaigns")}
          </Link>
        </div>
      </header>

      <Banner errors={errors} fields={["form", "session", "campaign"]} />

      {campaign?.you && options ? (
        <PlayerIdentity key={campaign.id} campaign={campaign} options={options} onSave={saveBanner} />
      ) : null}
      {campaign && campaign.hexes.length > 0 ? (
        <section className="campaign-map" aria-labelledby="territory-title">
          <h2 id="territory-title">{t("territoryTitle")}</h2>
          <p className="hint">{t("territoryHint")}</p>
          <ul className="territory-legend">
            {campaign.members.filter(member => member.color).map(member => {
              const faction = options?.factions.find(item => item.id === member.faction)
              return (
                <li key={member.player_id}>
                  <span className="territory-dot" style={{ backgroundColor: member.color }} aria-hidden="true" />
                  <span><strong>{member.alias}</strong>{faction ? <> · {t(faction.label)}</> : null}</span>
                </li>
              )
            })}
          </ul>
          <HexBoard
            cells={campaign.hexes.filter(cell => cell.known)}
            unknown={campaign.hexes.filter(cell => !cell.known)}
            anchors={campaign.fortresses}
            players={campaign.members.map(member => ({
              player_id: member.player_id, color: member.color, label: member.alias,
            }))}
          />
        </section>
      ) : null}
      {campaign ? (
        <div className="detail-grid">
          <article className="detail-panel">
            <h2>{t("rulesSummary")}</h2>
            <ul className="detail-list">
              <li>
                {t("ruleSeats")}: {campaign.rules.seats}
              </li>
              <li>
                {t("ruleArmies")}: {campaign.rules.armies}
              </li>
              <li>
                {t("ruleMovement")}: {campaign.rules.movement}
              </li>
              <li>
                {t("ruleMapSize")}: {campaign.rules.map_size}
              </li>
              <li>
                {t("ruleVisibility")}: {t(visibilityKey(campaign.rules.visibility))}
              </li>
              <li>
                {t("ruleVictory")}: {t(victoryKey(campaign.rules.victory))}
              </li>
              <li>
                {t("ruleHoldTurns")}: {campaign.rules.hold_turns}
              </li>
              <li>
                {t("rulePlacement")}:{" "}
                {campaign.rules.placement === "app" ? t("placementApp") : t("placementPlayers")}
              </li>
              <li>
                {t("ruleOrderDays")}: {campaign.rules.order_days}
              </li>
              <li>
                {t("ruleBattleDays")}: {campaign.rules.battle_days}
              </li>
              <li>
                {t("ruleMissedTurns")}: {campaign.rules.missed_turns}
              </li>
            </ul>
          </article>
          <article className="detail-panel">
            <h2>{t("membersTitle")}</h2>
            <ul className="detail-list">
              {campaign.members.map((member) => (
                <li key={member.player_id}>
                  <strong>{member.alias}</strong> · {member.role} · {member.status}
                  {!member.faction ? <> · {t("identityPending")}</> : null}
                </li>
              ))}
            </ul>
            {campaign.phase === "recruiting" ? (
              <p className="quiet">{t("recruitingHint")}</p>
            ) : null}
          </article>
        </div>
      ) : null}
      {campaign?.phase === "finished" ? (
        <Chronicle entries={campaign.chronicle} members={campaign.members} />
      ) : null}
    </section>
  )
}

function visibilityKey(value: CampaignDetail["rules"]["visibility"]) {
  if (value === "full") {
    return "visibilityFull" as const
  }
  if (value === "adjacent") {
    return "visibilityAdjacent" as const
  }
  return "visibilityAnonymous" as const
}

function victoryKey(value: CampaignDetail["rules"]["victory"]) {
  if (value === "armies") {
    return "victoryArmies" as const
  }
  if (value === "fortress") {
    return "victoryFortress" as const
  }
  return "victoryEither" as const
}
