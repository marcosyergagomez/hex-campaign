import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"

import {
  ApiError,
  claimCampaignColor,
  closeCampaignOrders,
  expelCampaignMember,
  judgeCampaignBattle,
  promoteCampaignMember,
  revertCampaignTurn,
  getCampaign,
  identityOptions,
  lockCampaignOrders,
  inviteCampaignPlayer,
  applyFortMove,
  placeCampaignArmies,
  confirmCampaignPlacement,
  standCampaignArmy,
  markCampaignReady,
  restoreCampaignMember,
  saveIdentity,
  startCampaign,
  type CampaignDetail,
  type IdentityOptions,
  type Visibility,
  type Victory,
} from "../api"
import { ArmyModal, ArmyRosterPanel } from "./ArmySheets"
import { DeployTray } from "./DeployTray"
import { seatAroundFort } from "./seatAroundFort"
import { Chronicle } from "./Chronicle"
import { InvitePanel } from "./InvitePanel"
import { PlayerIdentity } from "./PlayerIdentity"
import { RoadPreparation, isKnownHex, toggleOwnRoad } from "./RoadPreparation"
import { Banner } from "../form"
import { armyNeedsSheet, ownIndexes, toBoardTokens } from "../game/hex/boardTokens"
import { deployReach } from "../game/hex/disk"
import { HexBoard } from "../game/hex/HexBoard"
import {
  exitCostOf,
  gazeReach,
  hexDistance,
  moveBudget,
  routeTo,
  spotKey,
  type Spot,
} from "../game/hex/orders"
import { setBattleFilm, useMarchFilm } from "../game/hex/useMarchFilm"
import { clientNotice, type MessageKey } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"
import { useCampaignLive } from "../useCampaignLive"
import type { LiveSeat } from "../liveEvents"

const PHASE_KEYS: Record<CampaignDetail["phase"], MessageKey> = {
  recruiting: "phaseRecruiting",
  placing: "phasePlacing",
  preparing: "phasePreparing",
  orders: "phaseOrders",
  battles: "phaseBattles",
  finished: "phaseFinished",
}

