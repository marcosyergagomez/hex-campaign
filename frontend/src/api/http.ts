import { readCookie } from "../cookies"

export type FieldErrors = Record<string, string[]>

export class ApiError extends Error {
  readonly status: number
  readonly errors: FieldErrors

  constructor(status: number, errors: FieldErrors) {
    super("api")
    this.status = status
    this.errors = errors
  }
}

export const ALIAS = /^[A-Za-z0-9_]{3,24}$/
// The class is the check: a payload must not carry control characters.
export const CONTROL = /[\u0000-\u001F\u007F]/ // eslint-disable-line no-control-regex

function isErrorBody(value: unknown): value is { errors: FieldErrors } {
  if (!value || typeof value !== "object" || !("errors" in value)) {
    return false
  }
  const errors = value.errors
  if (!errors || typeof errors !== "object" || Array.isArray(errors)) {
    return false
  }
  const entries = Object.entries(errors)
  if (entries.length === 0 || entries.length > 12) {
    return false
  }
  return entries.every(([, messages]) => {
    return (
      Array.isArray(messages) &&
      messages.length > 0 &&
      messages.length <= 8 &&
      messages.every((item) => typeof item === "string" && item.length > 0 && item.length <= 300)
    )
  })
}

export function readInt(value: unknown, min: number, max: number): number | null {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min || value > max) {
    return null
  }
  return value
}

export function readDetail(value: unknown): string | null {
  if (!value || typeof value !== "object" || !("detail" in value)) {
    return null
  }
  const detail = (value as { detail: unknown }).detail
  if (typeof detail !== "string" || detail.length === 0 || detail.length > 500 || CONTROL.test(detail)) {
    return null
  }
  return detail
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

export async function request(path: string, init: RequestInit): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(0, {})
  }
  const data = await readJson(response)
  if (!response.ok) {
    throw new ApiError(response.status, isErrorBody(data) ? data.errors : {})
  }
  return data
}

export function csrfHeaders(): HeadersInit {
  const token = readCookie("__Host-csrf")
  return token ? { "X-CSRF-Token": token } : {}
}
