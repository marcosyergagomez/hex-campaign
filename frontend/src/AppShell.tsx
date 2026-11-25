import { useEffect, useRef, useState } from "react"
import { Link, Navigate, NavLink, Outlet } from "react-router-dom"

import { currentPlayer, logout, type Player } from "./api"
import { Banner } from "./form"
import { LanguageSelect, useI18n } from "./i18n/language"
import { presentError } from "./presentError"

export type AppOutletContext = {
  player: Player
}

export function AppShell() {
  const { t } = useI18n()
  const mounted = useRef(true)
  const [player, setPlayer] = useState<Player | null>(null)
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    currentPlayer()
      .then((found) => {
        if (current) {
          setPlayer(found)
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setErrors(presentError(error, "sessionCheckFailed"))
        }
      })
      .finally(() => {
        if (current) {
          setReady(true)
        }
      })
    return () => {
      current = false
      mounted.current = false
    }
  }, [])

  async function onLogout() {
    setPending(true)
    setErrors({})
    try {
      await logout()
      if (!mounted.current) {
        return
      }
      setPlayer(null)
    } catch (error) {
      if (mounted.current) {
        setErrors(presentError(error, "logOutFailed"))
      }
    } finally {
      if (mounted.current) {
        setPending(false)
      }
    }
  }

  if (!ready) {
    return (
      <main className="app-shell">
        <p className="quiet app-loading">{t("checkingSession")}</p>
      </main>
    )
  }

  if (!player) {
    if (Object.keys(errors).length > 0) {
      return (
        <main className="app-shell">
          <div className="app-body">
            <Banner errors={errors} fields={["form", "session"]} />
            <Link className="text-link" to="/entrar">
              {t("signIn")}
            </Link>
          </div>
        </main>
      )
    }
    return <Navigate to="/entrar" replace />
  }

  return (
    <div className="app-shell">
      <header className="app-bar">
        <div className="app-brand">
          <p className="mark">Hex Campaign</p>
          <nav className="app-nav" aria-label={t("campaignsNav")}>
            <NavLink to="/campanas" end>
              {t("campaignsNav")}
            </NavLink>
            <NavLink to="/mapas">{t("mapsNav")}</NavLink>
            <NavLink to="/campanas/nueva">{t("newCampaign")}</NavLink>
          </nav>
        </div>
        <div className="app-user">
          <LanguageSelect />
          <p className="quiet">
            {t("signedInAs").split("{alias}")[0]}
            <strong>{player.alias}</strong>
            {t("signedInAs").split("{alias}")[1] ?? ""}
          </p>
          <button type="button" className="button-quiet" onClick={onLogout} disabled={pending}>
            {pending ? t("loggingOut") : t("logOut")}
          </button>
        </div>
      </header>
      <Banner errors={errors} fields={["form", "origin", "csrf", "session"]} />
      <main className="app-body">
        <Outlet context={{ player } satisfies AppOutletContext} />
      </main>
    </div>
  )
}
