import { render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

import { ErrorBoundary } from "../../src/components/ErrorBoundary"
import { LanguageProvider } from "../../src/i18n/language"

function BrokenScreen() {
  throw new Error("boom")
}

afterEach(() => {
  vi.restoreAllMocks()
})

it("shows a notice when a screen throws while rendering", () => {
  vi.spyOn(console, "error").mockImplementation(() => {})
  render(
    <LanguageProvider>
      <ErrorBoundary>
        <BrokenScreen />
      </ErrorBoundary>
    </LanguageProvider>,
  )
  const notice = screen.getByRole("alert")
  expect(notice).toHaveTextContent("Esta pantalla no se ha podido mostrar.")
  expect(notice).toHaveTextContent("Ha fallado al dibujarse. Puedes volver a intentarlo.")
  expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument()
})
