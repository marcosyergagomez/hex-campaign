import type { CampaignDetail } from "../../api"
import { useI18n } from "../../i18n/language"

export function MissingSheets({
  pieces,
  rosterRequired,
}: {
  pieces: { kind: string; attention?: boolean; label: string; mark?: number }[]
  rosterRequired: boolean
}) {
  const { t } = useI18n()
  const pending = pieces.filter((piece) => piece.kind === "army" && piece.attention)
  if (pending.length === 0) return null
  const names = pending.map((piece) => {
    if (piece.mark) return `${t("unitArmy")} ${piece.mark}`
    return piece.label === t("armyUnnamed") ? t("unitArmy") : piece.label
  }).join(", ")
  return (
    <p className="prep-alert" role="status">
      {t(rosterRequired ? "prepSheetsMissingList" : "prepSheetsMissing", { names })}
    </p>
  )
}

export function WaitingNames({ campaign }: { campaign: CampaignDetail }) {
  const { t } = useI18n()
  const names = campaign.members
    .filter((member) => member.status === "active" && !campaign.prep_done.includes(member.player_id))
    .map((member) => member.alias)
    .join(", ")
  if (!names) return null
  return <p className="quiet">{t("prepWaitingNames", { names })}</p>
}
