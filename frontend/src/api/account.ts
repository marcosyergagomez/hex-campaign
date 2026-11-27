import { readCookie } from "../cookies"
import { ApiError, ALIAS, CONTROL, readDetail, request } from "./http"

export type Sex = "woman" | "man" | "other" | "undisclosed"

export type Player = {
  email: string
  alias: string
}

export type Profile = Player & {
  sex: Sex
  birth_date: string
}

export type ProfileUpdate = {
  alias: string
  sex: Sex
  password?: string
  current_password?: string
}

const SEXES: readonly Sex[] = ["woman", "man", "other", "undisclosed"]

function isSex(value: unknown): value is Sex {
  return typeof value === "string" && (SEXES as readonly string[]).includes(value)
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

function readProfile(value: unknown): Profile | null {
  const player = readPlayer(value)
  if (!player || !value || typeof value !== "object") {
    return null
  }
  const record = value as Record<string, unknown>
  const { sex, birth_date: birthDate } = record
  if (!isSex(sex)) {
    return null
  }
  if (typeof birthDate !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) {
    return null
  }
  return { ...player, sex, birth_date: birthDate }
}

export async function requestPasswordReset(email: string): Promise<void> {
  await request("/api/password-reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  })
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

export async function loadProfile(): Promise<Profile> {
  const profile = readProfile(await request("/api/profile", { method: "GET" }))
  if (!profile) {
    throw new ApiError(200, {})
  }
  return profile
}

export async function saveProfile(payload: ProfileUpdate): Promise<Profile> {
  const token = readCookie("__Host-csrf")
  const body: Record<string, string> = {
    alias: payload.alias,
    sex: payload.sex,
  }
  if (payload.password) {
    body.password = payload.password
    body.current_password = payload.current_password ?? ""
  }
  const profile = readProfile(
    await request("/api/profile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-CSRF-Token": token } : {}),
      },
      body: JSON.stringify(body),
    }),
  )
  if (!profile) {
    throw new ApiError(200, {})
  }
  return profile
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
