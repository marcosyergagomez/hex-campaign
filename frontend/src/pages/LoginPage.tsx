import { useEffect, useRef, useState, type FormEvent } from "react"

import { currentPlayer, login, logout, type Player } from "../api"
import { Banner, Field } from "../form"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

export function LoginPage() {
  const { t } = useI18n()
  const mounted = useRef(true)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setErrors({})
    try {
      const signedIn = await login(email, password)
      if (!mounted.current) {
        return
      }
      setPassword("")
      setPlayer(signedIn)
    } catch (error) {
      if (mounted.current) {
        setErrors(presentError(error, "signInFailed"))
      }
    } finally {
      if (mounted.current) {
        setPending(false)
      }
    }
  }

  async function onLogout() {
    setPending(true)
    setErrors({})
    try {
      await logout()
      if (!mounted.current) {
        return
      }
      setPlayer(null)
      setPassword("")
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
    return <p className="quiet">{t("checkingSession")}</p>
  }

  if (player) {
    return (
      <div className="session">
        <h2>{t("sessionOpen")}</h2>
        <SignedIn alias={player.alias} />
        <p className="quiet">{player.email}</p>
        <Banner errors={errors} fields={["form", "origin", "csrf", "session"]} />
        <button type="button" onClick={onLogout} disabled={pending}>
          {pending ? t("loggingOut") : t("logOut")}
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <Banner errors={errors} fields={["form", "credentials", "origin"]} />
      <Field
        label={t("email")}
        name="email"
        type="email"
        autoComplete="username"
        value={email}
        error={errors.email}
        onChange={setEmail}
      />
      <Field
        label={t("password")}
        name="password"
        type="password"
        autoComplete="current-password"
        value={password}
        error={errors.password}
        onChange={setPassword}
      />
      <button type="submit" disabled={pending}>
        {pending ? t("signingIn") : t("signIn")}
      </button>
    </form>
  )
}

function SignedIn({ alias }: { alias: string }) {
  const { t } = useI18n()
  const [before, after = ""] = t("signedInAs").split("{alias}")
  return (
    <p>
      {before}
      <strong>{alias}</strong>
      {after}
    </p>
  )
}
