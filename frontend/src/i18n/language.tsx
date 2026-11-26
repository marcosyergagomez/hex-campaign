import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
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
import { LanguageFlag } from "./flags"

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
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    function onPointer(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onPointer)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onPointer)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div className="circle-menu language" ref={root}>
      <button
        type="button"
        className="circle-trigger flag-trigger"
        aria-label={t("language")}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((value) => !value)}
      >
        <LanguageFlag code={language} className="circle-flag" />
      </button>
      {open ? (
        <ul className="circle-panel" role="listbox" aria-label={t("language")}>
          {languages.map((code) => (
            <li key={code} role="none">
              <button
                type="button"
                role="option"
                aria-selected={code === language}
                lang={code}
                className={code === language ? "is-active" : undefined}
                onClick={() => {
                  setLanguage(code)
                  setOpen(false)
                }}
              >
                <span className="circle-flag-chip">
                  <LanguageFlag code={code} className="circle-flag" />
                </span>
                {languageNames[code]}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
