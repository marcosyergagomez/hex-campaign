import { de } from "./de"
import { en, type MessageKey } from "./en"
import { es } from "./es"
import { fr } from "./fr"
import { it } from "./it"

export type { MessageKey } from "./en"

export const languages = ["en", "es", "fr", "it", "de"] as const

export type Language = (typeof languages)[number]

export const languageNames: Record<Language, string> = {
  en: "English",
  es: "Español",
  fr: "Français",
  it: "Italiano",
  de: "Deutsch",
}

export const catalogs: Record<Language, Record<MessageKey, string>> = {
  en,
  es,
  fr,
  it,
  de,
}

// ageHint repeats the Spanish sentence of minAge, so only minAge is indexed.
const fromSpanish = [
  "chooseOption",
  "offline",
  "incomplete",
  "sessionCheckFailed",
  "signInFailed",
  "logOutFailed",
  "registerFailed",
  "emailTaken",
  "aliasTaken",
  "aliasShape",
  "minAge",
  "passwordTooLong",
  "passwordTooShort",
  "invalidEmail",
  "invalidSex",
  "fieldRequired",
  "invalidValue",
  "badCredentials",
  "invalidSession",
  "badOrigin",
  "badRequest",
  "tooMany",
  "tooLarge",
  "mailFailed",
  "acceptedDetail",
  "rulesInvalid",
  "campaignNotFound",
  "campaignRevisionConflict",
  "campaignOpenLimit",
  "mapUnknown",
  "factionInvalid",
  "colorInvalid",
  "colorTaken",
  "identityRequired",
] as const satisfies readonly MessageKey[]

const knownMessages: Record<string, MessageKey> = indexSpanish(fromSpanish)

const CLIENT_MARK = "\u0000"

export function clientNotice(key: MessageKey): string {
  return `${CLIENT_MARK}${key}`
}

export function isLanguage(value: string | null): value is Language {
  return value !== null && (languages as readonly string[]).includes(value)
}

export function isMessageKey(value: string): value is MessageKey {
  return Object.hasOwn(en, value)
}

export function translate(
  language: Language,
  key: MessageKey,
  vars?: Record<string, string>,
): string {
  let text = catalogs[language][key]
  if (!vars) {
    return text
  }
  for (const [name, value] of Object.entries(vars)) {
    text = text.replaceAll(`{${name}}`, value)
  }
  return text
}

export function noticeText(language: Language, message: string): string {
  if (message.startsWith(CLIENT_MARK)) {
    const key = message.slice(CLIENT_MARK.length)
    return catalogs[language][isMessageKey(key) ? key : "incomplete"]
  }
  const key = knownMessages[message]
  return key ? catalogs[language][key] : message
}

function indexSpanish(keys: readonly MessageKey[]): Record<string, MessageKey> {
  const index: Record<string, MessageKey> = {}
  for (const key of keys) {
    const sentence = es[key]
    if (Object.hasOwn(index, sentence)) {
      throw new Error(`Repeated Spanish sentence for ${key}`)
    }
    index[sentence] = key
  }
  return index
}
