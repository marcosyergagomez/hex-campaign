import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"

import { requestPasswordReset } from "../api"
import { Banner, Field } from "../form"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

export function ResetPasswordPage() {
  const { t } = useI18n()
  const mounted = useRef(true)
  const [email, setEmail] = useState("")
  const [pending, setPending] = useState(false)
  const [sent, setSent] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setErrors({})
    setSent(false)
    try {
      await requestPasswordReset(email)
      if (!mounted.current) return
      setSent(true)
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "resetFailed"))
    } finally {
      if (mounted.current) setPending(false)
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <h2>{t("resetTitle")}</h2>
      <p className="quiet">{t("resetLead")}</p>
      <Banner errors={errors} fields={["form", "email", "origin"]} />
      {sent ? <p role="status">{t("resetSent")}</p> : null}
      <Field
        label={t("email")}
        name="email"
        type="email"
        autoComplete="username"
        value={email}
        error={errors.email}
        onChange={setEmail}
      />
      <button type="submit" disabled={pending || email.trim().length === 0}>
        {pending ? t("resetSending") : t("resetSend")}
      </button>
      <p className="quiet">
        <Link to="/entrar">{t("signIn")}</Link>
      </p>
    </form>
  )
}
