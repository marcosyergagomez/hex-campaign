import type { ChronicleEntry, ChronicleSpot, CampaignMember } from "../api"
import type { MessageKey } from "../i18n/catalog"
import { useI18n } from "../i18n/language"

export function Chronicle({
  entries,
  members,
}: {
  entries: ChronicleEntry[]
  members: CampaignMember[]
}) {
  const { t } = useI18n()
  const names = new Map(members.map((member) => [member.player_id, member.alias]))
  const alias = (playerId?: string) => names.get(playerId ?? "") ?? t("chronicleSomeone")
  const groups = groupByTurn(entries)

  return (
    <section className="chronicle">
      <h2>{t("chronicleTitle")}</h2>
      {groups.length === 0 ? <p className="quiet">{t("chronicleEmpty")}</p> : null}
      {groups.map((group, index) => (
        <article className="chronicle-turn" key={`${group.turn}-${index}`}>
          <h3>{group.turn === 0 ? t("chronicleBefore") : t("chronicleTurn", { turn: String(group.turn) })}</h3>
          <ol>
            {group.entries.map((entry, entryIndex) => (
              <li key={`${entry.code}-${entryIndex}`}>{sentence(entry, alias, t)}</li>
            ))}
          </ol>
        </article>
      ))}
    </section>
  )
}

function groupByTurn(entries: ChronicleEntry[]) {
  const groups: { turn: number; entries: ChronicleEntry[] }[] = []
  for (const entry of entries) {
    const last = groups[groups.length - 1]
    if (!last || last.turn !== entry.turn) {
      groups.push({ turn: entry.turn, entries: [entry] })
    } else {
      last.entries.push(entry)
    }
  }
  return groups
}

function sentence(
  entry: ChronicleEntry,
  alias: (playerId?: string) => string,
  t: (key: MessageKey, vars?: Record<string, string>) => string,
): string {
  const who = alias(entry.player_id)
  const army = entry.name || t("chronicleArmy")
  const outcome = entry.result === "draw" ? t("chronicleDraw") : alias(entry.result)
  switch (entry.code) {
    case "opened":
      return t("chronicleOpened", { alias: who })
    case "rules_changed":
      return t("chronicleRules", { alias: who })
    case "invited":
      return t("chronicleInvited", { alias: who })
    case "joined":
      return t("chronicleJoined", { alias: who })
    case "started":
      return t("chronicleStarted", { alias: who })
    case "deployed":
      return t("chronicleDeployed", { army, alias: who, q: String(entry.q ?? 0), r: String(entry.r ?? 0) })
    case "placed":
      return t("chroniclePlaced", { alias: who, q: String(entry.q ?? 0), r: String(entry.r ?? 0) })
    case "placement_closed":
      return t("chroniclePlacementClosed", { alias: who })
    case "roads_ready":
      return t("chronicleRoadsReady", { alias: who })
    case "preparation_closed":
      return t("chroniclePreparationClosed")
    case "named":
      return t("chronicleNamed", { alias: who, name: entry.name ?? army })
    case "orders_locked":
      return t("chronicleOrders", { alias: who })
    case "marched":
      return marchSentence(entry, who, army, t)
    case "battle_opened":
      return t("chronicleBattle", { q: String(entry.q ?? 0), r: String(entry.r ?? 0) })
    case "battle_reported":
      return t("chronicleReported", { alias: who, battle: entry.battle_id ?? "", result: outcome })
    case "battle_judged":
      return t("chronicleJudged", { alias: who, battle: entry.battle_id ?? "", result: outcome })
    case "destroyed":
      return t("chronicleDestroyed", { army, alias: who })
    case "battle_resolved":
      return t("chronicleResolved", { battle: entry.battle_id ?? "", result: outcome })
    case "eliminated":
      return t("chronicleEliminated", { alias: who })
    case "missed":
      return t("chronicleMissed", { alias: who })
    case "inactive":
      return t("chronicleInactive", { alias: who })
    case "expelled":
      return t("chronicleExpelled", { actor: who, target: alias(entry.target_id) })
    case "left":
      return t("chronicleLeft", { alias: who })
    case "promoted":
      return t("chroniclePromoted", { target: alias(entry.target_id) })
    case "reverted":
      return t("chronicleReverted", { turn: String(entry.undone ?? entry.turn) })
    case "owner_transferred":
      return t("chronicleOwner", { alias: who })
    case "hold":
      return holdSentence(entry, alias, t)
    case "finished":
      return finishSentence(entry, alias, t)
    default:
      return entry.code
  }
}

function marchSentence(
  entry: ChronicleEntry,
  who: string,
  army: string,
  t: (key: MessageKey, vars?: Record<string, string>) => string,
): string {
  const from = place(entry.origin)
  const to = place(entry.destination)
  if (from === to) {
    return t("chronicleStayed", { army, alias: who, from })
  }
  return t("chronicleMarched", { army, alias: who, from, to })
}

function holdSentence(
  entry: ChronicleEntry,
  alias: (playerId?: string) => string,
  t: (key: MessageKey, vars?: Record<string, string>) => string,
): string {
  const owner = alias(entry.player_id)
  if (!entry.holder_id) {
    return t("chronicleHoldLost", { owner })
  }
  return t("chronicleHold", { holder: alias(entry.holder_id), owner, hold: String(entry.hold ?? 0) })
}

function finishSentence(
  entry: ChronicleEntry,
  alias: (playerId?: string) => string,
  t: (key: MessageKey, vars?: Record<string, string>) => string,
): string {
  const names = (entry.winners ?? []).map((playerId) => alias(playerId)).join(", ")
  if (!names) {
    return t("chronicleNoWinner")
  }
  return t("chronicleWinners", { names })
}

function place(spot: ChronicleSpot | undefined): string {
  if (!spot) {
    return "0, 0"
  }
  return `${spot.q}, ${spot.r}`
}
