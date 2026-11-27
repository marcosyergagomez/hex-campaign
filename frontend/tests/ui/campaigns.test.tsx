import { render, screen } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import { LanguageProvider } from "../../src/i18n/language"
import { CampaignDetailPage } from "../../src/pages/CampaignDetailPage"
import { CampaignListPage } from "../../src/pages/CampaignListPage"
import { getCampaign, identityOptions, listCampaigns } from "../../src/api"

vi.mock("../../src/api", async () => {
  const actual = await vi.importActual<typeof import("../../src/api")>("../../src/api")
  return {
    ...actual,
    getCampaign: vi.fn(),
    identityOptions: vi.fn(),
    listCampaigns: vi.fn(),
  }
})

function page(ui: ReactElement, path = "/") {
  return render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/campanas" element={ui} />
          <Route path="/campanas/:id" element={ui} />
          <Route path="/vacia" element={ui} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
}

beforeEach(() => {
  vi.mocked(listCampaigns).mockReset()
  vi.mocked(getCampaign).mockReset()
  vi.mocked(identityOptions).mockReset()
})

it("shows a loading line and then the empty campaign list", async () => {
  let release: (value: []) => void = () => {}
  vi.mocked(listCampaigns).mockReturnValue(new Promise((resolve) => {
    release = resolve
  }))
  page(<CampaignListPage />, "/campanas")
  expect(screen.getByText("Cargando campañas…")).toBeInTheDocument()
  release([])
  expect(await screen.findByText("Todavía no estás en ninguna campaña.")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "Crea tu primera campaña" })).toBeInTheDocument()
})

it("shows an error when the campaign list cannot be loaded", async () => {
  vi.mocked(listCampaigns).mockRejectedValue(new Error("down"))
  page(<CampaignListPage />, "/campanas")
  expect(await screen.findByRole("alert")).toHaveTextContent("No se han podido cargar las campañas.")
})

it("shows a loading line while a campaign is opening", () => {
  vi.mocked(getCampaign).mockReturnValue(new Promise(() => {}))
  vi.mocked(identityOptions).mockReturnValue(new Promise(() => {}))
  page(<CampaignDetailPage />, "/campanas/abc")
  expect(screen.getByText("Cargando la campaña…")).toBeInTheDocument()
})

it("shows an error when the campaign cannot be opened", async () => {
  vi.mocked(getCampaign).mockRejectedValue(new Error("missing"))
  vi.mocked(identityOptions).mockResolvedValue({ factions: [], colors: [] })
  page(<CampaignDetailPage />, "/campanas/abc")
  expect(await screen.findByRole("alert")).toHaveTextContent("No se ha podido cargar la campaña.")
})

it("shows the missing-campaign state when the address has no id", async () => {
  page(<CampaignDetailPage />, "/vacia")
  expect(await screen.findByRole("alert")).toHaveTextContent("No hay ninguna campaña con ese identificador.")
})
