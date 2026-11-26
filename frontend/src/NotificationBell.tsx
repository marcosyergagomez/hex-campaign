import { useCallback, useEffect, useRef, useState } from "react"
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

function campaignInvite(note: AppNotification): { id: string; name: string; revision: number } | null {
  if (note.kind !== "campaign_invite") return null
  const id = note.payload.campaign_id
  const name = note.payload.campaign_name
  const revision = note.payload.revision
  if (typeof id !== "string" || typeof name !== "string" || typeof revision !== "number") return null
  if (!Number.isInteger(revision) || revision < 1) return null
  return { id, name, revision }
}

export function NotificationBell() {
  const { t, text } = useI18n()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const root = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
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
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onPointer)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onPointer)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const unread = rows.filter((row) => !row.read).length

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
              return (
                <li key={note.id} className={note.read ? undefined : "is-unread"}>
                  <div>
                    <p className="notification-item-title">
                      {invite
                        ? t("notificationCampaignInvite", { name: invite.name })
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
    </div>
  )
}
