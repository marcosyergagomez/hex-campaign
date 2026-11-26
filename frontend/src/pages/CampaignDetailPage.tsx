import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"

import {
  ApiError,
  expelCampaignMember,
  getCampaign,
  identityOptions,
  inviteCampaignPlayer,
  markCampaignReady,
  restoreCampaignMember,
  saveIdentity,
  startCampaign,
  type CampaignDetail,
  type IdentityOptions,
  type Visibility,
  type Victory,
} from "../api"
import { Chronicle } from "./Chronicle"
import { InvitePanel } from "./InvitePanel"
import { PlayerIdentity } from "./PlayerIdentity"
import { RoadPreparation, isKnownHex, toggleOwnRoad } from "./RoadPreparation"
import { Banner } from "../form"
import { HexBoard } from "../game/hex/HexBoard"
import { clientNotice, type MessageKey } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"
import { useCampaignLive } from "../useCampaignLive"

const PHASE_KEYS: Record<CampaignDetail["phase"], MessageKey> = {
  recruiting: "phaseRecruiting",
  placing: "phasePlacing",
  preparing: "phasePreparing",
  orders: "phaseOrders",
  battles: "phaseBattles",
  finished: "phaseFinished",
}

function statusKey(phase: CampaignDetail["phase"]): MessageKey {
  if (phase === "finished") return "statusFinished"
  if (phase === "orders" || phase === "battles") return "statusRunning"
  return "statusPrepared"
}

