/** A round badge: the player's colour is the ring, the race is the emblem. */

import { useId } from "react"

export type UnitKind = "army" | "explorer"

export const FACTION_TOKEN_IDS = [
  "empire",
  "bretonnia",
  "dwarfs",
  "high_elves",
  "wood_elves",
  "cathay",
  "orcs_goblins",
  "warriors_chaos",
  "beastmen",
  "tomb_kings",
  "chaos_dwarfs",
  "daemons_chaos",
  "dark_elves",
  "lizardmen",
  "ogre_kingdoms",
  "skaven",
  "vampire_counts",
] as const

export type FactionTokenId = (typeof FACTION_TOKEN_IDS)[number]

const ink = "#4a3018"
const dark = "#24160e"

function isFaction(value: string): value is FactionTokenId {
  return (FACTION_TOKEN_IDS as readonly string[]).includes(value)
}

/** Parchment fill and the blank mark used when a race has no emblem yet. */
export function TokenDefinitions({ id }: { id: string }) {
  return (
    <defs>
      <radialGradient id={`${id}-parchment`} cx="38%" cy="32%" r="75%">
        <stop offset="0%" stopColor="#f6ead0" />
        <stop offset="100%" stopColor="#d9c39a" />
      </radialGradient>
      <symbol id={`${id}-token-generic`} viewBox="0 0 40 40">
        <g fill={ink} stroke={dark} strokeWidth="0.7" strokeLinejoin="round">
          <path d="M20 13 26 20 20 27 14 20 Z" />
        </g>
      </symbol>
    </defs>
  )
}

export function UnitToken({
  boardId,
  faction,
  kind,
  color,
  x,
  y,
  size,
  label,
  mark,
  attention = false,
}: {
  boardId: string
  faction: string
  kind: UnitKind
  color: string
  x: number
  y: number
  size: number
  label: string
  mark?: number
  attention?: boolean
}) {
  const known = isFaction(faction)
  const clipId = useId().replaceAll(":", "")
  const scale = size / 26
  return (
    <g
      className={`hex-token hex-token-${kind}`}
      transform={`translate(${x} ${y}) scale(${scale})`}
      style={{ color }}
    >
      <title>{label}</title>
      <circle className="hex-token-rim" cx="0" cy="0" r="15.2" />
      <circle className="hex-token-ring" cx="0" cy="0" r="12.5" />
      <circle className="hex-token-face" cx="0" cy="0" r="10.9" fill={`url(#${boardId}-parchment)`} />
      {kind === "army" ? <path className="hex-token-notch" d="M-2.6 -14.6 0 -17.6 2.6 -14.6 Z" /> : null}
      {known ? (
        <>
          <clipPath id={clipId}>
            <circle cx="0" cy="0" r="10.9" />
          </clipPath>
          <image
            href={`/emblems/${faction}${kind === "explorer" ? "-explorer" : ""}.png`}
            x="-10.9"
            y="-10.9"
            width="21.8"
            height="21.8"
            clipPath={`url(#${clipId})`}
          />
        </>
      ) : (
        <use href={`#${boardId}-token-generic`} x="-16" y="-16" width="32" height="32" />
      )}
      {attention ? (
        <g className="hex-token-alert" transform="translate(10 -11)">
          <circle r="5.4" />
          <text y="0.6">!</text>
        </g>
      ) : null}
      {mark != null ? (
        <g className="hex-token-index" transform="translate(0 10.6)">
          <circle r="3.8" />
          <text y="0.4">{mark}</text>
        </g>
      ) : null}
    </g>
  )
}
