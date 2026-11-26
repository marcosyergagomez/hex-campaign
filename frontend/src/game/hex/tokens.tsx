/** Race-inspired army and explorer tokens. Banner color tints via currentColor. */

import type { SVGProps } from "react"

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

function isFaction(value: string): value is FactionTokenId {
  return (FACTION_TOKEN_IDS as readonly string[]).includes(value)
}

/** Shared defs for one board. Symbol ids: `${boardId}-token-${faction}-${kind}`. */
export function TokenDefinitions({ id }: { id: string }) {
  return (
    <defs>
      {FACTION_TOKEN_IDS.map((faction) => (
        <g key={faction}>
          <symbol id={`${id}-token-${faction}-army`} viewBox="0 0 40 40">
            <ArmyArt faction={faction} />
          </symbol>
          <symbol id={`${id}-token-${faction}-explorer`} viewBox="0 0 40 40">
            <ExplorerArt faction={faction} />
          </symbol>
        </g>
      ))}
      <symbol id={`${id}-token-generic-army`} viewBox="0 0 40 40">
        <GenericArmy />
      </symbol>
      <symbol id={`${id}-token-generic-explorer`} viewBox="0 0 40 40">
        <GenericExplorer />
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
}: {
  boardId: string
  faction: string
  kind: UnitKind
  color: string
  x: number
  y: number
  size: number
  label: string
}) {
  const key = isFaction(faction) ? faction : "generic"
  const href = `#${boardId}-token-${key}-${kind}`
  const scale = size / 28
  const offset = kind === "explorer" ? -size * 0.15 : size * 0.08
  return (
    <g className={`hex-token hex-token-${kind}`} transform={`translate(${x} ${y + offset}) scale(${scale})`} style={{ color }}>
      <title>{label}</title>
      <circle className="hex-token-disk" cx="0" cy="6" r="14" />
      <use href={href} x="-20" y="-26" width="40" height="40" />
    </g>
  )
}

const ink = {
  fill: "currentColor",
  stroke: "#1a140c",
  strokeWidth: 0.9,
  strokeLinejoin: "round" as const,
}

const pale = {
  fill: "#efe2b8",
  stroke: "#1a140c",
  strokeWidth: 0.7,
  strokeLinejoin: "round" as const,
}

const mount = {
  fill: "#2a2218",
  stroke: "#1a140c",
  strokeWidth: 0.9,
  strokeLinejoin: "round" as const,
}

function rim(extra: SVGProps<SVGPathElement> = {}) {
  return {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.4,
    strokeLinejoin: "round" as const,
    ...extra,
  }
}

function GenericArmy() {
  return (
    <g>
      <path d="M20 6 28 12 26 30 14 30 12 12Z" {...ink} />
      <path d="M17 12H23V18H17Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
      <path d="M20 4V10M16 7H24" {...rim({ strokeWidth: 1.8 })} />
    </g>
  )
}

function GenericExplorer() {
  return (
    <g>
      <path d="M8 28C10 20 14 16 20 16S30 20 32 28" {...mount} />
      <path d="M14 18C16 12 18 10 20 10S24 12 26 18" {...ink} />
      <circle cx="20" cy="7" r="3.2" {...ink} />
      <path d="M26 12 34 8 32 14Z" {...pale} />
    </g>
  )
}

