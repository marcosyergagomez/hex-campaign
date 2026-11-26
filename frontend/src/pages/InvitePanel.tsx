import { useEffect, useId, useRef, useState } from "react"

import { searchPlayers, type PlayerSuggestion } from "../api"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

type Props = {
  busy?: boolean
  onInvite: (alias: string) => Promise<void>
}

export function InvitePanel({ busy = false, onInvite }: Props) {
  const { t, text } = useI18n()
  const listId = useId()
  const mounted = useRef(true)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<PlayerSuggestion[]>([])
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [sent, setSent] = useState(false)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const needle = query.trim()
    if (needle.length < 1) {
      setSuggestions([])
      return
    }
    let current = true
    const timer = window.setTimeout(() => {
      searchPlayers(needle)
        .then((found) => {
          if (current) setSuggestions(found)
        })
        .catch(() => {
          if (current) setSuggestions([])
        })
    }, 180)
    return () => {
      current = false
      window.clearTimeout(timer)
    }
  }, [query, open])

  async function send() {
    if (!selected || pending || busy) return
    setPending(true)
    setErrors({})
    setSent(false)
    try {
      await onInvite(selected)
      if (!mounted.current) return
      setSent(true)
      setSelected(null)
      setQuery("")
      setSuggestions([])
      setOpen(false)
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "inviteSendFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  return (
    <div className="invite-panel">
      {!open ? (
        <button type="button" className="button-quiet" disabled={busy || pending} onClick={() => setOpen(true)}>
          {t("invitePlayer")}
        </button>
      ) : (
        <div className="invite-form">
          <label className="field">
            <span className="label-text">{t("invitePlayerAlias")}</span>
            <input
              value={query}
              autoFocus
              autoComplete="off"
              spellCheck={false}
              disabled={pending || busy}
              placeholder={t("invitePlayerFilter")}
              aria-controls={listId}
              aria-autocomplete="list"
              onChange={(event) => {
                setQuery(event.target.value)
                setSelected(null)
                setSent(false)
              }}
            />
          </label>
          {suggestions.length > 0 ? (
            <ul id={listId} className="invite-suggestions" role="listbox">
              {suggestions.map((item) => (
                <li key={item.alias}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected === item.alias}
                    className={selected === item.alias ? "is-selected" : undefined}
                    disabled={pending || busy}
                    onClick={() => {
                      setSelected(item.alias)
                      setQuery(item.alias)
                    }}
                  >
                    {item.alias}
                  </button>
                </li>
              ))}
            </ul>
          ) : query.trim().length > 0 ? (
            <p className="quiet">{t("invitePlayerNone")}</p>
          ) : null}
          {Object.keys(errors).length > 0 ? (
            <p className="banner" role="alert">
              {Object.values(errors).flat().map(text).join(" ")}
            </p>
          ) : null}
          <div className="invite-actions">
            <button
              type="button"
              className="button-quiet"
              disabled={pending || busy}
              onClick={() => {
                setOpen(false)
                setQuery("")
                setSelected(null)
                setErrors({})
              }}
            >
              {t("inviteCancel")}
            </button>
            <button type="button" disabled={!selected || pending || busy} onClick={() => { void send() }}>
              {pending ? t("inviteSending") : t("inviteSend")}
            </button>
          </div>
        </div>
      )}
      {sent ? <p className="quiet" role="status">{t("inviteSent")}</p> : null}
    </div>
  )
}