export function CampaignDetailPage() {
  const { t } = useI18n()
  const { id = "" } = useParams()
  const mounted = useRef(true)
  const routeId = useRef(id)
  routeId.current = id
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null)
  const [options, setOptions] = useState<IdentityOptions | null>(null)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    mounted.current = true
    let current = true
    if (!id) {
      setErrors({ campaign: [clientNotice("campaignNotFound")] })
      return
    }
    Promise.all([getCampaign(id), identityOptions()])
      .then(([found, choices]) => {
        if (current) {
          setCampaign(found)
          setOptions(choices)
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

  function accept(updated: CampaignDetail) {
    if (mounted.current && routeId.current === updated.id) setCampaign(updated)
  }

  async function refresh(campaignId: string) {
    accept(await getCampaign(campaignId))
  }

  const pullLive = useCallback(async () => {
    if (!id || busy) return
    try {
      accept(await getCampaign(id))
    } catch {
      /* keep the last good view; next pulse retries */
    }
  }, [busy, id])

  useCampaignLive(campaign?.id ?? null, campaign?.revision ?? null, busy, pullLive)

  async function applyCampaign(action: () => Promise<CampaignDetail>) {
    if (!campaign || busy) return
    setBusy(true)
    try {
      accept(await action())
      if (mounted.current) setErrors({})
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        try {
          await refresh(campaign.id)
        } catch {
          /* keep the mutation error below */
        }
      }
      if (mounted.current) setErrors(presentError(error, "campaignLoadFailed"))
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  async function saveBanner(faction: string, color: string) {
    if (!campaign) throw new Error("Campaign not loaded")
    try {
      accept(await saveIdentity(campaign.id, campaign.revision, faction, color))
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) await refresh(campaign.id)
      throw error
    }
  }

  async function markReady() {
    if (!campaign) throw new Error("Campaign not loaded")
    try {
      accept(await markCampaignReady(campaign.id, campaign.revision))
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) await refresh(campaign.id)
      throw error
    }
  }

  const preparing = campaign?.phase === "preparing" && campaign.roads !== null
  const activeMembers = campaign?.members.filter((member) => member.status === "active") ?? []
  const seatsFull = Boolean(campaign && activeMembers.length === campaign.rules.seats)
  const allReady = activeMembers.length > 0 && activeMembers.every((member) => member.ready)
  const canStart = Boolean(
    campaign &&
      campaign.phase === "recruiting" &&
      campaign.you?.role === "owner" &&
      seatsFull &&
      allReady,
  )
  const canInvite = Boolean(
    campaign &&
      campaign.phase === "recruiting" &&
      (campaign.you?.role === "owner" || campaign.you?.role === "admin") &&
      activeMembers.length < campaign.rules.seats,
  )
  const known = useMemo(
    () => (campaign ? campaign.hexes.filter(isKnownHex) : []),
    [campaign],
  )
  const unknown = useMemo(
    () => (campaign ? campaign.hexes.filter(cell => !cell.known) : []),
    [campaign],
  )
  const players = useMemo(
    () => (campaign ? campaign.members.map(member => ({
      player_id: member.player_id, color: member.color, label: member.alias,
    })) : []),
    [campaign],
  )

  if (!campaign && Object.keys(errors).length === 0) {
    return <p className="quiet">{t("loadingCampaign")}</p>
  }

  return (
    <section className="campaign-detail">
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

      <Banner errors={errors} fields={["form", "session", "campaign", "origin", "csrf", "revision"]} />

      {campaign?.description ? (
        <p className="campaign-blurb">{campaign.description}</p>
      ) : null}

      {campaign?.you && options ? (
        <PlayerIdentity
          key={campaign.id}
          campaign={campaign}
          options={options}
          onSave={saveBanner}
          onReady={markReady}
          busy={busy}
        />
      ) : null}
      {campaign && campaign.phase !== "recruiting" && campaign.hexes.length > 0 ? (
        <section className="campaign-map" aria-labelledby="territory-title">
          <h2 id="territory-title">{t("territoryTitle")}</h2>
          <p className="hint">{t(preparing ? "roadsHint" : "territoryHint")}</p>
          {preparing ? (
            <RoadPreparation
              campaign={campaign}
              busy={busy}
              onChange={action => { void applyCampaign(action) }}
            />
          ) : null}
          <ul className="territory-legend">
            {campaign.members.filter(member => member.color).map(member => {
              const faction = options?.factions.find(item => item.id === member.faction)
              return (
                <li key={member.player_id}>
                  <span className="territory-dot" style={{ backgroundColor: member.color }} aria-hidden="true" />
                  <span><strong>{member.alias}</strong>{faction ? <> · {t(faction.label)}</> : null}</span>
                </li>
              )
            })}
          </ul>
          <HexBoard
            cells={known}
            unknown={unknown}
            anchors={campaign.fortresses}
            players={players}
            onCellClick={
              preparing && campaign.roads && !campaign.roads.ready && !busy
                ? cell => toggleOwnRoad(campaign, cell, action => { void applyCampaign(action) })
                : undefined
            }
          />
        </section>
      ) : null}
      {campaign?.phase === "recruiting" ? (
        <p className="quiet">{t("mapSealedHint")}</p>
      ) : null}
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
              {campaign.members.map((member) => {
                const staff =
                  campaign.you?.role === "owner" || campaign.you?.role === "admin"
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
                        <button
                          type="button"
                          className="button-quiet"
                          disabled={busy}
                          onClick={() => {
                            void applyCampaign(() =>
                              restoreCampaignMember(
                                campaign.id,
                                campaign.revision,
                                member.player_id,
                              ),
                            )
                          }}
                        >
                          {t("restoreMember")}
                        </button>
                        <button
                          type="button"
                          className="button-quiet"
                          disabled={busy}
                          onClick={() => {
                            void applyCampaign(() =>
                              expelCampaignMember(
                                campaign.id,
                                campaign.revision,
                                member.player_id,
                              ),
                            )
                          }}
                        >
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
                {canInvite ? (
                  <InvitePanel
                    busy={busy}
                    onInvite={async (alias) => {
                      try {
                        accept(
                          await inviteCampaignPlayer(
                            campaign.id,
                            campaign.revision,
                            alias,
                          ),
                        )
                      } catch (error: unknown) {
                        if (error instanceof ApiError && error.status === 409) {
                          try {
                            await refresh(campaign.id)
                          } catch {
                            /* keep invite error */
                          }
                        }
                        throw error
                      }
                    }}
                  />
                ) : null}
                {campaign.you?.role === "owner" ? (
                  <button
                    type="button"
                    disabled={busy || !canStart}
                    onClick={() => {
                      void applyCampaign(() => startCampaign(campaign.id, campaign.revision))
                    }}
                  >
                    {busy ? t("startingCampaign") : t("startCampaign")}
                  </button>
                ) : null}
                {campaign.you?.role === "owner" && !canStart ? (
                  <p className="quiet">
                    {!seatsFull ? t("startNeedSeats") : t("startNeedReady")}
                  </p>
                ) : null}
              </>
            ) : null}
          </article>
        </div>
      ) : null}
      {campaign?.phase === "finished" ? (
        <Chronicle entries={campaign.chronicle} members={campaign.members} />
      ) : null}
    </section>
  )
}

function visibilityKey(value: Visibility) {
  if (value === "full") {
    return "visibilityFull" as const
  }
  if (value === "total") {
    return "visibilityTotal" as const
  }
  if (value === "charted") {
    return "visibilityCharted" as const
  }
  if (value === "home") {
    return "visibilityHome" as const
  }
  if (value === "adjacent") {
    return "visibilityAdjacent" as const
  }
  return "visibilityAnonymous" as const
}

function victoryKey(value: Victory) {
  if (value === "armies") {
    return "victoryArmies" as const
  }
  if (value === "fortress") {
    return "victoryFortress" as const
  }
  return "victoryEither" as const
}