function paintSeats(
  current: CampaignDetail | null,
  revision: number,
  seats: LiveSeat[],
): CampaignDetail | null {
  if (!current || revision < current.revision) return current
  const byId = new Map(seats.map((seat) => [seat.player_id, seat]))
  const apply = (member: CampaignDetail["members"][number]) => {
    const seat = byId.get(member.player_id)
    if (!seat || (member.color === seat.color && member.ready === seat.ready)) return member
    return { ...member, color: seat.color, ready: seat.ready }
  }
    const members = current.members.map(apply)
    const you = current.you ? apply(current.you) : current.you
    if (members.every((member, index) => member === current.members[index]) && you === current.you) {
      return current
    }
  // The event revision belongs to a document that has not arrived yet.
  // Stamping it now makes that document look old, and the map stays stale.
  return { ...current, members, you }
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
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const [orderPaths, setOrderPaths] = useState<Record<string, Spot[]>>({})
  const orderPathsRef = useRef(orderPaths)
  orderPathsRef.current = orderPaths
  const [selectedToken, setSelectedToken] = useState<string | null>(null)
  const spotAt = useRef<((clientX: number, clientY: number) => { q: number; r: number } | null) | null>(null)
  const skipClick = useRef(false)
  const fortMove = useRef({
    running: false,
    revision: 0,
    pending: null as null | {
      fortress: { q: number; r: number }
      armies: Record<string, { q: number; r: number }>
    },
  })
  const [sheetArmy, setSheetArmy] = useState<string | null>(null)
  const [locking, setLocking] = useState(false)

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

  function accept(updated: CampaignDetail, force = false) {
    if (!mounted.current || routeId.current !== updated.id) return
    setCampaign((current) => {
      // Equal revisions stay. A late reload must not pull a fortress back after the click.
      if (!force && current && current.id === updated.id && updated.revision <= current.revision) {
        return current
      }
      return updated
    })
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

  useCampaignLive(
    campaign?.id ?? null,
    campaign?.revision ?? null,
    busy,
    pullLive,
    (revision, seats) => {
      setCampaign((current) => paintSeats(current, revision, seats))
    },
  )

  async function mutateCampaign(action: () => Promise<CampaignDetail>) {
    if (!campaign) throw new Error("Campaign not loaded")
    const snapshot = campaign
    try {
      accept(await action())
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        try {
          await refresh(snapshot.id)
        } catch {
          /* keep the mutation error below */
        }
      }
      throw error
    }
  }

  async function applyCampaign(action: () => Promise<CampaignDetail>) {
    if (!campaign || busy) return
    setBusy(true)
    try {
      await mutateCampaign(action)
      if (mounted.current) setErrors({})
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "campaignLoadFailed"))
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  async function saveBanner(faction: string, color: string) {
    if (!campaign) throw new Error("Campaign not loaded")
    await mutateCampaign(() => saveIdentity(campaign.id, campaign.revision, faction, color))
  }

  async function claimColor(color: string) {
    if (!campaign) throw new Error("Campaign not loaded")
    await mutateCampaign(() => claimCampaignColor(campaign.id, campaign.revision, color))
  }

  async function markReady(faction: string, color: string, ready: boolean) {
    if (!campaign) throw new Error("Campaign not loaded")
    setBusy(true)
    try {
      let revision = campaign.revision
      const you = campaign.you
      if (ready && (!you || you.faction !== faction || you.color !== color)) {
        const saved = await saveIdentity(campaign.id, revision, faction, color)
        accept(saved)
        revision = saved.revision
      }
      accept(await markCampaignReady(campaign.id, revision, ready))
      if (mounted.current) setErrors({})
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, ready ? "lobbyReadyFailed" : "identitySaveFailed"))
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  const stage = campaign ? prepOf(campaign) : null
  const playing = Boolean(campaign && campaign.phase !== "recruiting")
  const staff = campaign?.you?.status === "active" &&
    (campaign.you.role === "owner" || campaign.you.role === "admin")
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
  const tokens = useMemo(
    () => (campaign ? toBoardTokens(campaign, t) : []),
    [campaign, t],
  )
  const film = useMarchFilm(campaign)
  useEffect(() => {
    if (!campaign) return
    setBattleFilm(campaign.id, film.playing)
    return () => setBattleFilm(campaign.id, false)
  }, [campaign, film.playing])
  const ordering = Boolean(
    campaign &&
      campaign.phase === "orders" &&
      campaign.you?.status === "active" &&
      !campaign.you.orders_locked &&
      !film.playing,
  )
  useEffect(() => {
    setOrderPaths({})
    setSelectedToken(null)
  }, [campaign?.id, campaign?.turn])

  function plan(armyId: string, target: Spot) {
    if (!campaign?.you) return
    const army = campaign.armies.find((item) => item.id === armyId && item.player_id === campaign.you?.player_id)
    if (!army || army.q === null || army.r === null || army.destroyed) return
    const plots = new Map(campaign.hexes.map((cell) => [spotKey(cell), cell.known
      ? { known: true, ground: cell.ground, road: cell.road, bridge: cell.bridge }
      : { known: false }]))
    const board = new Set(campaign.hexes.map(spotKey))
    const forts = new Set(campaign.fortresses.map(spotKey))
    const blocked = new Set(
      campaign.armies.flatMap((item) => {
        if (item.kind !== "army" || item.player_id === army.player_id || item.destroyed) return []
        if (item.q === null || item.r === null) return []
        return [spotKey({ q: item.q, r: item.r })]
      }),
    )
    const next = routeTo({
      origin: { q: army.q, r: army.r },
      path: orderPathsRef.current[armyId] ?? [],
      target,
      budget: moveBudget(campaign.rules.movement, army.kind),
      paid: army.paid,
      kind: army.kind,
      plots,
      board,
      forts,
      blocked,
    })
    if (!next) return
    const taken = new Set(
      campaign.armies.flatMap((item) => {
        if (item.id === armyId || item.kind !== "army" || item.player_id !== army.player_id) return []
        const path = orderPathsRef.current[item.id]
        if (item.q === null || item.r === null) return []
        const end = path && path.length > 0 ? path[path.length - 1] : { q: item.q, r: item.r }
        return [spotKey(end)]
      }),
    )
    if (next.length > 0 && army.kind === "army" && taken.has(spotKey(next[next.length - 1]))) return
    setOrderPaths((current) => ({ ...current, [armyId]: next }))
  }

  const drawnPaths = useMemo(() => {
    if (!campaign?.you) return []
    const own = campaign.armies.filter((army) => army.player_id === campaign.you?.player_id && army.q !== null && army.r !== null)
    const line = (army: (typeof own)[number], path: Spot[]) => {
      if (army.q === null || army.r === null || path.length === 0) return []
      return [{ spots: [{ q: army.q, r: army.r }, ...path], selected: army.id === selectedToken }]
    }
    if (ordering) {
      return own.flatMap((army) => line(army, orderPaths[army.id] ?? []))
    }
    if (campaign.you.orders_locked) {
      return own.flatMap((army) => line(army, campaign.orders[army.id] ?? []))
    }
    return []
  }, [campaign, ordering, orderPaths, selectedToken])
  const tokenNotes = useMemo(() => {
    if (!campaign?.you || campaign.phase !== "orders") return {}
    const notes: Record<string, string> = {}
    for (const army of campaign.armies) {
      if (army.player_id !== campaign.you.player_id || army.destroyed || army.q === null || army.r === null) {
        continue
      }
      const cell = campaign.hexes.find((hex) => hex.q === army.q && hex.r === army.r)
      const cost = exitCostOf(
        cell?.known
          ? { known: true, ground: cell.ground, road: cell.road, bridge: cell.bridge }
          : { known: false },
      )
      const list = army.kind === "army" && army.roster
        ? `\n${army.roster.length > 180 ? `${army.roster.slice(0, 180)}…` : army.roster}`
        : ""
      notes[army.id] = `${t("ordersPaidHint", {
        paid: String(army.paid),
        cost: String(cost),
        budget: String(moveBudget(campaign.rules.movement, army.kind)),
      })}${list}`
    }
    return notes
  }, [campaign, t])
  const movableIds = useMemo(() => new Set(
    campaign?.you && (ordering || stage === "armies")
      ? campaign.armies.flatMap((army) =>
        army.player_id === campaign.you?.player_id && !army.destroyed && army.q !== null ? [army.id] : [],
      )
      : [],
  ), [campaign, ordering, stage])
  const deployPieces = useMemo(() => {
    if (!campaign?.you || stage !== "armies") return []
    const marks = ownIndexes(campaign)
    const member = campaign.members.find((item) => item.player_id === campaign.you?.player_id)
    return campaign.armies.flatMap((army) => {
      if (army.player_id !== campaign.you?.player_id || army.destroyed) return []
      return [{
        id: army.id,
        kind: army.kind,
        faction: army.race || member?.faction || "",
        color: member?.color || "#c0a062",
        label: army.kind === "explorer" ? t("unitExplorer") : (army.commander || t("armyUnnamed")),
        mark: marks.get(army.id),
        placed: army.q !== null,
        attention: army.kind === "army" && armyNeedsSheet(army, campaign.rules.roster_required),
      }]
    })
  }, [campaign, stage, t])
  const watch = useMemo(() => {
    if (!campaign?.you) return null
    const you = campaign.you.player_id
    if (!film.playing && !ordering) return null
    const spots = new Map<string, Spot>()
    for (const army of campaign.armies) {
      if (army.player_id !== you || army.destroyed || army.q === null || army.r === null) continue
      if (film.playing && film.spots?.[army.id]) {
        spots.set(army.id, film.spots[army.id])
        continue
      }
      const path = orderPaths[army.id]
      spots.set(army.id, path && path.length > 0 ? path[path.length - 1] : { q: army.q, r: army.r })
    }
    return spots
  }, [campaign, film.playing, film.spots, ordering, orderPaths])
  const dimmed = useMemo(
    () => (campaign ? watchedDim(campaign, watch) : []),
    [campaign, watch],
  )
  const shownTokens = useMemo(() => {
    if (!film.playing || !campaign) return tokens
    // Snapshot: keep every marching token visible even if fog hid it after the turn.
    const ids = new Set(tokens.map((token) => token.id))
    const glimpsed = campaign.playback.moves.flatMap((move) => {
      if (ids.has(move.army_id)) return []
      return [{
        id: move.army_id,
        q: move.from.q,
        r: move.from.r,
        kind: move.kind ?? "army" as const,
        faction: move.faction ?? "",
        color: move.color || "#c0a062",
        label: move.name || t("unitArmy"),
      }]
    })
    return [...tokens, ...glimpsed]
  }, [campaign, film.playing, t, tokens])
  const traces = useMemo(() => {
    if (!campaign || film.playing) return []
    return campaign.playback.moves.flatMap((move) => {
      if (!move.lost) return []
      const spots = [move.from, ...move.steps]
      const unique = spots.filter((spot, index) => index === 0 || spot.q !== spots[index - 1].q || spot.r !== spots[index - 1].r)
      return unique.length > 0 ? [{ spots: unique, color: move.color || "#c0a062" }] : []
    })
  }, [campaign, film.playing])
  const lostNames = traces.length === 0 || !campaign
    ? ""
    : campaign.playback.moves
      .filter((move) => move.lost)
      .map((move) => move.name || t("unitArmy"))
      .join(", ")
  const clashes = useMemo(() => {
    if (!campaign) return []
    const pairs: { from: Spot; to: Spot }[] = []
    for (const battle of campaign.battles) {
      if (battle.result !== null || battle.reverted || battle.army_ids.length < 2) continue
      const placed = battle.army_ids.flatMap((id) => {
        const army = campaign.armies.find((item) => item.id === id && !item.destroyed && item.q !== null && item.r !== null)
        if (!army || army.q === null || army.r === null) return []
        const rest = { q: army.q, r: army.r }
        return [{ spot: film.spots?.[id] ?? rest, rest }]
      })
      if (placed.length < 2) continue
      const met = placed.every((item) => item.spot.q === item.rest.q && item.spot.r === item.rest.r)
      if (film.playing && !met) continue
      pairs.push({ from: placed[0].spot, to: placed[1].spot })
    }
    return pairs
  }, [campaign, film.playing, film.spots])

  async function lockTurn() {
    if (!campaign?.you || locking || busy) return
    const orders: Record<string, Spot[]> = {}
    for (const army of campaign.armies) {
      if (army.player_id !== campaign.you.player_id || army.destroyed || army.q === null) continue
      orders[army.id] = orderPaths[army.id] ?? []
    }
    const campaignId = campaign.id
    let revision = campaign.revision
    setLocking(true)
    setBusy(true)
    try {
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          accept(await lockCampaignOrders(campaignId, revision, orders))
          if (mounted.current) setErrors({})
          return
        } catch (error: unknown) {
          if (!(error instanceof ApiError) || error.status !== 409 || attempt === 1) throw error
          const fresh = await getCampaign(campaignId)
          accept(fresh, true)
          if (fresh.revision === revision) throw error
          revision = fresh.revision
        }
      }
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "ordersFailed"))
    } finally {
      if (mounted.current) {
        setLocking(false)
        setBusy(false)
      }
    }
  }

  async function placeFort(cell: { q: number; r: number; owner_id?: string | null }) {
    if (!campaign?.you) return
    const you = campaign.you.player_id
    const known = campaign.hexes.find((hex) => hex.q === cell.q && hex.r === cell.r)
    if (!known?.known) return
    const owner = cell.owner_id ?? known.owner_id
    if (owner !== you) return
    const home = new Set(
      campaign.hexes.flatMap((hex) => (
        hex.known && hex.owner_id === you ? [`${hex.q},${hex.r}`] : []
      )),
    )
    const standable = new Set(
      campaign.hexes.flatMap((hex) => {
        if (!hex.known || hex.owner_id !== you || (hex.ground && BLOCKED_GROUND.has(hex.ground))) return []
        return [`${hex.q},${hex.r}`]
      }),
    )
    for (const fort of campaign.fortresses) {
      if (fort.player_id !== you) standable.delete(`${fort.q},${fort.r}`)
    }
    const own = campaign.armies.filter((army) => army.player_id === campaign.you?.player_id && !army.destroyed)
    const spots = seatAroundFort({ q: cell.q, r: cell.r }, home, own, standable)
    if (!spots) {
      setErrors({ campaign: [clientNotice("prepFortFailed")] })
      return
    }
    const fortress = { q: cell.q, r: cell.r }
    setCampaign((current) => current ? paintFort(current, you, fortress, spots) : current)
    const job = fortMove.current
    if (!job.running) job.revision = Math.max(job.revision, campaign.revision)
    job.pending = { fortress, armies: spots }
    if (job.running) return
    job.running = true
    setBusy(true)
    try {
      while (job.pending) {
        const next = job.pending
        job.pending = null
        const moved = await placeCampaignArmies(campaign.id, job.revision, next.fortress, next.armies)
        job.revision = moved.revision
        const queued = job.pending !== null
        if (!mounted.current) return
        setCampaign((current) => {
          if (!current || moved.revision < current.revision) return current
          if (queued) return { ...current, revision: moved.revision }
          return applyFortMove(current, moved)
        })
      }
      if (mounted.current) setErrors({})
    } catch (error: unknown) {
      job.pending = null
      if (mounted.current) setErrors(presentError(error, "prepFortFailed"))
      try {
        const fresh = await getCampaign(campaign.id)
        job.revision = fresh.revision
        accept(fresh, true)
      } catch {
        /* the banner already says the click failed */
      }
    } finally {
      job.running = false
      if (mounted.current) setBusy(false)
    }
  }

  async function saveFort() {
    if (!campaign || busy) return
    setBusy(true)
    try {
      while (fortMove.current.running) {
        await new Promise((resolve) => window.setTimeout(resolve, 40))
      }
      const revision = Math.max(campaign.revision, fortMove.current.revision)
      try {
        const saved = await confirmCampaignPlacement(campaign.id, revision)
        fortMove.current.revision = saved.revision
        accept(saved, true)
        if (mounted.current) setErrors({})
      } catch (error: unknown) {
        const fresh = await getCampaign(campaign.id).catch(() => null)
        if (!fresh || !mounted.current) throw error
        fortMove.current.revision = fresh.revision
        accept(fresh, true)
        if (prepOf(fresh) === "fort" && error instanceof ApiError && error.status === 409) {
          const saved = await confirmCampaignPlacement(campaign.id, fresh.revision)
          fortMove.current.revision = saved.revision
          accept(saved, true)
          if (mounted.current) setErrors({})
          return
        }
        if (prepOf(fresh) !== "fort") {
          if (mounted.current) setErrors({})
          return
        }
        throw error
      }
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "prepFortFailed"))
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  function dropPiece(id: string, cell: { q: number; r: number }) {
    skipClick.current = true
    queueMicrotask(() => {
      skipClick.current = false
    })
    setSelectedToken(id)
    void placePiece(cell, id)
  }

  async function placePiece(cell: { q: number; r: number }, armyId?: string) {
    const id = armyId ?? selectedToken
    if (!campaign?.you || !id) return
    const army = campaign.armies.find((item) =>
      item.id === id && item.player_id === campaign.you?.player_id && !item.destroyed,
    )
    if (!army || (army.q === cell.q && army.r === cell.r)) return
    const fort = campaign.fortresses.find((item) => item.player_id === campaign.you?.player_id)
    if (!fort) return
    const allowed = standSpots(fort, campaign.hexes, deployReach(campaign.rules.map_size))
    if (!allowed.some((spot) => spot.q === cell.q && spot.r === cell.r)) return
    await applyCampaign(() => standCampaignArmy(campaign.id, campaign.revision, id, cell.q, cell.r))
  }

  if (!campaign && Object.keys(errors).length === 0) {
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

      <Banner errors={errors} fields={["form", "session", "campaign", "origin", "csrf", "revision"]} />

      {!playing && campaign?.description ? (
        <p className="campaign-blurb">{campaign.description}</p>
      ) : null}

      {playing && adminOpen && staff && campaign ? (
        <AdminPanel
          campaign={campaign}
          busy={busy}
          onRevert={() => applyCampaign(() => revertCampaignTurn(campaign.id, campaign.revision))}
          onCloseOrders={() => applyCampaign(() => closeCampaignOrders(campaign.id, campaign.revision))}
          onPromote={(playerId) => applyCampaign(() =>
            promoteCampaignMember(campaign.id, campaign.revision, playerId))}
          onExpel={(playerId) => applyCampaign(() =>
            expelCampaignMember(campaign.id, campaign.revision, playerId))}
          onRestore={(playerId) => applyCampaign(() =>
            restoreCampaignMember(campaign.id, campaign.revision, playerId))}
          onJudge={(battleId, result) => applyCampaign(() =>
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
              busy={busy}
              canInvite={false}
              canStart={false}
              seatsFull={seatsFull}
              onInvite={undefined}
              onRestore={(playerId) => {
                void applyCampaign(() =>
                  restoreCampaignMember(campaign.id, campaign.revision, playerId),
                )
              }}
              onExpel={(playerId) => {
                void applyCampaign(() =>
                  expelCampaignMember(campaign.id, campaign.revision, playerId),
                )
              }}
            />
          </div>
        </div>
      ) : null}

      {campaign?.phase === "recruiting" && campaign.you && options ? (
        <PlayerIdentity
          key={campaign.id}
          campaign={campaign}
          options={options}
          onSave={saveBanner}
          onClaim={claimColor}
          onReady={markReady}
          busy={busy}
        />
      ) : null}
      {playing && campaign && campaign.hexes.length > 0 ? (
        <section className="campaign-map is-play" aria-label={t("territoryTitle")}>
          <div className="play-map-meta">
            {stage && campaign.you ? (
              <section className={`prep-stage is-${stage}`}>
                {stage === "waiting" ? null : (
                  <p className="prep-stage-kicker">
                    {stage === "fort" ? "1" : stage === "roads" ? "2" : "3"} / 3
                  </p>
                )}
                <h2>
                  {stage === "fort"
                    ? t("prepFortTitle")
                    : stage === "roads"
                      ? t("prepRoadsTitle")
                      : stage === "armies"
                        ? t("prepNamesTitle")
                        : t("prepWaitingTitle")}
                </h2>
                <p>
                  {stage === "fort"
                    ? t("prepFortHint")
                    : stage === "roads"
                      ? t("roadsHint")
                      : stage === "armies"
                        ? t("prepNamesHint")
                        : t("prepWaitingHint")}
                </p>
                {stage === "armies" ? <MissingSheets pieces={deployPieces} rosterRequired={campaign.rules.roster_required} /> : null}
                {stage === "fort" ? (
                  <button
                    type="button"
                    disabled={busy || !campaign.fortresses.some((fort) => fort.player_id === campaign.you?.player_id)}
                    onClick={() => { void saveFort() }}
                  >
                    {t("prepSave")}
                  </button>
                ) : null}
                {stage === "roads" ? (
                  <RoadPreparation
                    campaign={campaign}
                    busy={busy}
                    onChange={action => { void applyCampaign(action) }}
                  />
                ) : null}
                {stage === "waiting" ? (
                  <WaitingNames campaign={campaign} />
                ) : null}
              </section>
            ) : null}
            {lostNames ? <p className="hint">{t("sightLost", { name: lostNames })}</p> : null}
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
          </div>
          <div className={stage === "armies" ? "play-board has-tray" : "play-board"}>
          {stage === "armies" ? (
            <DeployTray
              pieces={deployPieces}
              selectedId={selectedToken}
              onSelect={setSelectedToken}
              onOpen={setSheetArmy}
              onDropAt={dropPiece}
              spotAt={spotAt}
            />
          ) : null}
          <HexBoard
            cells={known}
            unknown={unknown}
            dimmed={dimmed}
            traces={traces}
            clashes={clashes}
            mapTools={false}
            anchors={campaign.fortresses}
            players={players}
            tokens={stage === "fort" || stage === "roads" ? [] : shownTokens}
            tokensQuiet={stage === "fort"}
            marks={placementMarks(campaign)}
            markColor={campaign.you?.color || undefined}
            tokenNotes={tokenNotes}
            orderPaths={drawnPaths}
            tokenSpots={film.spots}
            movableIds={movableIds}
            selectedTokenId={selectedToken}
            sliding={film.playing}
            spotAtRef={spotAt}
            onOrderToken={ordering ? (id, spot, phase) => {
              setSelectedToken(id)
              if (phase === "move") plan(id, spot)
            } : undefined}
            onTokenDrop={stage === "armies" && !busy ? dropPiece : undefined}
            onTokenInspect={(id) => {
              const army = campaign.armies.find((item) => item.id === id)
              if (army?.kind === "army") setSheetArmy(id)
            }}
            onCellClick={
              ordering
                ? (cell) => {
                    const token = campaign.armies.find((army) =>
                      army.player_id === campaign.you?.player_id &&
                      !army.destroyed &&
                      army.q === cell.q &&
                      army.r === cell.r,
                    )
                    if (token) {
                      setSelectedToken(token.id)
                      return
                    }
                    if (selectedToken) plan(selectedToken, cell)
                  }
                : stage === "armies" && selectedToken && !busy
                  ? (cell) => {
                      if (skipClick.current) return
                      void placePiece(cell)
                    }
                : stage === "fort"
                  ? (cell) => { void placeFort(cell) }
                : stage === "roads" && campaign.roads && !campaign.roads.ready && !busy
                  ? cell => toggleOwnRoad(campaign, cell, action => { void applyCampaign(action) })
                  : undefined
            }
          />
          </div>
          {sheetArmy ? (
            <ArmyModal
              campaign={campaign}
              armyId={sheetArmy}
              busy={busy}
              onClose={() => setSheetArmy(null)}
              onSave={async (action) => {
                setBusy(true)
                try {
                  accept(await action())
                  if (mounted.current) setErrors({})
                } catch (error: unknown) {
                  if (mounted.current) setErrors(presentError(error, "identitySaveFailed"))
                  throw error
                } finally {
                  if (mounted.current) setBusy(false)
                }
              }}
            />
          ) : null}
          {campaign.phase === "orders" ? (
            <div className="orders-dock">
              <p className="hint">{film.playing ? t("ordersFilm") : t("ordersHint")}</p>
              {campaign.you?.orders_locked ? (
                <p className="quiet" role="status">{t("ordersFixed")}</p>
              ) : (
                <button type="button" disabled={!ordering || locking || busy} onClick={() => { void lockTurn() }}>
                  {locking ? t("ordersFixing") : t("ordersFix")}
                </button>
              )}
              {campaign.members.some((member) => member.orders_locked && member.player_id !== campaign.you?.player_id) ? (
                <p className="quiet">
                  {t("ordersFixedNames", {
                    names: campaign.members
                      .filter((member) => member.orders_locked && member.player_id !== campaign.you?.player_id)
                      .map((member) => member.alias)
                      .join(", "),
                  })}
                </p>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
      {campaign?.phase === "recruiting" ? (
        <p className="quiet">{t("mapSealedHint")}</p>
      ) : null}
      {campaign?.phase === "recruiting" ? (
        <div className="detail-grid">
          <RulesPanel campaign={campaign} />
          <MembersPanel
            campaign={campaign}
            busy={busy}
            canInvite={canInvite}
            canStart={canStart}
            seatsFull={seatsFull}
            onInvite={
              canInvite
                ? async (alias) => {
                    await mutateCampaign(() =>
                      inviteCampaignPlayer(campaign.id, campaign.revision, alias),
                    )
                  }
                : undefined
            }
            onStart={() => {
              void applyCampaign(() => startCampaign(campaign.id, campaign.revision))
            }}
            onRestore={(playerId) => {
              void applyCampaign(() =>
                restoreCampaignMember(campaign.id, campaign.revision, playerId),
              )
            }}
            onExpel={(playerId) => {
              void applyCampaign(() =>
                expelCampaignMember(campaign.id, campaign.revision, playerId),
              )
            }}
          />
        </div>
      ) : null}
      {campaign?.phase === "finished" ? (
        <Chronicle entries={campaign.chronicle} members={campaign.members} />
      ) : null}
    </section>
  )
}

function RulesPanel({ campaign }: { campaign: CampaignDetail }) {
  const { t } = useI18n()
  return (
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
        <li>
          {t("ruleRosterRequired")}: {campaign.rules.roster_required ? t("armyRosterRequiredShort") : t("armyRosterOptional")}
        </li>
      </ul>
    </article>
  )
}

function AdminPanel({
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

function MembersPanel({
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
                    onClick={() => onRestore(member.player_id)}
                  >
                    {t("restoreMember")}
                  </button>
                  <button
                    type="button"
                    className="button-quiet"
                    disabled={busy}
                    onClick={() => onExpel(member.player_id)}
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
          {canInvite && onInvite ? (
            <InvitePanel busy={busy} onInvite={onInvite} />
          ) : null}
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

const BLOCKED_GROUND = new Set(["montana_rocosa", "lago", "acantilado"])

function standSpots(fort: Spot, hexes: CampaignDetail["hexes"], reach: number): Spot[] {
  return hexes.flatMap((cell) => {
    if (!cell.known || (cell.ground && BLOCKED_GROUND.has(cell.ground))) return []
    if (hexDistance(cell, fort) > reach) return []
    return [{ q: cell.q, r: cell.r }]
  })
}

function MissingSheets({
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

function WaitingNames({ campaign }: { campaign: CampaignDetail }) {
  const { t } = useI18n()
  const names = campaign.members
    .filter((member) => member.status === "active" && !campaign.prep_done.includes(member.player_id))
    .map((member) => member.alias)
    .join(", ")
  if (!names) return null
  return <p className="quiet">{t("prepWaitingNames", { names })}</p>
}

function paintFort(
  campaign: CampaignDetail,
  playerId: string,
  fortress: { q: number; r: number },
  spots: Record<string, { q: number; r: number }>,
): CampaignDetail {
  const known = campaign.fortresses.some((fort) => fort.player_id === playerId)
  const fortresses = known
    ? campaign.fortresses.map((fort) => (
      fort.player_id === playerId ? { ...fort, q: fortress.q, r: fortress.r } : fort
    ))
    : [...campaign.fortresses, { player_id: playerId, ...fortress }]
  const armies = campaign.armies.map((army) => {
    const spot = spots[army.id]
    return spot ? { ...army, q: spot.q, r: spot.r } : army
  })
  return { ...campaign, fortresses, armies }
}

function prepOf(campaign: CampaignDetail): "fort" | "roads" | "armies" | "waiting" | null {
  if (
    campaign.prep === "fort" ||
    campaign.prep === "roads" ||
    campaign.prep === "armies" ||
    campaign.prep === "waiting"
  ) {
    return campaign.prep
  }
  if (campaign.phase === "placing" || (campaign.phase === "preparing" && campaign.fort_open)) return "fort"
  if (campaign.phase === "preparing" && !campaign.naming) return "roads"
  if (campaign.naming) return "armies"
  return null
}

function placementMarks(campaign: CampaignDetail): Spot[] {
  const you = campaign.you?.player_id
  if (!you) return []
  const stage = prepOf(campaign)
  if (stage === "fort") {
    if (campaign.lobby_ready.includes(you)) return []
    return campaign.hexes.flatMap((cell) => {
      if (!cell.known || cell.owner_id !== you || (cell.ground && BLOCKED_GROUND.has(cell.ground))) return []
      return [{ q: cell.q, r: cell.r }]
    })
  }
  if (stage !== "armies") return []
  const fort = campaign.fortresses.find((item) => item.player_id === you)
  return fort ? standSpots(fort, campaign.hexes, deployReach(campaign.rules.map_size)) : []
}

function watchedDim(campaign: CampaignDetail, watch: Map<string, Spot> | null): Spot[] {
  if (campaign.rules.visibility === "full" || campaign.rules.visibility === "total") return []
  const you = campaign.you?.player_id
  if (!you || watch === null) {
    return campaign.hexes.flatMap((cell) => cell.known && !cell.sight ? [{ q: cell.q, r: cell.r }] : [])
  }
  const known = campaign.hexes.filter(isKnownHex)
  const groundAt = new Map(known.map((cell) => [spotKey(cell), cell.ground]))
  const eyes = campaign.armies.flatMap((army) => {
    if (army.player_id !== you || army.destroyed || army.q === null || army.r === null) return []
    const at = watch.get(army.id) ?? { q: army.q, r: army.r }
    return [{ at, reach: gazeReach(groundAt.get(spotKey(at)), army.kind === "explorer") }]
  })
  return known.flatMap((cell) => {
    if (cell.owner_id === you) return []
    if (eyes.some((eye) => hexDistance(cell, eye.at) <= eye.reach)) return []
    return [{ q: cell.q, r: cell.r }]
  })
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
