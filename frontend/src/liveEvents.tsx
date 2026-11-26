import { useEffect, useRef, type ReactNode } from "react"

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
    }

type LiveHandler = (event: LiveEvent) => void

const handlers = new Set<LiveHandler>()

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

    function connect() {
      if (closed) return
      source.current?.close()
      const stream = new EventSource("/api/events")
      source.current = stream

      stream.onmessage = (message) => {
        const event = readEvent(message.data)
        if (event) emit(event)
      }

      stream.onopen = () => {
        if (!openedOnce) {
          openedOnce = true
          return
        }
        emit({ type: "reconnect" })
      }

      stream.onerror = () => {
        stream.close()
        if (source.current === stream) source.current = null
        if (closed) return
        window.clearTimeout(retryTimer)
        retryTimer = window.setTimeout(connect, 2500)
      }
    }

    connect()
    return () => {
      closed = true
      window.clearTimeout(retryTimer)
      source.current?.close()
      source.current = null
    }
  }, [active])

  return null
}
