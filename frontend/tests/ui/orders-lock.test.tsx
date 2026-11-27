import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactElement } from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import {
  ApiError,
  DEFAULT_CAMPAIGN_RULES,
  getCampaign,
  getCampaignPulse,
  identityOptions,
  lockCampaignOrders,
  type CampaignDetail,
} from "../../src/api"
import { LanguageProvider } from "../../src/i18n/language"
import { CampaignDetailPage } from "../../src/pages/CampaignDetailPage"

vi.mock("../../src/api", async () => {
  const actual = await vi.importActual<typeof import("../../src/api")>("../../src/api")
  return {
    ...actual,
    getCampaign: vi.fn(),
    getCampaignPulse: vi.fn(),
    identityOptions: vi.fn(),
    lockCampaignOrders: vi.fn(),
  }
})

function campaign(revision: number, ordersLocked = false): CampaignDetail {
  const you = {
    player_id: "p1",
    alias: "Ada",
    role: "owner",
    status: "active",
    faction: "",
    color: "#7a1f2b",
    ready: true,
    orders_locked: ordersLocked,
  }
  const hexes: CampaignDetail["hexes"] = Array.from({ length: 9 }, (_, index) => ({
    q: index - 4,
    r: 0,
    ground: "llanura",
    road: false,
    bridge: false,
    known: true,
    owner_id: null,
    sight: true,
  }))
  return {
    id: "abc",
    name: "La mesa",
    description: "",
    phase: "orders",
    revision,
    turn: 1,
    rules: { ...DEFAULT_CAMPAIGN_RULES, map_size: 19 },
    members: [{ ...you }],
    joined: true,
    you,
    hexes,
    fortresses: [],
    armies: [],
    battles: [],
    orders: {},
    playback: { turn: 0, moves: [] },
    chronicle: [],
    road_ready: [],
    lobby_ready: [],
    naming: false,
    fort_open: false,
    prep_done: [],
    prep: null,
    roads: null,
  }
}

function page(ui: ReactElement) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={["/campanas/abc"]}>
        <Routes>
          <Route path="/campanas/:id" element={ui} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

let reads = 0

beforeEach(() => {
  reads = 0
  vi.mocked(getCampaign).mockReset()
  vi.mocked(getCampaignPulse).mockReset()
  vi.mocked(identityOptions).mockReset()
  vi.mocked(lockCampaignOrders).mockReset()
  vi.mocked(identityOptions).mockResolvedValue({ factions: [], colors: [] })
  vi.mocked(getCampaignPulse).mockResolvedValue({ revision: 1, phase: "orders" })
  vi.mocked(getCampaign).mockImplementation(async () => {
    reads += 1
    return reads === 1 ? campaign(3) : campaign(4)
  })
})

it("reloads the campaign after a 409 and locks the turn once more", async () => {
  const user = userEvent.setup()
  vi.mocked(lockCampaignOrders)
    .mockRejectedValueOnce(new ApiError(409, {}))
    .mockResolvedValueOnce(campaign(5, true))
  page(<CampaignDetailPage />)
  await user.click(await screen.findByRole("button", { name: "Fijar turno" }))
  await waitFor(() => expect(lockCampaignOrders).toHaveBeenCalledTimes(2))
  expect(lockCampaignOrders).toHaveBeenNthCalledWith(1, "abc", 3, {})
  expect(lockCampaignOrders).toHaveBeenNthCalledWith(2, "abc", 4, {})
  expect(getCampaign).toHaveBeenCalledTimes(2)
  expect(screen.queryByRole("button", { name: "Fijar turno" })).not.toBeInTheDocument()
})

it("stops after the second 409 and shows the lock error", async () => {
  const user = userEvent.setup()
  vi.mocked(lockCampaignOrders).mockRejectedValue(new ApiError(409, {}))
  page(<CampaignDetailPage />)
  await user.click(await screen.findByRole("button", { name: "Fijar turno" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("No se ha podido fijar el turno.")
  expect(lockCampaignOrders).toHaveBeenCalledTimes(2)
  expect(getCampaign).toHaveBeenCalledTimes(2)
  expect(screen.getByRole("button", { name: "Fijar turno" })).toBeEnabled()
})
