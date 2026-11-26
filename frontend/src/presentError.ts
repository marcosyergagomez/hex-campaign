import { ApiError, type FieldErrors } from "./api"
import { clientNotice, type MessageKey } from "./i18n/catalog"

/**
 * Turn any failure into field errors the Banner can show.
 * Prefer the server's messages; never collapse a known failure into silence.
 */
export function presentError(error: unknown, fallback: MessageKey): FieldErrors {
  if (!(error instanceof ApiError)) {
    return { form: [clientNotice(fallback)] }
  }
  const fromServer: FieldErrors = {}
  for (const [field, messages] of Object.entries(error.errors)) {
    const kept = messages.filter((message) => message.trim().length > 0)
    if (kept.length > 0) {
      fromServer[field] = kept
    }
  }
  if (Object.keys(fromServer).length > 0) {
    return fromServer
  }
  if (error.status === 0) {
    return { form: [clientNotice("offline")] }
  }
  // Empty body / HTML 404 / parse failure: still tell the player what we tried.
  return { form: [clientNotice(fallback)] }
}
