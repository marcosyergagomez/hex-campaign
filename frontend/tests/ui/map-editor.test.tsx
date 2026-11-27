import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import { getMap, listMapScales, saveDrawnMap, type MapScale } from "../../src/api"
import { LanguageProvider } from "../../src/i18n/language"
import { MapEditorPage } from "../../src/pages/MapEditorPage"

vi.mock("../../src/api", async () => {
  const actual = await vi.importActual<typeof import("../../src/api")>("../../src/api")
  return {
    ...actual,
    getMap: vi.fn(),
    listMapScales: vi.fn(),
    saveDrawnMap: vi.fn(),
  }
})

const scales: MapScale[] = [
  { key: "small", size: 19, seats: [2], recommend: 2, home_size: 7 },
  { key: "medium", size: 37, seats: [2, 3], recommend: 3, home_size: 7 },
  { key: "large", size: 61, seats: [2, 3, 4], recommend: 4, home_size: 7 },
]

beforeEach(() => {
  vi.mocked(listMapScales).mockReset()
  vi.mocked(saveDrawnMap).mockReset()
  vi.mocked(getMap).mockReset()
  vi.mocked(listMapScales).mockResolvedValue(scales)
  vi.mocked(saveDrawnMap).mockResolvedValue({
    id: "map-1",
    name: "Valle",
    size: 19,
    seats: null,
    generated: false,
  })
  vi.mocked(getMap).mockResolvedValue({
    id: "map-1",
    name: "Valle",
    size: 19,
    seats: null,
    generated: false,
    cells: [{ q: 0, r: 0, ground: "llanura", road: false, bridge: false }],
    anchors: [],
  })
})

it("saves a drawn map from the editor", async () => {
  const user = userEvent.setup()
  render(
    <LanguageProvider>
      <MemoryRouter initialEntries={["/mapas/editor"]}>
        <Routes>
          <Route path="/mapas/editor" element={<MapEditorPage />} />
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar mapa" })).toBeEnabled())
  await user.type(screen.getByLabelText("Nombre del mapa"), "Valle")
  await user.click(screen.getByRole("button", { name: "Guardar mapa" }))
  expect(await screen.findByRole("status")).toHaveTextContent("Mapa guardado.")
  expect(saveDrawnMap).toHaveBeenCalledTimes(1)
  const [name, size, cells, anchors] = vi.mocked(saveDrawnMap).mock.calls[0]
  expect(name).toBe("Valle")
  expect(size).toBe(19)
  expect(cells).toHaveLength(19)
  expect(anchors).toEqual([])
})
