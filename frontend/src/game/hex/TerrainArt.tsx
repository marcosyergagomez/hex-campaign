import type { MapCell } from "../../api"

export const EARTH: Record<string, string> = {
  llanura: "#c6b580", colina: "#a1996c", bosque: "#9b9b68",
  bosque_profundo: "#7e895d", montana: "#a39980", montana_rocosa: "#92928b",
  desierto: "#dcc484", tundra: "#c6c9bc", orilla: "#aaa477",
  rio: "#b1ac7f", pantano: "#899572", lago: "#386575", playa: "#d3c295",
  acantilado: "#a69a80", mina: "#b4a17b", campo: "#bbaa70",
}

export function ArtDefinitions({ id, size }: { id: string; size: number }) {
  return (
    <defs>
      <filter id={`${id}-blend`} x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation={size * .17} />
      </filter>
      <filter id={`${id}-grain`} x="0" y="0" width="100%" height="100%">
        <feTurbulence type="fractalNoise" baseFrequency=".48" numOctaves="3" seed="17" />
        <feColorMatrix type="saturate" values="0" />
        <feComponentTransfer><feFuncA type="linear" slope=".18" /></feComponentTransfer>
        <feBlend in="SourceGraphic" mode="soft-light" />
        <feComposite in2="SourceAlpha" operator="in" />
      </filter>
      <linearGradient id={`${id}-water`} x1="0" y1="0" x2=".8" y2="1">
        <stop stopColor="#143b41" /><stop offset=".5" stopColor="#285664" /><stop offset="1" stopColor="#1c414d" />
      </linearGradient>
      <radialGradient id={`${id}-canopy`} cx=".3" cy=".2" r=".8">
        <stop stopColor="#90985b" /><stop offset=".45" stopColor="#576b3c" /><stop offset="1" stopColor="#293e2b" />
      </radialGradient>
      <linearGradient id={`${id}-slope`} x1="0" y1="0" x2="1" y2="1">
        <stop stopColor="#ddd4b5" /><stop offset=".45" stopColor="#a69d84" /><stop offset="1" stopColor="#625e50" />
      </linearGradient>
      <linearGradient id={`${id}-hill-lit`} x1="0" y1="0" x2=".85" y2="1">
        <stop stopColor="#efe6c4" /><stop offset=".4" stopColor="#b7ae86" /><stop offset="1" stopColor="#5f5a45" />
      </linearGradient>
      <linearGradient id={`${id}-dune-lit`} x1="0" y1="0" x2="1" y2="1">
        <stop stopColor="#f3e2a8" /><stop offset=".45" stopColor="#d4b05a" /><stop offset="1" stopColor="#9a7535" />
      </linearGradient>
      <pattern id={`${id}-paper`} width={size * 8} height={size * 8} patternUnits="userSpaceOnUse">
        <image href="/terrain/llanura.jpg" width={size * 8} height={size * 8} opacity=".38" />
      </pattern>
      <pattern id={`${id}-ripples`} width={size * 1.7} height={size * 1.3} patternUnits="userSpaceOnUse">
        <path d={`M0 ${size * .2}q${size * .3} ${-size * .05} ${size * .6} 0m${size * .5} ${size * .6}h${size * .3}M${size * .4} ${size}h${size * .2}`} fill="none" stroke="#b4c6b6" strokeWidth={size * .018} opacity=".18" />
      </pattern>
      <symbol id={`${id}-tree`} viewBox="-9 -22 18 26">
        <ellipse cx="2" cy="0" rx="7" ry="3" fill="#202f23" opacity=".35" />
        <path d="M0 1-1-10M-1-5-4-8" stroke="#615536" strokeWidth="1.2" />
        <path d="M-7-7-8-10-6-13-7-16-3-18-1-22 3-20 6-18 5-15 8-12 7-7 4-5 0-4Z" fill={`url(#${id}-canopy)`} stroke="#39472b" strokeWidth=".45" />
        {Array.from({ length: 11 }, (_, i) => (
          <ellipse key={i} cx={(noise(i, 2, 0) - .5) * 11} cy={-7 - noise(i, 3, 0) * 11}
            rx={1.8 + noise(i, 4, 0) * 1.3} ry="2.2" fill={`url(#${id}-canopy)`} opacity=".85" />
        ))}
      </symbol>
      <symbol id={`${id}-pine`} viewBox="-9 -24 18 28">
        <ellipse cy="1" rx="8" ry="3" fill="#303e2e" opacity=".25" />
        <path d="M0 1V-15" stroke="#534633" strokeWidth="2" />
        <path d="M0-24 2-18 1-17 5-13 3-12 7-8 4-7 9-2 5-2 7 0-1-2-7 0-5-3-9-2-5-8-7-8-3-13-5-13-1-18-2-18Z" fill={`url(#${id}-canopy)`} stroke="#314536" strokeWidth=".4" />
        <path d="M0-21-2-17M-1-15-4-12M-1-11-5-7M0-7-5-3M1-13 3-11M1-8 4-5" fill="none" stroke="#8b986a" strokeWidth=".6" opacity=".65" />
      </symbol>
      {Array.from({ length: 5 }, (_, variant) => (
        <g key={variant}>
          <MountainSymbol id={id} variant={variant} rocky={false} />
          <MountainSymbol id={id} variant={variant} rocky />
        </g>
      ))}
      <symbol id={`${id}-cliff`} viewBox="-20 -20 40 26">
        <path d="M-20-6-17-10-10-11-6-17 2-15 6-19 11-16 18-13 16-5 19 3 9 6-1 2-10 5-18 1Z" fill="#766f5c" stroke="#595747" strokeWidth=".5" />
        <path d="M-20-6-17-10-10-11-6-17 2-15 6-19 11-16 18-13 9-8 0-10-9-6Z" fill="#a8aa83" />
        <path d="M-12-8-13-4-10 3M-3-10-5-3-1 1M6-11 7-6 5-2 8 3M14-11 13-5 15 1" stroke="#c1b69a" strokeWidth=".7" fill="none" />
      </symbol>
      <symbol id={`${id}-hill`} viewBox="-22 -24 44 32">
        <ellipse cy="4" rx="19" ry="3.5" fill="#3a372c" opacity=".24" />
        <path d="M-19 4C-13-1-9-18-1-20S11-4 20 4Z" fill={`url(#${id}-hill-lit)`} stroke="#5a5546" strokeWidth=".45" opacity=".92" />
        <path d="M-1-20 3-8 11-1 20 4 7 1-1-6Z" fill="#464236" opacity=".42" />
        <path d="M-9-10Q-1-22 5-9" fill="none" stroke="#efe6c8" strokeWidth="1.1" opacity=".62" />
        <path d="M-16 4C-11 1-7-9 1-10S12 1 16 4Z" fill={`url(#${id}-hill-lit)`} stroke="#5f5a48" strokeWidth=".4" opacity=".88" />
        <path d="M1-10 5-3 16 4 4 1Z" fill="#4a4638" opacity=".38" />
      </symbol>
      <symbol id={`${id}-dune`} viewBox="-20 -12 40 18">
        <ellipse cy="3" rx="17" ry="3" fill="#7a5f2e" opacity=".16" />
        <path d="M-19 3C-11-1-5-9 2-8S13 0 19 3Q2 0-19 3" fill={`url(#${id}-dune-lit)`} stroke="#b08a42" strokeWidth=".45" opacity=".9" />
        <path d="M2-8 7-1 19 3 5 0Z" fill="#8f6c36" opacity=".4" />
        <path d="M-7-2Q2-9 9-1" fill="none" stroke="#f4e6b8" strokeWidth="1" opacity=".7" />
        <path d="M-14 3C-9 1-5-4 1-3S10 2 13 3Z" fill={`url(#${id}-dune-lit)`} opacity=".82" stroke="#b89550" strokeWidth=".35" />
      </symbol>
      <symbol id={`${id}-reeds`} viewBox="-8 -12 16 16">
        <path d="M-8 2Q0 5 8 1M-3 0-5-9M0 1V-12M3 0 6-8" fill="none" stroke="#555e3b" strokeWidth="1" />
        <path d="M-5-10V-6M0-11V-7M6-9 5-6" stroke="#8f7847" strokeWidth="2" />
      </symbol>
      <symbol id={`${id}-rock`} viewBox="-8 -7 16 12">
        <path d="M-8 2-5-4 1-7 7-2 8 3Z" fill="#a3997e" stroke="#7c755f" strokeWidth=".6" />
        <path d="M1-7 0 1 8 3 7-2Z" fill="#777363" />
      </symbol>
      <symbol id={`${id}-keep`} viewBox="-20 -29 40 38">
        <ellipse cy="4" rx="20" ry="5" fill="#393729" opacity=".3" />
        <path d="M-18-4-10-12 8-13 18-5 15 5-1 9-16 4Z" fill="#767657" stroke="#514c3c" strokeWidth=".7" />
        <path d="M-16-4-8-10 7-10 15-4 12 3-1 6-13 2Z" fill="#b5a982" stroke="#d0c09a" strokeWidth="2.5" />
        <path d="M-5 0V-17H-3V-20H0V-17H3V-20H6V-17H8V0Z" fill="#ada181" stroke="#514d3c" strokeWidth=".7" />
        <path d="M3-17H8V0H3" fill="#756f58" />
        {[-14, 12].map((x) => <g key={x} transform={`translate(${x} -1)`}>
          <path d="M-3 3V-9H-4V-12H-2V-10H0V-12H2V-10H4V-9H3V3Z" fill="#bfb18d" stroke="#665e48" strokeWidth=".6" />
          <path d="M1-7V-3" stroke="#514932" />
        </g>)}
        <path d="M-3 7V2Q0-2 3 2V7" fill="#453e30" />
        <path d="M-1-13V-10M5-13V-10M-1-7V-4M5-7V-4" stroke="#514b38" strokeWidth="1.2" />
        <path d="M1-20V-28L9-25 1-23" fill="#8c4330" stroke="#55452d" strokeWidth=".7" />
      </symbol>
      <symbol id={`${id}-mine`} viewBox="-17 -20 34 26">
        <path d="M-17 3-11-11-3-19 8-13 17 3Z" fill="#92856b" stroke="#6b624f" />
        <path d="M-6 3V-7Q0-15 6-7V3Z" fill="#383a30" stroke="#b29b71" strokeWidth="2.5" />
        <path d="M-6 4-10 8M6 4 10 8M-8 6H8" stroke="#665740" strokeWidth="1.4" />
      </symbol>
    </defs>
  )
}

