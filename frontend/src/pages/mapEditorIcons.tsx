type IconProps = { className?: string }

export function IconErase({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M16.2 3.3 20.7 7.8a1.5 1.5 0 0 1 0 2.1l-8.9 8.9H6.4L3.3 15.7a1.5 1.5 0 0 1 0-2.1l10.8-10.3a1.5 1.5 0 0 1 2.1 0Zm-2.1 2.2L5.4 14.2l1.9 1.9h3.5l7.2-7.2-3.9-3.4Z"
      />
      <path fill="currentColor" d="M4 20.25h16v1.5H4z" opacity=".55" />
    </svg>
  )
}

export function IconAddHex({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        d="M12 3.2 19.2 7.4v9.2L12 20.8 4.8 16.6V7.4Z"
      />
      <path fill="currentColor" d="M11.25 8.5h1.5v7h-1.5zm-2.75 2.75h7v1.5h-7z" />
    </svg>
  )
}

export function IconRemoveHex({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        d="M12 3.2 19.2 7.4v9.2L12 20.8 4.8 16.6V7.4Z"
      />
      <path fill="currentColor" d="M7.5 11.25h9v1.5h-9z" />
    </svg>
  )
}

export function IconBrush({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M7.2 14.2c1.8 1.8 4.7 1.5 6-.2l5.5-5.5-3.8-3.8-5.5 5.5c-1.7 1.3-2 4.2-.2 6Zm9.4-10.8 3 3 1.2-1.2a1.4 1.4 0 0 0 0-2l-1-1a1.4 1.4 0 0 0-2 0l-1.2 1.2ZM6.1 16.1c-1.7.4-3.1 1.8-3.6 3.6-.2.7.5 1.4 1.2 1.2 1.8-.5 3.2-1.9 3.6-3.6.1-.5-.4-1-.9-.9-.1 0-.2 0-.3-.3Z"
      />
    </svg>
  )
}

export function IconBrushArea({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="2.2" fill="currentColor" />
      <circle cx="12" cy="5.2" r="1.6" fill="currentColor" opacity=".85" />
      <circle cx="12" cy="18.8" r="1.6" fill="currentColor" opacity=".85" />
      <circle cx="6.1" cy="8.6" r="1.6" fill="currentColor" opacity=".85" />
      <circle cx="17.9" cy="8.6" r="1.6" fill="currentColor" opacity=".85" />
      <circle cx="6.1" cy="15.4" r="1.6" fill="currentColor" opacity=".85" />
      <circle cx="17.9" cy="15.4" r="1.6" fill="currentColor" opacity=".85" />
    </svg>
  )
}

export function IconUndo({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12.2 6a7 7 0 1 1-6.3 10.1l1.4-.8A5.4 5.4 0 1 0 12.2 7.6H8.8l2.2 2.2-1.1 1.1L5.8 6.8l4.1-4.1 1.1 1.1-2.2 2.2h3.4Z"
      />
    </svg>
  )
}

export function IconRedo({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M11.8 6a7 7 0 1 0 6.3 10.1l-1.4-.8A5.4 5.4 0 1 1 11.8 7.6h3.4l-2.2 2.2 1.1 1.1 4.1-4.1-4.1-4.1-1.1 1.1 2.2 2.2h-3.4Z"
      />
    </svg>
  )
}

export function IconRoad({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <rect width="48" height="48" fill="#6b6348" />
      <path fill="#8a8160" d="M0 0h48v48H0z" opacity=".35" />
      <path
        fill="none"
        stroke="#d0b982"
        strokeWidth="5"
        strokeLinecap="round"
        d="M10 38 20 24 28 30 38 12"
      />
      <path
        fill="none"
        stroke="#ede0b2"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeDasharray="3 4"
        d="M10 38 20 24 28 30 38 12"
      />
    </svg>
  )
}

export function IconBridge({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <rect width="48" height="48" fill="#6f8a8c" />
      <path fill="#b5aa7f" d="M0 28h48v8H0z" opacity=".55" />
      <path
        fill="none"
        stroke="#504832"
        strokeWidth="2.4"
        d="M6 30c6-10 30-10 36 0"
      />
      <path fill="#c9b780" d="M4 28h40v4H4z" />
      <path fill="#504832" d="M10 20h2v10h-2zm26 0h2v10h-2z" />
      <path fill="#eee0b7" d="M8 27h32v2H8z" opacity=".7" />
    </svg>
  )
}
