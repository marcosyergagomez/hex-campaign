import type { CampaignDetail } from "../../api"
import type { MessageKey } from "../../i18n/catalog"
import type { BoardToken } from "./HexBoard"

export function armyNeedsSheet(
  army: { kind: string; commander: string; roster: string },
  rosterRequired: boolean,
): boolean {
  if (army.kind !== "army") return false
  if (!army.commander.trim()) return true
  return rosterRequired && !army.roster.trim()
}

/** Numbers for this player's own duplicate pieces. Rivals never receive them. */
export function ownIndexes(campaign: CampaignDetail): Map<string, number> {
  const you = campaign.you?.player_id
  const marks = new Map<string, number>()
  if (!you) return marks
  for (const kind of ["army", "explorer"] as const) {
    const rows = campaign.armies
      .filter((army) => army.player_id === you && !army.destroyed && !army.anonymous && army.kind === kind)
      .sort((left, right) => left.id < right.id ? -1 : left.id > right.id ? 1 : 0)
    if (rows.length < 2) continue
    rows.forEach((army, index) => marks.set(army.id, index + 1))
  }
  return marks
}

/** Map campaign armies into board tokens (presentation concern, not page state). */
export function toBoardTokens(
  campaign: CampaignDetail,
  t: (key: MessageKey, vars?: Record<string, string>) => string,
): BoardToken[] {
  const marks = ownIndexes(campaign)
  return campaign.armies.flatMap((army) => {
    if (army.destroyed || army.q === null || army.r === null) return []
    const member = campaign.members.find(item => item.player_id === army.player_id)
    const color = member?.color || "#c0a062"
    const faction = army.race || member?.faction || ""
    const kindLabel = army.kind === "explorer" ? t("unitExplorer") : t("unitArmy")
    const title = army.kind === "army" && army.commander ? army.commander : (army.name || kindLabel)
    const mark = marks.get(army.id)
    const mine = army.player_id === campaign.you?.player_id
    const label = army.anonymous
      ? kindLabel
      : `${member?.alias ?? "?"} · ${title}${mark ? ` ${mark}` : ""}`
    return [{
      id: army.id,
      q: army.q,
      r: army.r,
      kind: army.kind,
      faction,
      color,
      label,
      mark,
      attention: Boolean(
        mine && !army.anonymous && campaign.prep === "armies" && armyNeedsSheet(army, campaign.rules.roster_required),
      ),
    }]
  })
}
