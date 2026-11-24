import { ApiError, type FieldErrors } from "./api"
import { clientNotice, type MessageKey } from "./i18n/catalog"

export function presentError(error: unknown, fallback: MessageKey): FieldErrors {
  if (!(error instanceof ApiError)) {
    return { form: [clientNotice(fallback)] }
  }
  if (Object.values(error.errors).some((messages) => messages.length > 0)) {
    return error.errors
  }
  const key = error.status === 0 ? "offline" : "incomplete"
  return { form: [clientNotice(key)] }
}
