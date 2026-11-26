import type { CampaignDetail } from "../../api"
import type { MessageKey } from "../../i18n/catalog"
import type { BoardToken } from "./HexBoard"

/** Map campaign armies into board tokens (presentation concern, not page state). */
export function toBoardTokens(
  campaign: CampaignDetail,
  t: (key: MessageKey, vars?: Record<string, string>) => string,
): BoardToken[] {
  return campaign.armies.flatMap((army) => {
    if (army.destroyed || army.q === null || army.r === null) return []
    const member = campaign.members.find(item => item.player_id === army.player_id)
    const color = member?.color || "#c0a062"
    const faction = army.race || member?.faction || ""
    const kindLabel = army.kind === "explorer" ? t("unitExplorer") : t("unitArmy")
    const label = army.anonymous
      ? kindLabel
      : `${member?.alias ?? "?"} · ${army.name || kindLabel}`
    return [{
      id: army.id,
      q: army.q,
      r: army.r,
      kind: army.kind,
      faction,
      color,
      label,
    }]
  })
}
