import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"

import { HexBoard } from "../../src/game/hex/HexBoard"
import { LanguageProvider } from "../../src/i18n/language"

it("names the map and its zoom controls", () => {
  const cells = Array.from({ length: 9 }, (_, index) => ({
    q: index - 4,
    r: 0,
    ground: "llanura",
    road: false,
    bridge: false,
  }))
  render(
    <LanguageProvider>
      <HexBoard cells={cells} anchors={[]} />
    </LanguageProvider>,
  )
  expect(screen.getByRole("img", { name: "Mapas" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Alejar el mapa" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Ajustar el mapa" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Acercar el mapa" })).toBeInTheDocument()
})
