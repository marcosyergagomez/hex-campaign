import { ApiError, csrfHeaders, request } from "./http"

export type AppNotification = {
  id: string
  kind: string
  payload: Record<string, unknown>
  created_at: string
  read: boolean
}

export async function listNotifications(): Promise<AppNotification[]> {
  const data = await request("/api/notifications", { method: "GET" })
  if (!Array.isArray(data) || data.length > 60) {
    throw new ApiError(200, {})
  }
  const rows: AppNotification[] = []
  for (const item of data) {
    const row = readNotification(item)
    if (!row) throw new ApiError(200, {})
    rows.push(row)
  }
  return rows
}

export async function markNotificationRead(id: string): Promise<AppNotification> {
  const row = readNotification(
    await request(`/api/notifications/${encodeURIComponent(id)}/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: "{}",
    }),
  )
  if (!row) throw new ApiError(200, {})
  return row
}

function readNotification(value: unknown): AppNotification | null {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  if (
    typeof record.id !== "string" ||
    record.id.length === 0 ||
    record.id.length > 32 ||
    typeof record.kind !== "string" ||
    record.kind.length === 0 ||
    record.kind.length > 32 ||
    typeof record.created_at !== "string" ||
    typeof record.read !== "boolean" ||
    !record.payload ||
    typeof record.payload !== "object"
  ) {
    return null
  }
  return {
    id: record.id,
    kind: record.kind,
    created_at: record.created_at,
    read: record.read,
    payload: record.payload as Record<string, unknown>,
  }
}
