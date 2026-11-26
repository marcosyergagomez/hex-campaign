import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link, useOutletContext } from "react-router-dom"

import type { AppOutletContext } from "../AppShell"
import { loadProfile, saveProfile, type Sex } from "../api"
import { Banner, Field, SelectField } from "../form"
import { clientNotice } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

const SEXES: readonly Sex[] = ["woman", "man", "other", "undisclosed"]

function isSex(value: string): value is Sex {
  return (SEXES as readonly string[]).includes(value)
}

export function ProfilePage() {
  const { t } = useI18n()
  const { setPlayer } = useOutletContext<AppOutletContext>()
  const alive = useRef(true)
  const [email, setEmail] = useState("")
  const [alias, setAlias] = useState("")
  const [birthDate, setBirthDate] = useState("")
  const [sex, setSex] = useState<Sex | "">("")
  const [currentPassword, setCurrentPassword] = useState("")
  const [password, setPassword] = useState("")
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    alive.current = true
    loadProfile()
      .then((profile) => {
        if (!alive.current) {
          return
        }
        setEmail(profile.email)
        setAlias(profile.alias)
        setBirthDate(profile.birth_date)
        setSex(profile.sex)
        setPlayer({ email: profile.email, alias: profile.alias })
      })
      .catch((error: unknown) => {
        if (alive.current) {
          setErrors(presentError(error, "profileLoadFailed"))
        }
      })
      .finally(() => {
        if (alive.current) {
          setReady(true)
        }
      })
    return () => {
      alive.current = false
    }
  }, [setPlayer])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!isSex(sex)) {
      setErrors({ sex: [clientNotice("chooseOption")] })
      return
    }
    if (password && !currentPassword) {
      setErrors({ current_password: [clientNotice("passwordNeedsCurrent")] })
      return
    }
    setPending(true)
    setErrors({})
    setSaved(false)
    try {
      const profile = await saveProfile({
        alias,
        sex,
        ...(password
          ? { password, current_password: currentPassword }
          : {}),
      })
      if (!alive.current) {
        return
      }
      setAlias(profile.alias)
      setSex(profile.sex)
      setPassword("")
      setCurrentPassword("")
      setPlayer({ email: profile.email, alias: profile.alias })
      setSaved(true)
    } catch (error) {
      if (alive.current) {
        setErrors(presentError(error, "profileSaveFailed"))
      }
    } finally {
      if (alive.current) {
        setPending(false)
      }
    }
  }

  if (!ready) {
    return <p className="quiet">{t("loadingProfile")}</p>
  }

  return (
    <section className="session">
      <div className="page-header">
        <div>
          <h1>{t("profileTitle")}</h1>
          <p className="quiet">{t("profileLead")}</p>
        </div>
        <Link className="text-link" to="/campanas">
          {t("campaignsNav")}
        </Link>
      </div>
      <form onSubmit={onSubmit} noValidate>
        <Banner
          errors={errors}
          fields={["form", "origin", "csrf", "session", "alias", "sex", "password", "current_password"]}
        />
        {saved ? <p className="quiet">{t("profileSaved")}</p> : null}
        <Field
          label={t("email")}
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={() => undefined}
          disabled
        />
        <Field
          label={t("alias")}
          name="alias"
          autoComplete="nickname"
          value={alias}
          hint={t("aliasHint")}
          error={errors.alias}
          onChange={setAlias}
        />
        <Field
          label={t("birthDate")}
          name="birth_date"
          type="date"
          value={birthDate}
          hint={t("birthDateLocked")}
          onChange={() => undefined}
          disabled
        />
        <SelectField
          label={t("sex")}
          name="sex"
          value={sex}
          error={errors.sex}
          options={SEXES.map((value) => ({ value, label: t(value) }))}
          onChange={(next) => setSex(isSex(next) ? next : "")}
        />
        <Field
          label={t("currentPassword")}
          name="current_password"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          hint={t("passwordChangeHint")}
          error={errors.current_password}
          required={false}
          onChange={setCurrentPassword}
        />
        <Field
          label={t("newPassword")}
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          hint={t("passwordHint")}
          error={errors.password}
          required={false}
          onChange={setPassword}
        />
        <button type="submit" disabled={pending}>
          {pending ? t("savingProfile") : t("saveProfile")}
        </button>
      </form>
    </section>
  )
}
