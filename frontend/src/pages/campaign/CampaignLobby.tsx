import {
  claimCampaignColor,
  expelCampaignMember,
  inviteCampaignPlayer,
  markCampaignReady,
  restoreCampaignMember,
  saveIdentity,
  startCampaign,
} from "../../api"
import { useI18n } from "../../i18n/language"
import { presentError } from "../../presentError"
import { PlayerIdentity } from "../PlayerIdentity"
import { MembersPanel } from "./MembersPanel"
import { RulesPanel } from "./RulesPanel"
import type { CampaignSession } from "./useCampaignSession"

export function CampaignLobby({ session }: { session: CampaignSession }) {
  const { t } = useI18n()
  const campaign = session.campaign
  if (!campaign || campaign.phase !== "recruiting") return null
  const loaded = campaign
  const activeMembers = loaded.members.filter((member) => member.status === "active")
  const seatsFull = activeMembers.length === campaign.rules.seats
  const allReady = activeMembers.length > 0 && activeMembers.every((member) => member.ready)
  const canStart = campaign.you?.role === "owner" && seatsFull && allReady
  const canInvite = (campaign.you?.role === "owner" || campaign.you?.role === "admin") &&
    activeMembers.length < campaign.rules.seats

  async function saveBanner(faction: string, color: string) {
    await session.mutateCampaign(() => saveIdentity(loaded.id, loaded.revision, faction, color))
  }

  async function claimColor(color: string) {
    await session.mutateCampaign(() => claimCampaignColor(loaded.id, loaded.revision, color))
  }

  async function markReady(faction: string, color: string, ready: boolean) {
    session.setBusy(true)
    try {
      let revision = loaded.revision
      const you = loaded.you
      if (ready && (!you || you.faction !== faction || you.color !== color)) {
        const saved = await saveIdentity(loaded.id, revision, faction, color)
        session.accept(saved)
        revision = saved.revision
      }
      session.accept(await markCampaignReady(loaded.id, revision, ready))
      if (session.mounted.current) session.setErrors({})
    } catch (error: unknown) {
      if (session.mounted.current) {
        session.setErrors(presentError(error, ready ? "lobbyReadyFailed" : "identitySaveFailed"))
      }
    } finally {
      if (session.mounted.current) session.setBusy(false)
    }
  }

  return (
    <>
      {campaign.you && session.options ? (
        <PlayerIdentity
          key={campaign.id}
          campaign={campaign}
          options={session.options}
          onSave={saveBanner}
          onClaim={claimColor}
          onReady={markReady}
          busy={session.busy}
        />
      ) : null}
      <p className="quiet">{t("mapSealedHint")}</p>
      <div className="detail-grid">
        <RulesPanel campaign={campaign} />
        <MembersPanel
          campaign={campaign}
          busy={session.busy}
          canInvite={canInvite}
          canStart={canStart}
          seatsFull={seatsFull}
          onInvite={
            canInvite
              ? async (alias) => {
                  await session.mutateCampaign(() =>
                    inviteCampaignPlayer(loaded.id, loaded.revision, alias),
                  )
                }
              : undefined
          }
          onStart={() => {
            void session.applyCampaign(() => startCampaign(loaded.id, loaded.revision))
          }}
          onRestore={(playerId) => {
            void session.applyCampaign(() =>
              restoreCampaignMember(loaded.id, loaded.revision, playerId),
            )
          }}
          onExpel={(playerId) => {
            void session.applyCampaign(() =>
              expelCampaignMember(loaded.id, loaded.revision, playerId),
            )
          }}
        />
      </div>
    </>
  )
}
