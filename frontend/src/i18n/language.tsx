import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { readCookie } from "../cookies"
import {
  isLanguage,
  languageNames,
  languages,
  noticeText,
  translate,
  type Language,
  type MessageKey,
} from "./catalog"

const STORAGE_KEY = "hex-campaign-language"
const COOKIE = "hex_lang"

type I18n = {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: MessageKey, vars?: Record<string, string>) => string
  text: (message: string) => string
}

const LanguageContext = createContext<I18n | null>(null)

function savedLanguage(): Language | null {
  const value = readCookie(COOKIE)
  return isLanguage(value) ? value : null
}

function writeCookie(language: Language) {
  const secure = location.protocol === "https:" ? "; Secure" : ""
  const value = encodeURIComponent(language)
  document.cookie = `${COOKIE}=${value}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`
}

function initialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(stored)) {
      return stored
    }
  } catch {
    // Private mode can refuse local storage. The cookie and the browser still work.
  }
  return savedLanguage() ?? browserLanguage() ?? "en"
}

function browserLanguage(): Language | null {
  const tags = navigator.languages?.length ? navigator.languages : [navigator.language]
  for (const tag of tags) {
    const code = tag.slice(0, 2).toLowerCase()
    if (isLanguage(code)) {
      return code
    }
  }
  return null
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage)

  useLayoutEffect(() => {
    document.documentElement.lang = language
    writeCookie(language)
    try {
      localStorage.setItem(STORAGE_KEY, language)
    } catch {
      // The cookie already carries the choice to the confirmation page.
    }
  }, [language])

  const value = useMemo<I18n>(
    () => ({
      language,
      setLanguage: setLanguageState,
      t: (key, vars) => translate(language, key, vars),
      text: (message) => noticeText(language, message),
    }),
    [language],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useI18n(): I18n {
  const value = useContext(LanguageContext)
  if (!value) {
    throw new Error("LanguageProvider is missing")
  }
  return value
}

export function LanguageSelect() {
  const { language, setLanguage, t } = useI18n()
  return (
    <div className="language">
      <select
        value={language}
        aria-label={t("language")}
        onChange={(event) => {
          const next = event.target.value
          if (isLanguage(next)) {
            setLanguage(next)
          }
        }}
      >
        {languages.map((code) => (
          <option key={code} value={code} lang={code}>
            {languageNames[code]}
          </option>
        ))}
      </select>
    </div>
  )
}