function MountainSymbol({ id, variant, rocky }: { id: string; variant: number; rocky: boolean }) {
  const peak = -4 + noise(variant, 8, 0) * 8
  const height = 25 + noise(variant, 9, 0) * 9
  return (
    <symbol id={`${id}-${rocky ? "crag" : "peak"}-${variant}`} viewBox="-22 -36 44 42">
      <ellipse cx="3" cy="2" rx="19" ry="4" fill="#424a3c" opacity=".22" />
      <path d={`M-22 3-17-5-13-8-9-17 ${peak - 4},${-height + 7} ${peak},${-height} ${peak + 5},${-height + 10} 10-16 14-8 22 4 9 1 2 5-9 2Z`}
        fill={`url(#${id}-slope)`} stroke="#6e6a58" strokeWidth=".45" />
      <path d={`M${peak},${-height} ${peak + 2},${-height + 12} 1-11 7-5 10 2 22 4 14-8 10-16 ${peak + 5},${-height + 10}Z`}
        fill={rocky ? "#5c6764" : "#736f5f"} />
      {Array.from({ length: 14 }, (_, i) => {
        const x = -18 + i * 2.7
        const top = -3 - (1 - Math.abs(x) / 22) * (height - 5)
        const bend = noise(variant, i, 3) * 4 - 2
        return <path key={i} d={`M${x},${top}l${bend},4 ${-2 - bend},5 1,3 -3,4`}
          stroke={i % 3 === 0 ? "#d9cfaf" : "#5c6051"} opacity={i % 3 === 0 ? .7 : .35} strokeWidth=".55" fill="none" />
      })}
      {rocky ? <path d={`M${peak},${-height} ${peak - 6},${-height + 12} ${peak - 2},${-height + 10} ${peak},${-height + 15} ${peak + 2},${-height + 10} ${peak + 6},${-height + 12}Z`} fill="#dce0d3" /> : null}
    </symbol>
  )
}

