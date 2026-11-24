import { useState, type FormEvent } from "react"

import { ApiError, register, type Sex } from "../api"
import { Banner, Field } from "../form"

const SEXES: { value: Sex; label: string }[] = [
  { value: "woman", label: "Mujer" },
  { value: "man", label: "Hombre" },
  { value: "other", label: "Otro" },
  { value: "undisclosed", label: "Prefiero no decirlo" },
]

export function RegisterPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [alias, setAlias] = useState("")
  const [birthDate, setBirthDate] = useState("")
  const [sex, setSex] = useState<Sex | "">("")
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [detail, setDetail] = useState("")

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!sex) {
      setErrors({ sex: ["Elige una opción."] })
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
      setDetail(accepted.detail)
    } catch (error) {
      setErrors(
        error instanceof ApiError ? error.errors : { form: ["No se ha podido crear la cuenta."] },
      )
    } finally {
      setPending(false)
    }
  }

  if (detail) {
    return (
      <div className="session">
        <h2>Revisa el correo</h2>
        <p>{detail}</p>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <Banner errors={errors} fields={["form"]} />
      <Field
        label="Correo"
        name="email"
        type="email"
        autoComplete="email"
        value={email}
        error={errors.email}
        onChange={setEmail}
      />
      <Field
        label="Contraseña"
        name="password"
        type="password"
        autoComplete="new-password"
        value={password}
        hint="De 12 a 128 caracteres. Los espacios cuentan."
        error={errors.password}
        onChange={setPassword}
      />
      <Field
        label="Alias"
        name="alias"
        autoComplete="nickname"
        value={alias}
        hint="De 3 a 24 letras, números o guion bajo."
        error={errors.alias}
        onChange={setAlias}
      />
      <Field
        label="Fecha de nacimiento"
        name="birth_date"
        type="date"
        autoComplete="bday"
        value={birthDate}
        hint="Hay que tener al menos 16 años."
        error={errors.birth_date}
        onChange={setBirthDate}
      />
      <label>
        <span className="label-text">Sexo</span>
        <select
          name="sex"
          value={sex}
          required
          onChange={(event) => {
            setSex(event.target.value as Sex | "")
            setErrors((current) => {
              if (!current.sex) {
                return current
              }
              const next = { ...current }
              delete next.sex
              return next
            })
          }}
        >
          <option value="">Elige una opción</option>
          {SEXES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {errors.sex ? <p className="field-error">{errors.sex.join(" ")}</p> : null}
      </label>
      <button type="submit" disabled={pending}>
        {pending ? "Creando…" : "Crear cuenta"}
      </button>
    </form>
  )
}
