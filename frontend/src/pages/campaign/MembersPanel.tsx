import type { CampaignDetail } from "../../api"
import { useI18n } from "../../i18n/language"
import { InvitePanel } from "../InvitePanel"

export function MembersPanel({
  campaign,
  busy,
  canInvite,
  canStart,
  seatsFull,
  onInvite,
  onStart,
  onRestore,
  onExpel,
}: {
  campaign: CampaignDetail
  busy: boolean
  canInvite: boolean
  canStart: boolean
  seatsFull: boolean
  onInvite?: (alias: string) => Promise<void>
  onStart?: () => void
  onRestore: (playerId: string) => void
  onExpel: (playerId: string) => void
}) {
  const { t } = useI18n()
  return (
    <article className="detail-panel">
      <h2>{t("membersTitle")}</h2>
      <ul className="detail-list">
        {campaign.members.map((member) => {
          const staff = campaign.you?.role === "owner" || campaign.you?.role === "admin"
          const canManage =
            staff &&
            member.status === "inactive" &&
            member.player_id !== campaign.you?.player_id &&
            campaign.phase !== "finished"
          return (
            <li key={member.player_id}>
              <strong>{member.alias}</strong> · {member.role} · {member.status}
              {!member.faction ? <> · {t("identityPending")}</> : null}
              {campaign.phase === "recruiting" && member.status === "active" ? (
                <> · {member.ready ? t("memberReady") : t("memberNotReady")}</>
              ) : null}
              {canManage ? (
                <span className="member-actions">
                  <button type="button" className="button-quiet" disabled={busy} onClick={() => onRestore(member.player_id)}>
                    {t("restoreMember")}
                  </button>
                  <button type="button" className="button-quiet" disabled={busy} onClick={() => onExpel(member.player_id)}>
                    {t("expelMember")}
                  </button>
                </span>
              ) : null}
            </li>
          )
        })}
      </ul>
      {campaign.phase === "recruiting" ? (
        <>
          <p className="quiet">{t("recruitingHint")}</p>
          {canInvite && onInvite ? <InvitePanel busy={busy} onInvite={onInvite} /> : null}
          {campaign.you?.role === "owner" && onStart ? (
            <button type="button" disabled={busy || !canStart} onClick={onStart}>
              {busy ? t("startingCampaign") : t("startCampaign")}
            </button>
          ) : null}
          {campaign.you?.role === "owner" && !canStart ? (
            <p className="quiet">{!seatsFull ? t("startNeedSeats") : t("startNeedReady")}</p>
          ) : null}
        </>
      ) : null}
    </article>
  )
}
