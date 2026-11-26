import { useEffect, useRef } from "react"

import { subscribeLive } from "./liveEvents"

/**
 * Reloads a campaign when the server pushes a newer revision for it.
 */
export function useCampaignLive(
  campaignId: string | null | undefined,
  revision: number | null | undefined,
  busy: boolean,
  onStale: () => Promise<void>,
) {
  const revisionRef = useRef(revision ?? 0)
  const busyRef = useRef(busy)
  const onStaleRef = useRef(onStale)
  revisionRef.current = revision ?? 0
  busyRef.current = busy
  onStaleRef.current = onStale

  useEffect(() => {
    if (!campaignId) return

    let inFlight = false

    async function pull() {
      if (inFlight || busyRef.current) return
      inFlight = true
      try {
        await onStaleRef.current()
      } finally {
        inFlight = false
      }
    }

    return subscribeLive((event) => {
      if (busyRef.current) return
      if (event.type === "reconnect") {
        void pull()
        return
      }
      if (
        event.type === "campaign" &&
        event.campaign_id === campaignId &&
        event.revision > revisionRef.current
      ) {
        void pull()
      }
    })
  }, [campaignId])
}