export type Ornament = { x: number; y: number; kind: string; scale: number; mirror: number; variant: number }

// Stable across renders, independent of input ordering and the campaign's random state.
export function noise(q: number, r: number, index: number): number {
  let n = Math.imul(q, 374761393) ^ Math.imul(r, 668265263) ^ Math.imul(index + 1, 1274126177)
  n = Math.imul(n ^ (n >>> 13), 1274126177)
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296
}

export function ornaments(cell: MapCell): Ornament[] {
  const forest = cell.ground === "bosque" || cell.ground === "bosque_profundo"
  const mountain = cell.ground === "montana" || cell.ground === "montana_rocosa"
  const hills = cell.ground === "colina"
  const desert = cell.ground === "desierto"
  const count = forest ? 32 : mountain ? 7 : hills ? 5 : desert ? 5 : cell.ground === "pantano" ? 14 : 14
  return Array.from({ length: count }, (_, i) => {
    const x = (noise(cell.q, cell.r, i * 3) - .5) * (hills || desert ? 38 : 43)
    const y = (noise(cell.q, cell.r, i * 3 + 1) - .5) * (hills || desert ? 32 : 38) + (hills ? 7 : 9)
    const variant = noise(cell.q, cell.r, i * 3 + 2)
    let kind = "grass"
    if (forest) kind = cell.ground === "bosque_profundo" || variant > .75 ? "pine" : "tree"
    else if (mountain) kind = cell.ground === "montana_rocosa" ? "crag" : "peak"
    else if (cell.ground === "acantilado") kind = "cliff"
    else if (hills) kind = i === count - 1 && variant > .5 ? "rock" : "hill"
    else if (cell.ground === "pantano" || cell.ground === "orilla") kind = "reeds"
    else if (desert) kind = variant > .9 ? "rock" : "dune"
    else if (cell.ground === "playa") kind = "dune"
    else if (cell.ground === "tundra") kind = "rock"
    else if (cell.ground === "llanura") kind = variant > .9 ? "rock" : variant > .65 ? "scrub" : "grass"
    if (forest && i % 7 === 0) kind = "scrub"
    if (mountain && i % 3 === 0) kind = variant > .5 ? "rock" : "scrub"
    const scale = mountain ? .4 + variant * .55
      : forest ? .32 + variant * .38
      : hills ? .55 + variant * .35
      : desert ? .55 + variant * .32
      : .4 + variant * .35
    return { x, y, kind, scale, mirror: variant > .5 ? -1 : 1, variant: Math.floor(variant * 5) }
  })
}

