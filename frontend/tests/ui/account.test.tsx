import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import { loadProfile, register, saveProfile, type Player } from "../../src/api"
import { LanguageProvider } from "../../src/i18n/language"
import { ProfilePage } from "../../src/pages/ProfilePage"
import { RegisterPage } from "../../src/pages/RegisterPage"

vi.mock("../../src/api", async () => {
  const actual = await vi.importActual<typeof import("../../src/api")>("../../src/api")
  return {
    ...actual,
    loadProfile: vi.fn(),
    register: vi.fn(),
    saveProfile: vi.fn(),
  }
})

beforeEach(() => {
  vi.mocked(register).mockReset()
  vi.mocked(loadProfile).mockReset()
  vi.mocked(saveProfile).mockReset()
})

it("registers an account and asks the player to check their email", async () => {
  const user = userEvent.setup()
  vi.mocked(register).mockResolvedValue({ detail: "Cuenta creada." })
  render(
    <LanguageProvider>
      <RegisterPage />
    </LanguageProvider>,
  )
  await user.type(screen.getByLabelText("Correo"), "ada@example.com")
  await user.type(screen.getByLabelText("Contraseña"), "clave-segura")
  await user.type(screen.getByLabelText("Alias"), "Ada")
  await user.type(screen.getByLabelText("Fecha de nacimiento"), "1990-04-02")
  await user.selectOptions(screen.getByLabelText("Sexo"), "woman")
  await user.click(screen.getByRole("button", { name: "Crear cuenta" }))
  expect(register).toHaveBeenCalledWith({
    email: "ada@example.com",
    password: "clave-segura",
    alias: "Ada",
    birth_date: "1990-04-02",
    sex: "woman",
  })
  expect(await screen.findByRole("heading", { name: "Revisa el correo" })).toBeInTheDocument()
  expect(screen.getByText("Cuenta creada.")).toBeInTheDocument()
})

function ProfileHost() {
  const [player, setPlayer] = useState<Player>({ email: "ada@example.com", alias: "Ada" })
  return <Outlet context={{ player, setPlayer }} />
}

it("loads the profile, saves a new alias and confirms it", async () => {
  const user = userEvent.setup()
  vi.mocked(loadProfile).mockResolvedValue({
    email: "ada@example.com",
    alias: "Ada",
    sex: "woman",
    birth_date: "1990-04-02",
  })
  vi.mocked(saveProfile).mockImplementation(async (payload) => ({
    email: "ada@example.com",
    alias: payload.alias,
    sex: payload.sex,
    birth_date: "1990-04-02",
  }))
  render(
    <LanguageProvider>
      <MemoryRouter initialEntries={["/perfil"]}>
        <Routes>
          <Route element={<ProfileHost />}>
            <Route path="/perfil" element={<ProfilePage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </LanguageProvider>,
  )
  const alias = await screen.findByLabelText("Alias")
  expect(alias).toHaveValue("Ada")
  await user.clear(alias)
  await user.type(alias, "Nera")
  await user.click(screen.getByRole("button", { name: "Guardar cambios" }))
  expect(saveProfile).toHaveBeenCalledWith({ alias: "Nera", sex: "woman" })
  expect(await screen.findByText("Tus datos se han guardado.")).toBeInTheDocument()
})
