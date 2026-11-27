import { expect, test } from "@playwright/test"

import { installApi } from "./api"

test("enters, opens a campaign and zooms the board", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("hex-campaign-language", "es")
  })
  await installApi(page)
  await page.goto("/entrar")
  await page.getByLabel("Correo").fill("ada@example.com")
  await page.getByLabel("Contraseña").fill("clave-segura")
  await page.getByRole("button", { name: "Entrar" }).click()
  await page.getByRole("link", { name: /La mesa/ }).click()
  await expect(page.getByRole("heading", { name: "La mesa" })).toBeVisible()
  await page.getByRole("button", { name: "Acercar el mapa" }).click()
  await expect(page.getByRole("button", { name: "Ajustar el mapa" })).toHaveText("150%")
})
