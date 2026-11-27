import { ALIAS, ApiError, csrfHeaders, request } from "./http"
import type { CampaignDetail } from "./campaignTypes"
import { readDetailCampaign } from "./readCampaign"

export type PlayerSuggestion = { alias: string }

export async function searchPlayers(query: string): Promise<PlayerSuggestion[]> {
  const data = await request(`/api/players?q=${encodeURIComponent(query)}`, { method: "GET" })
  if (!Array.isArray(data) || data.length > 20) {
    throw new ApiError(200, {})
  }
  const rows: PlayerSuggestion[] = []
  for (const item of data) {
    if (!item || typeof item !== "object" || !("alias" in item) || typeof item.alias !== "string") {
      throw new ApiError(200, {})
    }
    if (!ALIAS.test(item.alias)) {
      throw new ApiError(200, {})
    }
    rows.push({ alias: item.alias })
  }
  return rows
}

export async function inviteCampaignPlayer(
  id: string,
  revision: number,
  alias: string,
): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/invitations`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision, alias }),
    }),
  )
  if (!campaign) throw new ApiError(200, {})
  return campaign
}

export type InvitationStatus = "pending" | "accepted" | "declined" | "revoked"

export type CampaignInvitation = {
  id: string
  alias: string
  status: InvitationStatus
}

export async function listCampaignInvitations(id: string): Promise<CampaignInvitation[]> {
  const data = await request(`/api/campaigns/${encodeURIComponent(id)}/invitations`, { method: "GET" })
  if (!Array.isArray(data)) return []
  const rows: CampaignInvitation[] = []
  for (const item of data) {
    if (!item || typeof item !== "object") continue
    const row = item as Record<string, unknown>
    const status = row.status
    if (
      typeof row.id !== "string" ||
      typeof row.alias !== "string" ||
      (status !== "pending" && status !== "accepted" && status !== "declined" && status !== "revoked")
    ) {
      continue
    }
    rows.push({ id: row.id, alias: row.alias, status })
  }
  return rows
}

export async function revokeCampaignInvitation(id: string, invitationId: string): Promise<void> {
  await request(
    `/api/campaigns/${encodeURIComponent(id)}/invitations/${encodeURIComponent(invitationId)}/revoke`,
    { method: "POST", headers: csrfHeaders() },
  )
}

export async function resendCampaignInvitation(id: string, invitationId: string): Promise<void> {
  await request(
    `/api/campaigns/${encodeURIComponent(id)}/invitations/${encodeURIComponent(invitationId)}/resend`,
    { method: "POST", headers: csrfHeaders() },
  )
}

export async function declineCampaignInvitation(id: string): Promise<void> {
  await request(`/api/campaigns/${encodeURIComponent(id)}/invitations/decline`, {
    method: "POST",
    headers: csrfHeaders(),
  })
}

export async function joinCampaign(id: string, revision: number): Promise<CampaignDetail> {
  const campaign = readDetailCampaign(
    await request(`/api/campaigns/${encodeURIComponent(id)}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ revision }),
    }),
  )
  if (!campaign) throw new ApiError(200, {})
  return campaign
}
