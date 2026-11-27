import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import { LanguageProvider } from "../../src/i18n/language"
import { LoginPage } from "../../src/pages/LoginPage"
import { RegisterPage } from "../../src/pages/RegisterPage"
import { currentPlayer, login, register } from "../../src/api"

vi.mock("../../src/api", async () => {
  const actual = await vi.importActual<typeof import("../../src/api")>("../../src/api")
  return {
    ...actual,
    currentPlayer: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
  }
})

function page(ui: ReactElement) {
  return render(
    <LanguageProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </LanguageProvider>,
  )
}

beforeEach(() => {
  vi.mocked(currentPlayer).mockReset()
  vi.mocked(login).mockReset()
  vi.mocked(register).mockReset()
})

it("shows the session check, then an empty sign-in form", async () => {
  let release: (value: null) => void = () => {}
  vi.mocked(currentPlayer).mockReturnValue(new Promise((resolve) => {
    release = resolve
  }))
  page(<LoginPage />)
  expect(screen.getByText("Comprobando la sesión…")).toBeInTheDocument()
  release(null)
  expect(await screen.findByLabelText("Correo")).toHaveValue("")
  expect(screen.getByLabelText("Contraseña")).toHaveValue("")
  expect(screen.getByRole("button", { name: "Entrar" })).toBeEnabled()
})

it("shows an error when the session check fails", async () => {
  vi.mocked(currentPlayer).mockRejectedValue(new Error("down"))
  page(<LoginPage />)
  expect(await screen.findByRole("alert")).toHaveTextContent("No se ha podido comprobar la sesión.")
})

it("shows an error when sign-in is rejected and keeps the form", async () => {
  vi.mocked(currentPlayer).mockResolvedValue(null)
  vi.mocked(login).mockRejectedValue(new Error("no"))
  page(<LoginPage />)
  expect(await screen.findByLabelText("Correo")).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Correo"), "ada@example.com")
  await userEvent.type(screen.getByLabelText("Contraseña"), "una-clave-larga")
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("No se ha podido entrar.")
  expect(screen.getByLabelText("Correo")).toHaveValue("ada@example.com")
})

it("shows the empty registration form and asks for a sex", async () => {
  page(<RegisterPage />)
  expect(screen.getByLabelText("Correo")).toHaveValue("")
  expect(screen.getByLabelText("Alias")).toHaveValue("")
  expect(screen.getByLabelText("Sexo")).toHaveValue("")
  await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Elige una opción.")
  expect(register).not.toHaveBeenCalled()
})

it("shows the confirmation when the account is accepted", async () => {
  vi.mocked(register).mockResolvedValue({ detail: "Mira el correo." })
  page(<RegisterPage />)
  await userEvent.type(screen.getByLabelText("Correo"), "ada@example.com")
  await userEvent.type(screen.getByLabelText("Contraseña"), "una-clave-larga")
  await userEvent.type(screen.getByLabelText("Alias"), "ada_l")
  await userEvent.type(screen.getByLabelText("Fecha de nacimiento"), "1990-01-02")
  await userEvent.selectOptions(screen.getByLabelText("Sexo"), "woman")
  await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }))
  expect(await screen.findByRole("heading", { name: "Revisa el correo" })).toBeInTheDocument()
  expect(screen.getByText("Mira el correo.")).toBeInTheDocument()
})
