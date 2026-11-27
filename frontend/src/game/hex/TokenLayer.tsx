import { useMemo, useRef, type ReactNode, type RefObject } from "react"

import type { BoardToken, Placed, Spot } from "./boardTypes"
import { hexCenter } from "./geometry"
import { UnitToken } from "./tokens"
import type { TokenPress, TokenTap } from "./useBoardPointer"
import { useMarchGlide } from "./useMarchGlide"
import type { MarchPath } from "./useMarchFilm"
import { useI18n } from "../../i18n/language"

export function TokenLayer({
  boardId,
  size,
  points,
  placed,
  dimmed,
  marks,
  tokens,
  tokenSpots,
  tokensQuiet,
  march,
  movableIds,
  selectedTokenId,
  spotlightId,
  showTokenNote,
  tokenPress,
  tokenTap,
  onTokenOpen,
  onTokenInspect,
  routeLayer,
  clashLayer,
}: {
  boardId: string
  size: number
  points: string
  placed: Placed[]
  dimmed: Spot[]
  marks: Spot[]
  tokens: BoardToken[]
  tokenSpots?: Record<string, Spot> | null
  tokensQuiet: boolean
  march: MarchPath[] | null
  movableIds?: ReadonlySet<string>
  selectedTokenId?: string | null
  spotlightId?: string | null
  showTokenNote: RefObject<(token: BoardToken | null) => void>
  tokenPress: RefObject<TokenPress | null>
  tokenTap: RefObject<TokenTap | null>
  onTokenOpen?: (id: string) => void
  onTokenInspect?: (id: string) => void
  routeLayer: ReactNode
  clashLayer: ReactNode
}) {
  const { t } = useI18n()
  const shaded = useMemo(
    () => dimmed.map((cell) => ({ ...cell, ...hexCenter(cell.q, cell.r, size) })),
    [dimmed, size],
  )
  const marked = new Set(marks.map((mark) => `${mark.q},${mark.r}`))
  const tokenStacks = new Map<string, BoardToken[]>()
  for (const token of tokens) {
    const at = tokenSpots?.[token.id] ?? token
    const key = `${at.q},${at.r}`
    const row = tokenStacks.get(key)
    if (row) row.push(token)
    else tokenStacks.set(key, [token])
  }
  const marchKey = march?.map((path) =>
    `${path.id}:${path.spots.map((spot) => `${spot.q},${spot.r}`).join(">")}`,
  ).join("|") ?? ""
  const marchLayer = useRef<SVGGElement>(null)
  useMarchGlide(marchLayer, march, marchKey, size)
  const gliding = useMemo(() => new Set(march?.map((path) => path.id) ?? []), [marchKey, march])

  return (
    <>
      <g className="hex-dim" pointerEvents="none">
        {shaded.map((cell) => (
          <polygon key={`dim-${cell.q},${cell.r}`} points={points} transform={`translate(${cell.x} ${cell.y})`}>
            <title>{t("sightDim")}</title>
          </polygon>
        ))}
      </g>
      <g className="hex-marks" pointerEvents="none">
        {placed.filter((cell) => marked.has(`${cell.q},${cell.r}`)).map((cell) => {
          const arm = size * 0.18
          return (
            <g key={`mark-${cell.q},${cell.r}`} transform={`translate(${cell.x} ${cell.y})`}>
              <path className="hex-mark-cross is-shadow" d={`M ${-arm} 0 H ${arm} M 0 ${-arm} V ${arm}`} />
              <path className="hex-mark-cross" d={`M ${-arm} 0 H ${arm} M 0 ${-arm} V ${arm}`} />
            </g>
          )
        })}
      </g>
      {routeLayer}
      {tokens.length > 0 ? (
        <g
          ref={marchLayer}
          className={tokensQuiet ? "hex-tokens is-quiet" : "hex-tokens"}
          pointerEvents="none"
        >
          {tokens.map((token) => {
            const at = tokenSpots?.[token.id] ?? token
            const spot = hexCenter(at.q, at.r, size)
            const stack = tokenStacks.get(`${at.q},${at.r}`) ?? [token]
            const slot = stack.findIndex((item) => item.id === token.id)
            const spread = stack.length > 1 ? (slot - (stack.length - 1) / 2) * size * 0.42 : 0
            const movable = movableIds?.has(token.id) ?? false
            const onMarch = gliding.has(token.id)
            return (
              <g
                key={token.id}
                data-token={token.id}
                className={onMarch ? "hex-token-glide" : undefined}
                transform={onMarch ? undefined : `translate(${spot.x + spread} ${spot.y})`}
              >
                <UnitToken
                  boardId={boardId}
                  faction={token.faction}
                  kind={token.kind}
                  color={token.color}
                  x={0}
                  y={0}
                  size={size}
                  label={token.label}
                  mark={token.mark}
                  attention={token.attention}
                />
                <circle
                  className={selectedTokenId === token.id || spotlightId === token.id ? "hex-token-hit is-selected" : "hex-token-hit"}
                  r={size * 0.72}
                  onPointerEnter={() => showTokenNote.current(token)}
                  onPointerLeave={() => showTokenNote.current(null)}
                  onPointerDown={(event) => {
                    event.stopPropagation()
                    tokenPress.current = { id: token.id, x: event.clientX, y: event.clientY, armed: false }
                  }}
                  onPointerUp={(event) => {
                    const start = tokenPress.current
                    if (!start || start.id !== token.id || start.armed) return
                    event.stopPropagation()
                    const now = performance.now()
                    if (tokenTap.current?.id === token.id && now - tokenTap.current.at < 450) {
                      tokenTap.current = null
                      onTokenInspect?.(token.id)
                      return
                    }
                    tokenTap.current = { id: token.id, at: now }
                  }}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (!movable) onTokenOpen?.(token.id)
                  }}
                  onDoubleClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    tokenTap.current = null
                    onTokenInspect?.(token.id)
                  }}
                />
              </g>
            )
          })}
        </g>
      ) : null}
      {clashLayer}
    </>
  )
}
