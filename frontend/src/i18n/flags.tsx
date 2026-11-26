import type { Language } from "./catalog"

type FlagProps = {
  code: Language
  className?: string
}

/** Rectangular flags drawn edge-to-edge; the parent circle clips them. */
export function LanguageFlag({ code, className }: FlagProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 60 40"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      {flagArt(code)}
    </svg>
  )
}

function flagArt(code: Language) {
  switch (code) {
    case "en":
      return (
        <>
          <rect width="60" height="40" fill="#012169" />
          <path d="M0 0 L60 40 M60 0 L0 40" stroke="#fff" strokeWidth="8" />
          <path d="M0 0 L60 40 M60 0 L0 40" stroke="#C8102E" strokeWidth="4" />
          <path d="M30 0 V40 M0 20 H60" stroke="#fff" strokeWidth="12" />
          <path d="M30 0 V40 M0 20 H60" stroke="#C8102E" strokeWidth="6" />
        </>
      )
    case "es":
      return (
        <>
          <rect width="60" height="40" fill="#AA151B" />
          <rect y="10" width="60" height="20" fill="#F1BF00" />
        </>
      )
    case "fr":
      return (
        <>
          <rect width="20" height="40" fill="#002395" />
          <rect x="20" width="20" height="40" fill="#fff" />
          <rect x="40" width="20" height="40" fill="#ED2939" />
        </>
      )
    case "it":
      return (
        <>
          <rect width="20" height="40" fill="#009246" />
          <rect x="20" width="20" height="40" fill="#fff" />
          <rect x="40" width="20" height="40" fill="#CE2B37" />
        </>
      )
    case "de":
      return (
        <>
          <rect width="60" height="40" fill="#000" />
          <rect y="13.33" width="60" height="13.34" fill="#D00" />
          <rect y="26.67" width="60" height="13.33" fill="#FFCE00" />
        </>
      )
  }
}
