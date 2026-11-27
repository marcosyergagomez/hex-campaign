import type { CampaignDetail } from "../../api"
import { useI18n } from "../../i18n/language"
import { victoryKey, visibilityKey } from "./phase"

export function RulesPanel({ campaign }: { campaign: CampaignDetail }) {
  const { t } = useI18n()
  return (
    <article className="detail-panel">
      <h2>{t("rulesSummary")}</h2>
      <ul className="detail-list">
        <li>{t("ruleSeats")}: {campaign.rules.seats}</li>
        <li>{t("ruleArmies")}: {campaign.rules.armies}</li>
        <li>{t("ruleMovement")}: {campaign.rules.movement}</li>
        <li>{t("ruleMapSize")}: {campaign.rules.map_size}</li>
        <li>{t("ruleVisibility")}: {t(visibilityKey(campaign.rules.visibility))}</li>
        <li>{t("ruleVictory")}: {t(victoryKey(campaign.rules.victory))}</li>
        <li>{t("ruleHoldTurns")}: {campaign.rules.hold_turns}</li>
        <li>
          {t("rulePlacement")}:{" "}
          {campaign.rules.placement === "app" ? t("placementApp") : t("placementPlayers")}
        </li>
        <li>{t("ruleOrderDays")}: {campaign.rules.order_days}</li>
        <li>{t("ruleBattleDays")}: {campaign.rules.battle_days}</li>
        <li>{t("ruleMissedTurns")}: {campaign.rules.missed_turns}</li>
        <li>
          {t("ruleRosterRequired")}: {campaign.rules.roster_required ? t("armyRosterRequiredShort") : t("armyRosterOptional")}
        </li>
      </ul>
    </article>
  )
}
