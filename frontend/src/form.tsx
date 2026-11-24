import type { FieldErrors } from "./api"
import { useI18n } from "./i18n/language"

export function Banner({ errors, fields }: { errors: FieldErrors; fields?: string[] }) {
  const { text } = useI18n()
  const names = fields ?? Object.keys(errors)
  const messages = names.flatMap((name) => errors[name] ?? []).map(text)
  if (messages.length === 0) {
    return null
  }
  return (
    <p className="banner" role="alert">
      {messages.join(" ")}
    </p>
  )
}

export function Field({
  label,
  name,
  type = "text",
  autoComplete,
  value,
  hint,
  error,
  onChange,
}: {
  label: string
  name: string
  type?: string
  autoComplete?: string
  value: string
  hint?: string
  error?: string[]
  onChange: (value: string) => void
}) {
  const { text } = useI18n()
  const hintId = hint ? `${name}-hint` : undefined
  const errorId = error?.length ? `${name}-error` : undefined
  const describedBy = [hintId, errorId].filter((id) => id).join(" ")
  const shown = error?.map(text)
  const suppressAssist = type === "email" || type === "password"
  return (
    <div className="field">
      <label className="label-text" htmlFor={name}>
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        autoComplete={autoComplete}
        autoCapitalize={suppressAssist ? "none" : undefined}
        autoCorrect={suppressAssist ? "off" : undefined}
        spellCheck={suppressAssist ? false : undefined}
        value={value}
        required
        aria-invalid={Boolean(shown?.length)}
        aria-describedby={describedBy || undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? (
        <p id={hintId} className="hint">
          {hint}
        </p>
      ) : null}
      {shown?.length ? (
        <p id={errorId} className="field-error">
          {shown.join(" ")}
        </p>
      ) : null}
    </div>
  )
}

export function SelectField({
  label,
  name,
  value,
  hint,
  error,
  options,
  onChange,
}: {
  label: string
  name: string
  value: string
  hint?: string
  error?: string[]
  options: readonly { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  const { text } = useI18n()
  const hintId = hint ? `${name}-hint` : undefined
  const errorId = error?.length ? `${name}-error` : undefined
  const describedBy = [hintId, errorId].filter((id) => id).join(" ")
  const shown = error?.map(text)
  return (
    <div className="field">
      <label className="label-text" htmlFor={name}>
        {label}
      </label>
      <select
        id={name}
        name={name}
        value={value}
        required
        aria-invalid={Boolean(shown?.length)}
        aria-describedby={describedBy || undefined}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? (
        <p id={hintId} className="hint">
          {hint}
        </p>
      ) : null}
      {shown?.length ? (
        <p id={errorId} className="field-error">
          {shown.join(" ")}
        </p>
      ) : null}
    </div>
  )
}
