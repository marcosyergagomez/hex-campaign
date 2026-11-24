import { useEffect, useRef, useState, type FormEvent } from "react"

import { register, type Sex } from "../api"
import { Banner, Field } from "../form"
import { clientNotice } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"

const SEXES: readonly Sex[] = ["woman", "man", "other", "undisclosed"]

function isSex(value: string): value is Sex {
  return (SEXES as readonly string[]).includes(value)
}

export function RegisterPage() {
  const { t, text } = useI18n()
  const alive = useRef(true)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [alias, setAlias] = useState("")
  const [birthDate, setBirthDate] = useState("")
  const [sex, setSex] = useState<Sex | "">("")
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [detail, setDetail] = useState("")

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!isSex(sex)) {
      setErrors({ sex: [clientNotice("chooseOption")] })
      return
    }
    setPending(true)
    setErrors({})
    setDetail("")
    try {
      const accepted = await register({
        email,
        password,
        alias,
        birth_date: birthDate,
        sex,
      })
      if (!alive.current) {
        return
      }
      setPassword("")
      setDetail(accepted.detail)
    } catch (error) {
      if (alive.current) {
        setErrors(presentError(error, "registerFailed"))
      }
    } finally {
      if (alive.current) {
        setPending(false)
      }
    }
  }

  if (detail) {
    return (
      <div className="session">
        <h2>{t("checkEmail")}</h2>
        <p>{text(detail)}</p>
      </div>
    )
  }

  const sexErrorId = errors.sex?.length ? "sex-error" : undefined
  return (
    <form onSubmit={onSubmit} noValidate>
      <Banner errors={errors} fields={["form"]} />
      <Field
        label={t("email")}
        name="email"
        type="email"
        autoComplete="email"
        value={email}
        error={errors.email}
        onChange={setEmail}
      />
      <Field
        label={t("password")}
        name="password"
        type="password"
        autoComplete="new-password"
        value={password}
        hint={t("passwordHint")}
        error={errors.password}
        onChange={setPassword}
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
        autoComplete="bday"
        value={birthDate}
        hint={t("ageHint")}
        error={errors.birth_date}
        onChange={setBirthDate}
      />
      <div className="field">
        <label className="label-text" htmlFor="sex">
          {t("sex")}
        </label>
        <select
          id="sex"
          name="sex"
          value={sex}
          required
          aria-invalid={Boolean(sexErrorId)}
          aria-describedby={sexErrorId}
          onChange={(event) => {
            const next = event.target.value
            setSex(isSex(next) ? next : "")
            setErrors((current) => {
              if (!current.sex) {
                return current
              }
              const rest = { ...current }
              delete rest.sex
              return rest
            })
          }}
        >
          <option value="">{t("choose")}</option>
          {SEXES.map((option) => (
            <option key={option} value={option}>
              {t(option)}
            </option>
          ))}
        </select>
        {sexErrorId ? (
          <p id={sexErrorId} className="field-error">
            {errors.sex?.map(text).join(" ")}
          </p>
        ) : null}
      </div>
      <button type="submit" disabled={pending}>
        {pending ? t("creating") : t("createAccount")}
      </button>
    </form>
  )
}
