import { useState } from "react"

import type { CampaignDetail } from "../../api"
import { useI18n } from "../../i18n/language"

export function AdminPanel({
  campaign,
  busy,
  onRevert,
  onCloseOrders,
  onPromote,
  onExpel,
  onRestore,
  onJudge,
}: {
  campaign: CampaignDetail
  busy: boolean
  onRevert: () => void
  onCloseOrders: () => void
  onPromote: (playerId: string) => void
  onExpel: (playerId: string) => void
  onRestore: (playerId: string) => void
  onJudge: (battleId: string, result: string) => void
}) {
  const { t } = useI18n()
  const [armed, setArmed] = useState<string | null>(null)
  const you = campaign.you?.player_id
  const alias = (playerId: string) =>
    campaign.members.find((member) => member.player_id === playerId)?.alias ?? playerId
  const roleLabel = (role: string) => {
    if (role === "owner") return t("adminRoleOwner")
    if (role === "admin") return t("adminRoleAdmin")
    return t("adminRolePlayer")
  }
  const statusLabel = (status: string) => {
    if (status === "inactive") return t("adminStatusInactive")
    if (status === "expelled") return t("adminStatusExpelled")
    if (status === "eliminated") return t("adminStatusEliminated")
    return t("adminStatusActive")
  }
  const openBattles = campaign.battles.filter((battle) => battle.result === null && !battle.reverted && (battle.conflict || battle.due))
  function confirm(key: string, run: () => void) {
    if (armed === key) {
      setArmed(null)
      run()
      return
    }
    setArmed(key)
  }
  return (
    <section className="admin-panel" aria-label={t("adminTitle")}>
      <h2>{t("adminTitle")}</h2>
      {campaign.phase === "orders" || campaign.phase === "battles" || campaign.phase === "finished" ? (
        <div className="admin-action">
          <p>{t("adminRevertHint")}</p>
          <span>
            <button type="button" className={armed === "revert" ? "is-armed" : "is-danger"} disabled={busy} onClick={() => confirm("revert", onRevert)}>
              {armed === "revert" ? t("adminConfirm") : t("adminRevert")}
            </button>
            {armed === "revert" ? (
              <button type="button" disabled={busy} onClick={() => setArmed(null)}>
                {t("adminCancel")}
              </button>
            ) : null}
          </span>
        </div>
      ) : null}
      {campaign.phase === "orders" ? (
        <div className="admin-action">
          <p>{t("adminCloseOrdersHint")}</p>
          <span>
            <button type="button" className={armed === "close" ? "is-armed" : undefined} disabled={busy} onClick={() => confirm("close", onCloseOrders)}>
              {armed === "close" ? t("adminConfirm") : t("adminCloseOrders")}
            </button>
            {armed === "close" ? (
              <button type="button" disabled={busy} onClick={() => setArmed(null)}>
                {t("adminCancel")}
              </button>
            ) : null}
          </span>
        </div>
      ) : null}
      <h3>{t("adminPlayers")}</h3>
      <ul className="admin-people">
        {campaign.members.filter((member) => member.player_id !== you).map((member) => {
          const canPromote = member.role === "player" && member.status !== "expelled" && campaign.phase !== "recruiting"
          const canRestore = member.status === "inactive" && campaign.phase !== "finished"
          const canExpel = member.status !== "expelled" && !(member.role === "owner" && member.status === "active")
          return (
            <li key={member.player_id}>
              <span className="admin-person">
                <strong>{member.alias}</strong>
                <span>{roleLabel(member.role)} · {statusLabel(member.status)}</span>
              </span>
              <span>
                {canPromote ? (
                  <button type="button" disabled={busy} onClick={() => onPromote(member.player_id)}>
                    {t("adminPromote")}
                  </button>
                ) : null}
                {canRestore ? (
                  <button type="button" disabled={busy} onClick={() => onRestore(member.player_id)}>
                    {t("restoreMember")}
                  </button>
                ) : null}
                {canExpel ? (
                  <>
                    <button type="button" className={armed === `expel:${member.player_id}` ? "is-armed" : "is-danger"} disabled={busy} onClick={() => confirm(`expel:${member.player_id}`, () => onExpel(member.player_id))}>
                      {armed === `expel:${member.player_id}` ? t("adminConfirm") : t("expelMember")}
                    </button>
                    {armed === `expel:${member.player_id}` ? (
                      <button type="button" disabled={busy} onClick={() => setArmed(null)}>
                        {t("adminCancel")}
                      </button>
                    ) : null}
                  </>
                ) : null}
              </span>
            </li>
          )
        })}
      </ul>
      {openBattles.length > 0 ? <h3>{t("adminBattles")}</h3> : null}
      {openBattles.map((battle) => (
        <div className="admin-action" key={battle.id}>
          <p>{t("adminBattleAt", { q: String(battle.q), r: String(battle.r) })}</p>
          <span>
            {battle.players.map((playerId) => {
              const key = `judge:${battle.id}:${playerId}`
              return (
                <button key={playerId} type="button" className={armed === key ? "is-armed" : undefined} disabled={busy} onClick={() => confirm(key, () => onJudge(battle.id, playerId))}>
                  {armed === key ? t("adminConfirm") : t("adminJudgeFor", { name: alias(playerId) })}
                </button>
              )
            })}
            <button type="button" className={armed === `judge:${battle.id}:draw` ? "is-armed" : undefined} disabled={busy} onClick={() => confirm(`judge:${battle.id}:draw`, () => onJudge(battle.id, "draw"))}>
              {armed === `judge:${battle.id}:draw` ? t("adminConfirm") : t("adminJudgeDraw")}
            </button>
            {armed?.startsWith(`judge:${battle.id}:`) ? (
              <button type="button" disabled={busy} onClick={() => setArmed(null)}>
                {t("adminCancel")}
              </button>
            ) : null}
          </span>
        </div>
      ))}
    </section>
  )
}
