import { NavLink, Outlet } from "react-router-dom"

import { LanguageSelect, useI18n } from "./i18n/language"

export function Gate() {
  const { t } = useI18n()
  return (
    <main className="gate">
      <LanguageSelect />
      <section className="gate-story">
        <p className="mark">Hex Campaign</p>
        <h1>{t("storyTitle")}</h1>
        <p>{t("storyLead")}</p>
      </section>
      <section className="panel">
        <nav className="tabs" aria-label={t("accountNav")}>
          <NavLink to="/entrar">{t("signIn")}</NavLink>
          <NavLink to="/alta">{t("createAccount")}</NavLink>
        </nav>
        <Outlet />
      </section>
    </main>
  )
}
