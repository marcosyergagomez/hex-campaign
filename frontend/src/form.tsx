import type { FieldErrors } from "./api"

export function Banner({ errors, fields }: { errors: FieldErrors; fields?: string[] }) {
  const names = fields ?? Object.keys(errors)
  const messages = names.flatMap((name) => errors[name] ?? [])
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
  const errorId = error?.length ? `${name}-error` : undefined
  return (
    <label>
      <span className="label-text">{label}</span>
      <input
        name={name}
        type={type}
        autoComplete={autoComplete}
        value={value}
        required
        aria-invalid={Boolean(error?.length)}
        aria-describedby={errorId}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? <p className="hint">{hint}</p> : null}
      {error?.length ? (
        <p id={errorId} className="field-error">
          {error.join(" ")}
        </p>
      ) : null}
    </label>
  )
}
