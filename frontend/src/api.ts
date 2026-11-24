import { readCookie } from "./cookies"

export type FieldErrors = Record<string, string[]>

export type Sex = "woman" | "man" | "other" | "undisclosed"

export type Player = {
  email: string
  alias: string
}

export class ApiError extends Error {
  readonly status: number
  readonly errors: FieldErrors

  constructor(status: number, errors: FieldErrors) {
    super("api")
    this.status = status
    this.errors = errors
  }
}

const ALIAS = /^[A-Za-z0-9_]{3,24}$/
const CONTROL = /[\u0000-\u001F\u007F]/

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

function readPlayer(value: unknown): Player | null {
  if (!value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const { email, alias } = record
  if (typeof email !== "string" || typeof alias !== "string") {
    return null
  }
  if (email.length === 0 || email.length > 254 || CONTROL.test(email)) {
    return null
  }
  if (!ALIAS.test(alias)) {
    return null
  }
  return { email, alias }
}

function readDetail(value: unknown): string | null {
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

async function request(path: string, init: RequestInit): Promise<unknown> {
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

export async function login(email: string, password: string): Promise<Player> {
  const player = readPlayer(
    await request("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  )
  if (!player) {
    throw new ApiError(200, {})
  }
  return player
}

export async function currentPlayer(): Promise<Player | null> {
  try {
    const player = readPlayer(await request("/api/session", { method: "GET" }))
    if (!player) {
      throw new ApiError(200, {})
    }
    return player
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }
    throw error
  }
}

export async function logout(): Promise<void> {
  const token = readCookie("__Host-csrf")
  await request("/api/session/logout", {
    method: "POST",
    headers: token ? { "X-CSRF-Token": token } : {},
  })
}

export type Registration = {
  email: string
  password: string
  alias: string
  birth_date: string
  sex: Sex
}

export async function register(payload: Registration): Promise<{ detail: string }> {
  const detail = readDetail(
    await request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  )
  if (!detail) {
    throw new ApiError(202, {})
  }
  return { detail }
}
