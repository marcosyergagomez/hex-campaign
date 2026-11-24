export function readCookie(name: string): string {
  const prefix = `${name}=`
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim()
    if (!trimmed.startsWith(prefix)) {
      continue
    }
    try {
      return decodeURIComponent(trimmed.slice(prefix.length))
    } catch {
      return ""
    }
  }
  return ""
}
