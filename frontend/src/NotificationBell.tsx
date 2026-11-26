import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { useNavigate } from "react-router-dom"

import {
  joinCampaign,
  listNotifications,
  markNotificationRead,
  type AppNotification,
} from "./api"
import { useI18n } from "./i18n/language"
import { subscribeLive } from "./liveEvents"
import { presentError } from "./presentError"
import { battleFilmHeld, subscribeBattleFilm } from "./game/hex/useMarchFilm"

function campaignInvite(note: AppNotification): { id: string; name: string; revision: number } | null {
  if (note.kind !== "campaign_invite") return null
  const id = note.payload.campaign_id
  const name = note.payload.campaign_name
  const revision = note.payload.revision
  if (typeof id !== "string" || typeof name !== "string" || typeof revision !== "number") return null
  if (!Number.isInteger(revision) || revision < 1) return null
  return { id, name, revision }
}

function campaignAdmin(note: AppNotification): { id: string; name: string } | null {
  if (note.kind !== "campaign_admin") return null
  const id = note.payload.campaign_id
  const name = note.payload.campaign_name
  if (typeof id !== "string" || typeof name !== "string" || name.length === 0) return null
  return { id, name }
}

function campaignBattle(note: AppNotification): { id: string; name: string } | null {
  if (note.kind !== "campaign_battle") return null
  const id = note.payload.campaign_id
  const name = note.payload.campaign_name
  const battleId = note.payload.battle_id
  if (typeof id !== "string" || typeof name !== "string" || name.length === 0) return null
  if (typeof battleId !== "string" || battleId.length === 0) return null
  return { id, name }
}

