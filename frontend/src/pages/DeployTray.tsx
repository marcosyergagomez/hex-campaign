import { useId, useRef, useState } from "react"

import { TokenDefinitions, UnitToken, type UnitKind } from "../game/hex/tokens"
import { useI18n } from "../i18n/language"

export type DeployPiece = {
  id: string
  kind: UnitKind
  faction: string
  color: string
  label: string
  mark?: number
  placed: boolean
  attention?: boolean
}

type Spot = { q: number; r: number }

export function DeployTray({
  pieces,
  selectedId,
  onSelect,
  onOpen,
  onDropAt,
  spotAt,
}: {
  pieces: DeployPiece[]
  selectedId: string | null
  onSelect: (id: string) => void
  onOpen: (id: string) => void
  onDropAt: (id: string, spot: Spot) => void
  spotAt: { current: ((clientX: number, clientY: number) => Spot | null) | null }
}) {
  const { t } = useI18n()
  const drag = useRef<{ id: string; x: number; y: number; moved: boolean } | null>(null)
  const tap = useRef<{ id: string; at: number } | null>(null)
  const [ghost, setGhost] = useState<{ id: string; x: number; y: number } | null>(null)
  const ghostPiece = ghost ? pieces.find((piece) => piece.id === ghost.id) : undefined

  return (
    <>
      <ul className="deploy-tray" aria-label={t("prepNamesTitle")}>
        {pieces.map((piece) => (
          <li key={piece.id}>
            <button
              type="button"
              className={[
                "deploy-piece",
                selectedId === piece.id ? "is-selected" : "",
                piece.placed ? "" : "is-loose",
              ].filter(Boolean).join(" ")}
              aria-pressed={selectedId === piece.id}
              onPointerDown={(event) => {
                if (event.button !== 0) return
                onSelect(piece.id)
                drag.current = { id: piece.id, x: event.clientX, y: event.clientY, moved: false }
              }}
              onPointerMove={(event) => {
                const current = drag.current
                if (!current || current.id !== piece.id) return
                if (Math.hypot(event.clientX - current.x, event.clientY - current.y) > 8) {
                  current.moved = true
                  event.currentTarget.setPointerCapture(event.pointerId)
                  setGhost({ id: current.id, x: event.clientX, y: event.clientY })
                }
              }}
              onPointerUp={(event) => {
                const current = drag.current
                if (!current || current.id !== piece.id) return
                drag.current = null
                setGhost(null)
                if (current.moved) {
                  const spot = spotAt.current?.(event.clientX, event.clientY) ?? null
                  if (spot) onDropAt(current.id, spot)
                  return
                }
                if (piece.kind !== "army") return
                const now = performance.now()
                if (tap.current?.id === piece.id && now - tap.current.at < 450) {
                  tap.current = null
                  onOpen(piece.id)
                  return
                }
                tap.current = { id: piece.id, at: now }
              }}
              onDoubleClick={() => {
                if (piece.kind !== "army") return
                tap.current = null
                onOpen(piece.id)
              }}
            >
              <PieceArt piece={piece} />
              <span>{piece.label}</span>
            </button>
          </li>
        ))}
      </ul>
      {ghost && ghostPiece ? (
        <div className="deploy-ghost" style={{ left: ghost.x, top: ghost.y }} aria-hidden="true">
          <PieceArt piece={ghostPiece} />
        </div>
      ) : null}
    </>
  )
}

function PieceArt({ piece }: { piece: DeployPiece }) {
  const boardId = useId().replaceAll(":", "")
  return (
    <svg viewBox="-22 -24 44 48" aria-hidden="true">
      <TokenDefinitions id={boardId} />
      <UnitToken
        boardId={boardId}
        faction={piece.faction}
        kind={piece.kind}
        color={piece.color}
        x={0}
        y={0}
        size={26}
        label=""
        mark={piece.mark}
        attention={piece.attention}
      />
    </svg>
  )
}