export function OrnamentArt({ mark, id }: { mark: Ornament; id: string }) {
  if (mark.kind === "scrub") {
    return <g opacity=".65"><ellipse rx="5" ry="2" fill="#737c4b" /><path d="M-4 0-2-3 0-2 2-4 4-1" stroke="#98966a" fill="none" strokeWidth="1.5" /></g>
  }
  if (mark.kind === "grass") {
    return <path d="M-3 0-4-3M0 0 1-4M3 0 5-2" fill="none" stroke="#777d4e" strokeWidth=".8" opacity=".7" />
  }
  const mountain = mark.kind === "peak" || mark.kind === "crag"
  const box = mountain ? [-22, -36, 44, 42]
    : mark.kind === "cliff" ? [-20, -20, 40, 26]
    : mark.kind === "hill" ? [-22, -24, 44, 32]
    : mark.kind === "dune" ? [-20, -12, 40, 18]
    : mark.kind === "pine" ? [-9, -24, 18, 28]
    : mark.kind === "tree" ? [-9, -22, 18, 26]
    : mark.kind === "reeds" ? [-8, -12, 16, 16] : [-8, -7, 16, 12]
  return <use href={`#${id}-${mark.kind}${mountain ? `-${mark.variant}` : ""}`} x={box[0]} y={box[1]} width={box[2]} height={box[3]} />
}

export function Fields() {
  return (
    <g transform="rotate(-18)">
      <path d="M-18-9H-1V10H-18Z" fill="#b49455" stroke="#807444" strokeWidth=".8" />
      <path d="M2-12H17V8H2Z" fill="#8f965c" stroke="#727847" strokeWidth=".8" />
      {[-6, -2, 2, 6].map((y) => <path key={y} d={`M-16 ${y}H-3M4 ${y - 2}H15`} stroke="#ded09a" strokeWidth="1" opacity=".6" />)}
    </g>
  )
}
