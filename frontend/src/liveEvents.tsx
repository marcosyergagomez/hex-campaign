import { useEffect, useRef, type ReactNode } from "react"

export type LiveSeat = {
  player_id: string
  color: string
  ready: boolean
}

export type LiveEvent =
  | { type: "ready" }
  | { type: "reconnect" }
  | { type: "notification" }
  | { type: "campaigns"; campaign_id?: string; gone?: boolean }
  | {
      type: "campaign"
      campaign_id: string
      revision: number
      phase: string
      seats: LiveSeat[]
    }

type LiveHandler = (event: LiveEvent) => void

type LiveScope = {
  handlers: Set<LiveHandler>
  source: EventSource | null
}

const SCOPE_KEY = "__hexcampaignLive"

function scope(): LiveScope {
  const host = globalThis as typeof globalThis & { [SCOPE_KEY]?: LiveScope }
  if (!host[SCOPE_KEY]) host[SCOPE_KEY] = { handlers: new Set(), source: null }
  return host[SCOPE_KEY]
}

const handlers = scope().handlers

export function subscribeLive(handler: LiveHandler): () => void {
  handlers.add(handler)
  return () => {
    handlers.delete(handler)
  }
}

function emit(event: LiveEvent) {
  for (const handler of handlers) {
    handler(event)
  }
}

function readSeats(value: unknown): LiveSeat[] {
  if (!Array.isArray(value)) return []
  const seats: LiveSeat[] = []
  for (const item of value) {
    if (!item || typeof item !== "object") continue
    const row = item as Record<string, unknown>
    const color = row.color
    if (typeof row.player_id !== "string" || typeof color !== "string" || typeof row.ready !== "boolean") {
      continue
    }
    if (color !== "" && !/^#[0-9a-fA-F]{6}$/.test(color)) continue
    seats.push({ player_id: row.player_id, color, ready: row.ready })
  }
  return seats
}

function readEvent(raw: string): LiveEvent | null {
  try {
    const data = JSON.parse(raw) as Record<string, unknown>
    if (data.type === "ready") return { type: "ready" }
    if (data.type === "notification") return { type: "notification" }
    if (data.type === "campaigns") {
      return {
        type: "campaigns",
        campaign_id: typeof data.campaign_id === "string" ? data.campaign_id : undefined,
        gone: data.gone === true,
      }
    }
    if (data.type === "campaign") {
      if (
        typeof data.campaign_id !== "string" ||
        typeof data.revision !== "number" ||
        !Number.isInteger(data.revision) ||
        data.revision < 1 ||
        typeof data.phase !== "string"
      ) {
        return null
      }
      return {
        type: "campaign",
        campaign_id: data.campaign_id,
        revision: data.revision,
        phase: data.phase,
        seats: readSeats(data.seats),
      }
    }
  } catch {
    return null
  }
  return null
}

/** One EventSource for the signed-in shell. Children subscribe via subscribeLive. */
export function LiveConnection({ active }: { active: boolean }): ReactNode {
  const source = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!active) {
      source.current?.close()
      source.current = null
      return
    }

    let closed = false
    let retryTimer = 0
    let openedOnce = false
    let attempt = 0

    function connect() {
      if (closed) return
      source.current?.close()
      const stream = new EventSource("/api/events")
      source.current = stream
      scope().source = stream

      stream.onmessage = (message) => {
        const event = readEvent(message.data)
        if (event) emit(event)
      }

      stream.onopen = () => {
        attempt = 0
        if (!openedOnce) {
          openedOnce = true
          return
        }
        emit({ type: "reconnect" })
      }

      stream.onerror = () => {
        stream.close()
        if (source.current === stream) source.current = null
        if (scope().source === stream) scope().source = null
        if (closed) return
        window.clearTimeout(retryTimer)
        const delay = Math.min(15000, 1500 * 2 ** Math.min(attempt, 3))
        attempt += 1
        retryTimer = window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      closed = true
      window.clearTimeout(retryTimer)
      if (scope().source === source.current) scope().source = null
      source.current?.close()
      source.current = null
    }
  }, [active])

  return null
}

export function liveIsOpen(): boolean {
  return scope().source?.readyState === EventSource.OPEN
}

const openStream = scope().source
if (openStream) {
  openStream.onmessage = (message) => {
    const event = readEvent(message.data)
    if (event) emit(event)
  }
}
