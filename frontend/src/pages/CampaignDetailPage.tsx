import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"

import {
  closeCampaignOrders,
  expelCampaignMember,
  judgeCampaignBattle,
  promoteCampaignMember,
  restoreCampaignMember,
  revertCampaignTurn,
} from "../api"
import { ArmyRosterPanel } from "./ArmySheets"
import { Banner } from "../form"
import { setBattleFilm, useMarchFilm } from "../game/hex/useMarchFilm"
import { useI18n } from "../i18n/language"
import { Chronicle } from "./Chronicle"
import { AdminPanel } from "./campaign/AdminPanel"
import { CampaignBoard } from "./campaign/CampaignBoard"
import { CampaignLobby } from "./campaign/CampaignLobby"
import { MembersPanel } from "./campaign/MembersPanel"
import { PHASE_KEYS, statusKey } from "./campaign/phase"
import { RulesPanel } from "./campaign/RulesPanel"
import { useBoardSelection } from "./campaign/useBoardSelection"
import { useCampaignSession } from "./campaign/useCampaignSession"
import { useOrders } from "./campaign/useOrders"
import { usePreparation } from "./campaign/usePreparation"

export function CampaignDetailPage() {
  const { t } = useI18n()
  const { id = "" } = useParams()
  const session = useCampaignSession(id)
  const selection = useBoardSelection()
  const prep = usePreparation(session, selection)
  const film = useMarchFilm(session.campaign)
  const orders = useOrders(session, selection, film.playing)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const campaign = session.campaign

  const campaignId = campaign?.id
  useEffect(() => {
    if (!campaignId) return
    setBattleFilm(campaignId, film.playing)
    return () => setBattleFilm(campaignId, false)
  }, [campaignId, film.playing])

  const playing = Boolean(campaign && campaign.phase !== "recruiting")
  const staff = campaign?.you?.status === "active" &&
    (campaign.you.role === "owner" || campaign.you.role === "admin")
  const activeMembers = campaign?.members.filter((member) => member.status === "active") ?? []
  const seatsFull = Boolean(campaign && activeMembers.length === campaign.rules.seats)

  if (!campaign && Object.keys(session.errors).length === 0) {
    return <p className="quiet">{t("loadingCampaign")}</p>
  }

  return (
    <section className={playing ? "campaign-detail is-playing" : "campaign-detail"}>
      {playing ? (
        <header className="play-bar">
          <div className="play-bar-copy">
            <Link className="text-link play-bar-back" to="/campanas">
              {t("backToCampaigns")}
            </Link>
            <div>
              <h1>{campaign?.name ?? t("campaignDetail")}</h1>
              {campaign ? (
                <p className="play-bar-phase">
                  {t(statusKey(campaign.phase))}
                  {campaign.phase !== "finished" ? ` · ${t(PHASE_KEYS[campaign.phase])}` : ""}
                </p>
              ) : null}
            </div>
          </div>
          <div className="play-bar-actions">
            {staff && campaign ? (
              <button
                type="button"
                className="button-quiet"
                aria-expanded={adminOpen}
                onClick={() => setAdminOpen((value) => !value)}
              >
                {t("campaignAdminButton")}
              </button>
            ) : null}
            <button
              type="button"
              className="button-quiet"
              aria-expanded={detailsOpen}
              onClick={() => setDetailsOpen((value) => !value)}
            >
              {t("campaignDetailsButton")}
            </button>
          </div>
        </header>
      ) : (
        <header className="stage">
          <img className="stage-photo" src="/campaign-fortress.jpg" alt="" />
          <div className="stage-copy">
            <div>
              <p className="mark">{t("campaignDetail")}</p>
              <h1>{campaign?.name ?? t("campaignDetail")}</h1>
              {campaign ? (
                <p>
                  {t(statusKey(campaign.phase))}
                  {campaign.phase !== "finished" ? ` · ${t(PHASE_KEYS[campaign.phase])}` : ""}
                </p>
              ) : null}
            </div>
            <Link className="text-link" to="/campanas">
              {t("backToCampaigns")}
            </Link>
          </div>
        </header>
      )}

      <Banner errors={session.errors} fields={["form", "session", "campaign", "origin", "csrf", "revision"]} />

      {!playing && campaign?.description ? (
        <p className="campaign-blurb">{campaign.description}</p>
      ) : null}

      {playing && adminOpen && staff && campaign ? (
        <AdminPanel
          campaign={campaign}
          busy={session.busy}
          onRevert={() => session.applyCampaign(() => revertCampaignTurn(campaign.id, campaign.revision))}
          onCloseOrders={() => session.applyCampaign(() => closeCampaignOrders(campaign.id, campaign.revision))}
          onPromote={(playerId) => session.applyCampaign(() =>
            promoteCampaignMember(campaign.id, campaign.revision, playerId))}
          onExpel={(playerId) => session.applyCampaign(() =>
            expelCampaignMember(campaign.id, campaign.revision, playerId))}
          onRestore={(playerId) => session.applyCampaign(() =>
            restoreCampaignMember(campaign.id, campaign.revision, playerId))}
          onJudge={(battleId, result) => session.applyCampaign(() =>
            judgeCampaignBattle(campaign.id, battleId, campaign.revision, result))}
        />
      ) : null}

      {playing && detailsOpen && campaign ? (
        <div className="campaign-details-toggle">
          <div className="detail-grid">
            <RulesPanel campaign={campaign} />
            <ArmyRosterPanel campaign={campaign} />
            <MembersPanel
              campaign={campaign}
              busy={session.busy}
              canInvite={false}
              canStart={false}
              seatsFull={seatsFull}
              onRestore={(playerId) => {
                void session.applyCampaign(() =>
                  restoreCampaignMember(campaign.id, campaign.revision, playerId),
                )
              }}
              onExpel={(playerId) => {
                void session.applyCampaign(() =>
                  expelCampaignMember(campaign.id, campaign.revision, playerId),
                )
              }}
            />
          </div>
        </div>
      ) : null}

      <CampaignLobby session={session} />
      <CampaignBoard
        session={session}
        selection={selection}
        prep={prep}
        orders={orders}
        film={film}
      />
      {campaign?.phase === "finished" ? (
        <Chronicle entries={campaign.chronicle} members={campaign.members} />
      ) : null}
    </section>
  )
}
