import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactElement } from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import {
  DEFAULT_CAMPAIGN_RULES,
  getCampaign,
  getCampaignPulse,
  identityOptions,
  placeRoad,
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
    placeRoad: vi.fn(),
  }
})

const YOU = "you"

function preparing(): CampaignDetail {
  const you = {
    player_id: YOU,
    alias: "mesa",
    role: "owner",
    status: "active",
    faction: "bretonnia",
    color: "#c0a062",
    ready: true,
    orders_locked: false,
  }
  return {
    id: "camp-1",
    name: "Camino",
    description: "",
    phase: "preparing",
    revision: 3,
    turn: 0,
    rules: { ...DEFAULT_CAMPAIGN_RULES, visibility: "full" },
    members: [you],
    joined: true,
    you,
    hexes: [
      { q: 0, r: 0, known: true, ground: "llanura", road: false, bridge: false, owner_id: YOU, sight: true },
      { q: 1, r: 0, known: true, ground: "llanura", road: false, bridge: false, owner_id: YOU, sight: true },
    ],
    fortresses: [{ q: 0, r: 0, player_id: YOU }],
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
    prep: "roads",
    roads: { budget: 4, laid: 0, left: 4, ready: false },
  }
}

function page(ui: ReactElement) {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={["/campanas/camp-1"]}>
        <Routes>
          <Route path="/campanas/:id" element={ui} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

beforeEach(() => {
  vi.mocked(getCampaign).mockReset()
  vi.mocked(getCampaignPulse).mockReset()
  vi.mocked(identityOptions).mockReset()
  vi.mocked(placeRoad).mockReset()
  vi.mocked(getCampaignPulse).mockResolvedValue({ revision: 3, phase: "preparing" })
  vi.mocked(identityOptions).mockResolvedValue({
    factions: [{ id: "bretonnia", label: "race_bretonnia", legacy: false }],
    colors: [{ id: "sand", label: "color_sand", value: "#c0a062" }],
  })
})

it("paints a road from the fortress and tells the server", async () => {
  const campaign = preparing()
  vi.mocked(getCampaign).mockResolvedValue(campaign)
  vi.mocked(placeRoad).mockImplementation(async (_id, revision, _q, _r, baseline) => ({
    ...baseline,
    revision: revision + 1,
  }))
  page(<CampaignDetailPage />)
  expect(await screen.findByRole("heading", { name: "Camino" })).toBeInTheDocument()
  expect(screen.getByText("Coloca tus caminos")).toBeInTheDocument()
  expect(screen.getByText("Caminos 0 / 4")).toBeInTheDocument()

  const hex = document.querySelector('[data-hex="1,0"]')
  expect(hex).not.toBeNull()
  await userEvent.click(hex as Element)

  expect(await screen.findByText("Caminos 1 / 4")).toBeInTheDocument()
  expect(placeRoad).toHaveBeenCalledWith(
    "camp-1",
    3,
    1,
    0,
    expect.objectContaining({
      id: "camp-1",
      hexes: expect.arrayContaining([
        expect.objectContaining({ q: 1, r: 0, road: true }),
      ]),
    }),
  )
})
