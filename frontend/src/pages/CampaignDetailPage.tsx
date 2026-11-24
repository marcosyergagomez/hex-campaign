import { useEffect, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"

import { getCampaign, type CampaignDetail } from "../api"
import { Banner } from "../form"
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
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    if (!id) {
      setErrors({ campaign: [clientNotice("campaignNotFound")] })
      return
    }
    getCampaign(id)
      .then((found) => {
        if (current) {
          setCampaign(found)
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

  if (!campaign && Object.keys(errors).length === 0) {
    return <p className="quiet">{t("loadingCampaign")}</p>
  }

  return (
    <section className="campaign-detail">
      <header className="page-header">
        <div>
          <p className="mark">{t("campaignDetail")}</p>
          <h1>{campaign?.name ?? t("campaignDetail")}</h1>
          {campaign ? <p className="quiet">{t(PHASE_KEYS[campaign.phase])}</p> : null}
        </div>
        <Link className="text-link" to="/campanas">
          {t("backToCampaigns")}
        </Link>
      </header>

      <Banner errors={errors} fields={["form", "session", "campaign"]} />

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
                </li>
              ))}
            </ul>
            {campaign.phase === "recruiting" ? (
              <p className="quiet">{t("recruitingHint")}</p>
            ) : null}
          </article>
        </div>
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