function ArmyArt({ faction }: { faction: FactionTokenId }) {
  switch (faction) {
    case "empire":
      return (
        <g>
          <path d="M20 5 29 11 27 30 13 30 11 11Z" {...ink} />
          <path d="M16 12H24V17H16Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M20 3 23 8 17 8Z" {...pale} />
          <path d="M12 18 8 22M28 18 32 22" {...rim()} />
        </g>
      )
    case "bretonnia":
      return (
        <g>
          <path d="M14 30 12 14 20 6 28 14 26 30Z" {...ink} />
          <path d="M20 4V14M17 8H23" {...rim({ strokeWidth: 2 })} />
          <path d="M18 16H22V22H18Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M29 10 35 6" {...rim({ strokeWidth: 2 })} />
        </g>
      )
    case "dwarfs":
      return (
        <g>
          <path d="M12 16H28V28H12Z" {...ink} />
          <path d="M14 16 20 8 26 16Z" {...ink} />
          <path d="M15 22H25" {...rim({ strokeWidth: 2.2 })} />
          <path d="M10 20 6 14 10 14M30 20 34 14 30 14" {...pale} />
        </g>
      )
    case "high_elves":
      return (
        <g>
          <path d="M20 4 27 12 25 30 15 30 13 12Z" {...ink} />
          <path d="M17 6 14 1M23 6 26 1" {...rim()} />
          <path d="M20 10V28M16 16H24" {...rim()} />
          <circle cx="20" cy="8" r="2.4" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
        </g>
      )
    case "wood_elves":
      return (
        <g>
          <path d="M20 5 28 14 24 30 16 30 12 14Z" {...ink} />
          <path d="M20 8 14 18 20 16 26 18Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M11 12C13 8 16 6 20 6" {...rim()} />
          <path d="M29 12C27 8 24 6 20 6" {...rim()} />
        </g>
      )
    case "cathay":
      return (
        <g>
          <path d="M13 28 12 14 20 7 28 14 27 28Z" {...ink} />
          <path d="M16 12H24V16H16Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M14 8H26L24 11H16Z" {...pale} />
          <path d="M20 16V26M17 20H23" {...rim()} />
        </g>
      )
    case "orcs_goblins":
      return (
        <g>
          <path d="M12 28 10 14 20 6 30 14 28 28Z" {...ink} />
          <path d="M15 14 12 10M25 14 28 10" {...rim({ strokeWidth: 1.8 })} />
          <path d="M16 18H24V24H16Z" fill="#1a140c" opacity=".35" />
          <path d="M8 18 4 12 9 14M32 18 36 12 31 14" {...pale} />
        </g>
      )
    case "warriors_chaos":
      return (
        <g>
          <path d="M14 30 12 15 20 7 28 15 26 30Z" {...ink} />
          <path d="M16 8 12 2M24 8 28 2M20 5V11" {...rim({ strokeWidth: 1.8 })} />
          <path d="M17 16H23V22H17Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
        </g>
      )
    case "beastmen":
      return (
        <g>
          <path d="M13 30 12 16 20 9 28 16 27 30Z" {...ink} />
          <path d="M14 10 8 3M26 10 32 3" {...rim({ strokeWidth: 2 })} />
          <circle cx="16" cy="15" r="1.6" fill="#efe2b8" />
          <circle cx="24" cy="15" r="1.6" fill="#efe2b8" />
          <path d="M18 20H22V26H18Z" fill="#1a140c" opacity=".35" />
        </g>
      )
    case "tomb_kings":
      return (
        <g>
          <path d="M14 30 13 16 20 8 27 16 26 30Z" {...ink} />
          <path d="M15 10H25V14H15Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M17 14V20M23 14V20M16 24H24" {...rim()} />
          <path d="M20 4 23 9 17 9Z" {...pale} />
        </g>
      )
    case "chaos_dwarfs":
      return (
        <g>
          <path d="M12 28H28V16H12Z" {...ink} />
          <path d="M14 16 20 7 26 16Z" {...ink} />
          <path d="M16 10H24V13H16Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".6" />
          <path d="M10 18 5 12 10 13M30 18 35 12 30 13" {...pale} />
        </g>
      )
    case "daemons_chaos":
      return (
        <g>
          <path d="M20 8 28 14 26 30 14 30 12 14Z" {...ink} />
          <path d="M14 9 9 2M26 9 31 2M20 5V12" {...rim({ strokeWidth: 1.8 })} />
          <path d="M16 17 20 22 24 17" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
        </g>
      )
    case "dark_elves":
      return (
        <g>
          <path d="M20 5 28 13 25 30 15 30 12 13Z" {...ink} />
          <path d="M16 6 11 1M24 6 29 1" {...rim()} />
          <path d="M18 14H22L21 24H19Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M28 12 34 16" {...rim({ strokeWidth: 1.8 })} />
        </g>
      )
    case "lizardmen":
      return (
        <g>
          <path d="M12 28 11 15 20 7 29 15 28 28Z" {...ink} />
          <path d="M16 12H24V16H16Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M20 4 22 9 18 9Z" {...pale} />
          <path d="M14 20 10 24M26 20 30 24" {...rim()} />
        </g>
      )
    case "ogre_kingdoms":
      return (
        <g>
          <path d="M10 30 9 14 20 6 31 14 30 30Z" {...ink} />
          <circle cx="15" cy="15" r="2" fill="#efe2b8" />
          <circle cx="25" cy="15" r="2" fill="#efe2b8" />
          <path d="M16 22H24V27H16Z" fill="#1a140c" opacity=".3" />
          <path d="M8 18H32" {...rim({ strokeWidth: 2 })} />
        </g>
      )
    case "skaven":
      return (
        <g>
          <path d="M14 28 12 15 20 8 28 15 26 28Z" {...ink} />
          <path d="M15 10 11 4M25 10 29 4" {...rim()} />
          <path d="M18 14H22V18H18Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".6" />
          <path d="M20 18Q28 22 30 28" {...rim()} />
        </g>
      )
    case "vampire_counts":
      return (
        <g>
          <path d="M14 30 13 15 20 6 27 15 26 30Z" {...ink} />
          <path d="M16 12H24V16H16Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
          <path d="M17 8 14 3M23 8 26 3" {...rim()} />
          <path d="M18 18 20 24 22 18" fill="#1a140c" opacity=".4" />
        </g>
      )
  }
}

