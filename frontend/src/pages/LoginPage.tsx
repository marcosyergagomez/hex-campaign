import { useEffect, useRef, useState, type FormEvent } from "react"
import { Navigate, useNavigate } from "react-router-dom"

import { currentPlayer, login } from "../api"
import { Banner, Field } from "../form"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

export function LoginPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [signedIn, setSignedIn] = useState(false)
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    currentPlayer()
      .then((found) => {
        if (current) {
          setSignedIn(Boolean(found))
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
      await login(email, password)
      if (!mounted.current) {
        return
      }
      setPassword("")
      navigate("/campanas", { replace: true })
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

  if (!ready) {
    return <p className="quiet">{t("checkingSession")}</p>
  }

  if (signedIn) {
    return <Navigate to="/campanas" replace />
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <Banner errors={errors} fields={["form", "credentials", "origin", "session"]} />
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
