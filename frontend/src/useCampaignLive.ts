import { useEffect, useRef } from "react"

import { getCampaignPulse } from "./api"
import { liveIsOpen, subscribeLive, type LiveSeat } from "./liveEvents"

/**
 * Paints a pushed seat colour at once, then reloads the campaign.
 */
export function useCampaignLive(
  campaignId: string | null | undefined,
  revision: number | null | undefined,
  busy: boolean,
  onStale: () => Promise<void>,
  onSeats?: (revision: number, seats: LiveSeat[]) => void,
) {
  const revisionRef = useRef(revision ?? 0)
  const busyRef = useRef(busy)
  const onStaleRef = useRef(onStale)
  const onSeatsRef = useRef(onSeats)
  const waitingRef = useRef(false)
  revisionRef.current = revision ?? 0
  busyRef.current = busy
  onStaleRef.current = onStale
  onSeatsRef.current = onSeats

  useEffect(() => {
    if (!campaignId) return

    let inFlight = false
    let closed = false

    async function pull() {
      if (closed) return
      if (busyRef.current || inFlight) {
        waitingRef.current = true
        return
      }
      inFlight = true
      waitingRef.current = false
      try {
        await onStaleRef.current()
      } finally {
        inFlight = false
        if (!closed && waitingRef.current && !busyRef.current) {
          waitingRef.current = false
          void pull()
        }
      }
    }

    const stop = subscribeLive((event) => {
      const newer =
        event.type === "campaign" &&
        event.campaign_id === campaignId &&
        event.revision > revisionRef.current
      if (newer) onSeatsRef.current?.(event.revision, event.seats)
      if (event.type !== "reconnect" && !newer) return
      void pull()
    })
    return () => {
      closed = true
      stop()
    }
  }, [campaignId])

  useEffect(() => {
    if (!campaignId || busy || !waitingRef.current) return
    waitingRef.current = false
    void onStaleRef.current()
  }, [busy, campaignId])

  useEffect(() => {
    if (!campaignId) return
    let stopped = false
    const timer = window.setInterval(() => {
      if (stopped || document.hidden || busyRef.current || liveIsOpen()) return
      void getCampaignPulse(campaignId)
        .then((pulse) => {
          if (stopped || pulse.revision <= revisionRef.current) return
          return onStaleRef.current()
        })
        .catch(() => undefined)
    }, 15000)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [campaignId])
}
