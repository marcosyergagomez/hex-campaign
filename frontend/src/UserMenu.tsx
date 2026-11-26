import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"

import { useI18n } from "./i18n/language"

function initials(alias: string): string {
  const parts = alias.replace(/_/g, " ").trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return (parts[0]![0]! + parts[1]![0]!).toUpperCase()
  }
  const compact = alias.replace(/[^A-Za-z0-9]/g, "")
  return (compact.slice(0, 2) || "?").toUpperCase()
}

type Props = {
  alias: string
  pending: boolean
  onLogout: () => void
}

export function UserMenu({ alias, pending, onLogout }: Props) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    function onPointer(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onPointer)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onPointer)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div className="circle-menu user-menu" ref={root}>
      <button
        type="button"
        className="circle-trigger avatar-trigger"
        aria-label={t("accountMenu")}
        aria-expanded={open}
        aria-haspopup="menu"
        title={alias}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="avatar-initials" aria-hidden="true">
          {initials(alias)}
        </span>
      </button>
      {open ? (
        <ul className="circle-panel" role="menu" aria-label={t("accountMenu")}>
          <li role="none">
            <p className="circle-panel-alias">{alias}</p>
          </li>
          <li role="none">
            <Link
              role="menuitem"
              to="/perfil"
              onClick={() => setOpen(false)}
            >
              {t("profile")}
            </Link>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              disabled={pending}
              onClick={() => {
                setOpen(false)
                onLogout()
              }}
            >
              {pending ? t("loggingOut") : t("logOut")}
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  )
}
