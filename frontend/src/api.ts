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

const OFFLINE: FieldErrors = {
  form: ["No se ha podido contactar con el servidor."],
}

function isErrorBody(value: unknown): value is { errors: FieldErrors } {
  if (!value || typeof value !== "object" || !("errors" in value)) {
    return false
  }
  const errors = value.errors
  if (!errors || typeof errors !== "object") {
    return false
  }
  return Object.values(errors).every(
    (messages) => Array.isArray(messages) && messages.every((item) => typeof item === "string"),
  )
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

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(0, OFFLINE)
  }
  const data = await readJson(response)
  if (!response.ok) {
    const errors = isErrorBody(data)
      ? data.errors
      : { form: ["No se ha podido completar la solicitud."] }
    throw new ApiError(response.status, errors)
  }
  return data as T
}

export function login(email: string, password: string): Promise<Player> {
  return request<Player>("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
}

export function currentPlayer(): Promise<Player | null> {
  return request<Player>("/api/session", { method: "GET" }).catch((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }
    throw error
  })
}

export async function logout(): Promise<void> {
  const token = readCookie("__Host-csrf")
  await request<null>("/api/session/logout", {
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

export function register(payload: Registration): Promise<{ detail: string }> {
  return request("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

function readCookie(name: string): string {
  const prefix = `${name}=`
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length))
    }
  }
  return ""
}
