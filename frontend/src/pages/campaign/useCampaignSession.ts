import { useCallback, useEffect, useRef, useState } from "react"

import { ApiError, getCampaign, identityOptions, type CampaignDetail, type IdentityOptions } from "../../api"
import { clientNotice } from "../../i18n/catalog"
import { presentError } from "../../presentError"
import { useCampaignLive } from "../../useCampaignLive"
import { paintSeats } from "./phase"

export type LocalJob = "fort" | "road" | "stand"

export function useCampaignSession(id: string) {
  const mounted = useRef(true)
  const routeId = useRef(id)
  routeId.current = id
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null)
  const [options, setOptions] = useState<IdentityOptions | null>(null)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [busy, setBusy] = useState(false)
  const campaignRef = useRef(campaign)
  campaignRef.current = campaign
  const jobs = useRef({ fort: false, road: false, stand: false })
  const localPlay = useRef(false)
  const pullAfter = useRef(false)

  useEffect(() => {
    mounted.current = true
    let current = true
    if (!id) {
      setErrors({ campaign: [clientNotice("campaignNotFound")] })
      return
    }
    Promise.all([getCampaign(id), identityOptions()])
      .then(([found, choices]) => {
        if (current) {
          setCampaign(found)
          setOptions(choices)
        }
      })
      .catch((error: unknown) => {
        if (current) setErrors(presentError(error, "campaignLoadFailed"))
      })
    return () => {
      current = false
      mounted.current = false
    }
  }, [id])

  const accept = useCallback((updated: CampaignDetail, force = false) => {
    if (!mounted.current || routeId.current !== updated.id) return
    setCampaign((current) => {
      // Equal revisions stay. A late reload must not pull a fortress back after the click.
      if (!force && current && current.id === updated.id && updated.revision <= current.revision) {
        return current
      }
      return updated
    })
  }, [])

  const refresh = useCallback(async (campaignId: string) => {
    accept(await getCampaign(campaignId))
  }, [accept])

  const pullLive = useCallback(async () => {
    if (!id || busy) return
    if (localPlay.current) {
      pullAfter.current = true
      return
    }
    try {
      accept(await getCampaign(id))
    } catch {
      /* keep the last good view; next pulse retries */
    }
  }, [accept, busy, id])

  const setJob = useCallback((kind: LocalJob, running: boolean) => {
    jobs.current[kind] = running
    localPlay.current = jobs.current.fort || jobs.current.road || jobs.current.stand
    if (!localPlay.current && pullAfter.current) {
      pullAfter.current = false
      void pullLive()
    }
  }, [pullLive])

  async function mutateCampaign(action: () => Promise<CampaignDetail>) {
    if (!campaign) throw new Error("Campaign not loaded")
    const snapshot = campaign
    try {
      accept(await action())
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 409) {
        try {
          await refresh(snapshot.id)
        } catch {
          /* keep the mutation error below */
        }
      }
      throw error
    }
  }

  async function applyCampaign(action: () => Promise<CampaignDetail>) {
    if (!campaign || busy) return
    setBusy(true)
    try {
      await mutateCampaign(action)
      if (mounted.current) setErrors({})
    } catch (error: unknown) {
      if (mounted.current) setErrors(presentError(error, "campaignLoadFailed"))
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  useCampaignLive(
    campaign?.id ?? null,
    campaign?.revision ?? null,
    busy,
    pullLive,
    (revision, seats) => {
      setCampaign((current) => paintSeats(current, revision, seats))
    },
  )

  return {
    id,
    campaign,
    setCampaign,
    options,
    errors,
    setErrors,
    busy,
    setBusy,
    accept,
    refresh,
    mutateCampaign,
    applyCampaign,
    pullLive,
    mounted,
    campaignRef,
    setJob,
  }
}

export type CampaignSession = ReturnType<typeof useCampaignSession>