function ExplorerArt({ faction }: { faction: FactionTokenId }) {
  const horse = (
    <path d="M7 29C9 21 13 17 20 17S31 21 33 29L28 29C27 24 24 22 20 22S13 24 12 29Z" {...mount} />
  )
  switch (faction) {
    case "empire":
      return (
        <g>
          {horse}
          <path d="M16 17C17 11 19 9 20 9S23 11 24 17" {...ink} />
          <circle cx="20" cy="6" r="2.8" {...ink} />
          <path d="M24 11 31 7" {...rim({ strokeWidth: 1.8 })} />
        </g>
      )
    case "bretonnia":
      return (
        <g>
          {horse}
          <path d="M16 17C17 10 19 8 20 8S23 10 24 17" {...ink} />
          <path d="M20 3 22 8 18 8Z" {...pale} />
          <path d="M25 10 34 5 32 11Z" {...pale} />
        </g>
      )
    case "dwarfs":
      return (
        <g>
          <path d="M8 30C10 23 14 19 20 19S30 23 32 30" {...mount} />
          <path d="M14 19H26V27H14Z" {...ink} />
          <path d="M16 19 20 12 24 19Z" {...ink} />
          <path d="M27 16 34 12" {...rim({ strokeWidth: 2 })} />
        </g>
      )
    case "high_elves":
      return (
        <g>
          {horse}
          <path d="M16 17C17 10 19 8 20 8S23 10 24 17" {...ink} />
          <path d="M17 6 14 1M23 6 26 1" {...rim()} />
          <circle cx="20" cy="5" r="2.4" fill="#efe2b8" stroke="#1a140c" strokeWidth=".7" />
        </g>
      )
    case "wood_elves":
      return (
        <g>
          <path d="M8 30C11 20 15 15 20 15S29 20 32 30" {...mount} />
          <path d="M15 16C16 10 18 8 20 8S24 10 25 16" {...ink} />
          <path d="M14 8C16 4 18 3 20 3S24 4 26 8" {...rim()} />
          <path d="M25 11 33 7" {...rim()} />
        </g>
      )
    case "cathay":
      return (
        <g>
          {horse}
          <path d="M16 17C17 11 19 9 20 9S23 11 24 17" {...ink} />
          <path d="M15 8H25L23 11H17Z" {...pale} />
          <path d="M25 12Q31 10 34 14" {...rim()} />
        </g>
      )
    case "orcs_goblins":
      return (
        <g>
          <path d="M7 30C10 21 14 17 20 17S30 21 33 30" {...mount} />
          <path d="M14 17C15 11 18 9 20 9S25 11 26 17" {...ink} />
          <path d="M15 11 11 6M25 11 29 6" {...rim()} />
          <path d="M26 13 34 10" {...rim({ strokeWidth: 2 })} />
        </g>
      )
    case "warriors_chaos":
      return (
        <g>
          {horse}
          <path d="M16 17C17 11 19 8 20 8S23 11 24 17" {...ink} />
          <path d="M16 6 12 1M24 6 28 1M20 4V10" {...rim({ strokeWidth: 1.8 })} />
        </g>
      )
    case "beastmen":
      return (
        <g>
          <path d="M8 30C11 20 15 15 20 15S29 20 32 30" {...mount} />
          <path d="M15 16C16 10 18 8 20 8S24 10 25 16" {...ink} />
          <path d="M15 8 10 2M25 8 30 2" {...rim({ strokeWidth: 2 })} />
        </g>
      )
    case "tomb_kings":
      return (
        <g>
          {horse}
          <path d="M16 17C17 11 19 9 20 9S23 11 24 17" {...ink} />
          <path d="M16 8H24V11H16Z" fill="#efe2b8" stroke="#1a140c" strokeWidth=".6" />
          <path d="M20 4 22 8 18 8Z" {...pale} />
        </g>
      )
    case "chaos_dwarfs":
      return (
        <g>
          <path d="M8 30C10 23 14 19 20 19S30 23 32 30" {...mount} />
          <path d="M14 19H26V27H14Z" {...ink} />
          <path d="M16 19 20 11 24 19Z" {...ink} />
          <path d="M27 15 35 10" {...rim({ strokeWidth: 2 })} />
        </g>
      )
    case "daemons_chaos":
      return (
        <g>
          <path d="M8 30C11 20 15 15 20 15S29 20 32 30" {...mount} />
          <path d="M15 16C16 10 18 7 20 7S24 10 25 16" {...ink} />
          <path d="M15 7 10 1M25 7 30 1" {...rim({ strokeWidth: 1.8 })} />
          <path d="M26 12 34 8" {...rim()} />
        </g>
      )
    case "dark_elves":
      return (
        <g>
          {horse}
          <path d="M16 17C17 10 19 8 20 8S23 10 24 17" {...ink} />
          <path d="M17 6 13 1M23 6 27 1" {...rim()} />
          <path d="M25 11 34 14" {...rim({ strokeWidth: 1.8 })} />
        </g>
      )
    case "lizardmen":
      return (
        <g>
          <path d="M7 30C10 20 14 15 20 15S30 20 33 30" {...mount} />
          <path d="M15 16C16 10 18 8 20 8S24 10 25 16" {...ink} />
          <path d="M20 4 22 8 18 8Z" {...pale} />
          <path d="M26 12 33 9" {...rim()} />
        </g>
      )
    case "ogre_kingdoms":
      return (
        <g>
          <path d="M6 30C9 20 14 15 20 15S31 20 34 30" {...mount} />
          <path d="M13 17C14 10 17 7 20 7S26 10 27 17" {...ink} />
          <circle cx="16" cy="12" r="1.5" fill="#efe2b8" />
          <circle cx="24" cy="12" r="1.5" fill="#efe2b8" />
        </g>
      )
    case "skaven":
      return (
        <g>
          <path d="M8 30C11 21 15 17 20 17S29 21 32 30" {...mount} />
          <path d="M15 17C16 11 18 9 20 9S24 11 25 17" {...ink} />
          <path d="M15 10 11 4M25 10 29 4" {...rim()} />
          <path d="M20 17Q28 20 31 27" {...rim()} />
        </g>
      )
    case "vampire_counts":
      return (
        <g>
          {horse}
          <path d="M16 17C17 10 19 8 20 8S23 10 24 17" {...ink} />
          <path d="M17 7 14 2M23 7 26 2" {...rim()} />
          <path d="M25 11 33 7" {...rim()} />
        </g>
      )
  }
}