export function NotificationBell() {
  const { t, text } = useI18n()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const root = useRef<HTMLDivElement>(null)
  const closeAppointed = useRef<HTMLButtonElement>(null)
  const appointedOpen = useRef(false)
  const [open, setOpen] = useState(false)
  const [filmTick, setFilmTick] = useState(0)
  const [rows, setRows] = useState<AppNotification[]>([])
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  const refresh = useCallback(async () => {
    try {
      const found = await listNotifications()
      if (mounted.current) {
        setRows(found)
        setErrors({})
      }
    } catch (error: unknown) {
      if (mounted.current) {
        setErrors(presentError(error, "notificationsLoadFailed"))
      }
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    return subscribeLive((event) => {
      if (event.type === "notification" || event.type === "reconnect") {
        void refresh()
      }
    })
  }, [refresh])

  useEffect(() => subscribeBattleFilm(() => setFilmTick((value) => value + 1)), [])

  useEffect(() => {
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    if (!open) return
    function onPointer(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !appointedOpen.current) setOpen(false)
    }
    document.addEventListener("mousedown", onPointer)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onPointer)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const unread = rows.filter((row) => !row.read).length
  const ceremony = (() => {
    void filmTick
    for (const note of rows) {
      if (note.read) continue
      const admin = campaignAdmin(note)
      if (admin) return { kind: "admin" as const, note, name: admin.name, campaignId: admin.id }
      const battle = campaignBattle(note)
      if (battle && !battleFilmHeld(battle.id)) {
        return { kind: "battle" as const, note, name: battle.name, campaignId: battle.id }
      }
    }
    return null
  })()
  const appointment = ceremony?.note ?? null
  appointedOpen.current = appointment !== null

  useEffect(() => {
    if (!appointment) return
    const note = appointment
    closeAppointed.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") void acknowledge(note)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [appointment])

  async function acceptInvite(note: AppNotification) {
    const invite = campaignInvite(note)
    if (!invite || pending) return
    setPending(true)
    setErrors({})
    try {
      await joinCampaign(invite.id, invite.revision)
      if (!note.read) await markNotificationRead(note.id)
      await refresh()
      if (mounted.current) {
        setOpen(false)
        navigate(`/campanas/${invite.id}`)
      }
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "inviteAcceptFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  async function acknowledge(note: AppNotification) {
    if (pending) return
    setPending(true)
    try {
      await markNotificationRead(note.id)
      await refresh()
      const battle = campaignBattle(note)
      if (battle && mounted.current) navigate(`/campanas/${battle.id}`)
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "notificationsLoadFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  async function dismiss(note: AppNotification) {
    if (pending || note.read) return
    setPending(true)
    try {
      await markNotificationRead(note.id)
      await refresh()
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "notificationsLoadFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  return (
    <div className="circle-menu notification-bell" ref={root}>
      <button
        type="button"
        className="notification-trigger"
        aria-label={t("notificationsNav")}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => {
          setOpen((value) => !value)
          void refresh()
        }}
      >
        <span className="notification-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.55">
            <path d="M6 9a6 6 0 1 1 12 0c0 7 3 7 3 7H3s3 0 3-7" />
            <path d="M10 19a2 2 0 0 0 4 0" />
          </svg>
        </span>
        {unread > 0 ? <span className="notification-dot">{unread > 9 ? "9+" : unread}</span> : null}
      </button>
      {open ? (
        <div className="circle-panel notification-panel" role="menu" aria-label={t("notificationsNav")}>
          <p className="notification-panel-title">{t("notificationsNav")}</p>
          {Object.keys(errors).length > 0 ? (
            <p className="notification-error" role="alert">
              {Object.values(errors).flat().map(text).join(" ")}
            </p>
          ) : null}
          {rows.length === 0 ? <p className="quiet">{t("notificationsEmpty")}</p> : null}
          <ul className="notification-list">
            {rows.map((note) => {
              const invite = campaignInvite(note)
              const admin = campaignAdmin(note)
              const battle = campaignBattle(note)
              return (
                <li key={note.id} className={note.read ? undefined : "is-unread"}>
                  <div>
                    <p className="notification-item-title">
                      {invite
                        ? t("notificationCampaignInvite", { name: invite.name })
                        : admin
                          ? t("notificationCampaignAdmin", { name: admin.name })
                          : battle
                            ? t("notificationCampaignBattle", { name: battle.name })
                            : t("notificationGeneric")}
                    </p>
                    {!note.read ? <span className="notification-new">{t("notificationUnread")}</span> : null}
                  </div>
                  <div className="notification-item-actions">
                    {invite && !note.read ? (
                      <button type="button" disabled={pending} onClick={() => { void acceptInvite(note) }}>
                        {t("inviteAccept")}
                      </button>
                    ) : null}
                    {!note.read ? (
                      <button
                        type="button"
                        className="button-quiet"
                        disabled={pending}
                        onClick={() => { void dismiss(note) }}
                      >
                        {t("notificationDismiss")}
                      </button>
                    ) : null}
                    {invite && note.read ? (
                      <button
                        type="button"
                        className="button-quiet"
                        onClick={() => {
                          setOpen(false)
                          navigate(`/campanas/${invite.id}`)
                        }}
                      >
                        {t("openCampaign")}
                      </button>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
      {ceremony
        ? createPortal(
            <div className="appoint-modal">
              <div className="appoint-panel" role="dialog" aria-modal="true" aria-labelledby="appoint-title">
                <img
                  className={ceremony.kind === "battle" ? "is-battle" : undefined}
                  src={ceremony.kind === "battle" ? "/battle-opened.jpg" : "/commander-appointed.jpg"}
                  alt=""
                />
                <div className="appoint-copy">
                  <h2 id="appoint-title">
                    {ceremony.kind === "battle" ? t("battleOpenedTitle") : t("adminAppointedTitle")}
                  </h2>
                  <p>
                    {ceremony.kind === "battle"
                      ? t("battleOpenedBody", { name: ceremony.name })
                      : t("adminAppointedBody", { name: ceremony.name })}
                  </p>
                  <button
                    ref={closeAppointed}
                    type="button"
                    disabled={pending}
                    onClick={() => { void acknowledge(ceremony.note) }}
                  >
                    {ceremony.kind === "battle" ? t("battleOpenedClose") : t("adminAppointedClose")}
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}
