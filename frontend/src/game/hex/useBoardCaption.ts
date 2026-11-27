import { useCallback, useMemo, useRef } from "react"

import { useI18n } from "../../i18n/language"
import type { BoardToken, OwnedCell, TerritoryPlayer } from "./boardTypes"
import { GROUND_LABEL, GROUND_TIP, GROUND_TIP_ON_ROAD } from "./grounds"

export function useBoardCaption(players: TerritoryPlayer[], tokenNotes?: Record<string, string>) {
  const { t } = useI18n()
  const captionRef = useRef<HTMLParagraphElement>(null)
  const playersById = useMemo(
    () => new Map(players.map((player) => [player.player_id, player])),
    [players],
  )

  function terrainName(cell: OwnedCell) {
    const owner = cell.owner_id ? playersById.get(cell.owner_id) : undefined
    return [
      t(GROUND_LABEL[cell.ground] ?? "groundPlain"),
      ...(cell.road ? [t("mapRoad")] : []),
      ...(cell.bridge ? [t("mapBridge")] : []),
      ...(owner ? [t("territoryOwner", { player: owner.label })] : []),
    ].join(" · ")
  }

  function terrainEffect(cell: OwnedCell) {
    if (cell.road || cell.bridge) {
      return t(GROUND_TIP_ON_ROAD[cell.ground] ?? "groundTipRoadClear")
    }
    return t(GROUND_TIP[cell.ground] ?? "groundTipPlain")
  }

  const label = useRef<(cell: OwnedCell | null) => void>(() => {})
  label.current = (cell) => {
    const node = captionRef.current
    if (!node) {
      return
    }
    if (!cell) {
      node.replaceChildren()
      return
    }
    const title = document.createElement("span")
    title.className = "hex-caption-title"
    title.textContent = terrainName(cell)
    const tip = document.createElement("span")
    tip.className = "hex-caption-tip"
    tip.textContent = terrainEffect(cell)
    node.replaceChildren(title, tip)
  }

  const showTokenNote = useRef<(token: BoardToken | null) => void>(() => {})
  showTokenNote.current = (token) => {
    const node = captionRef.current
    if (!node) return
    const note = token ? tokenNotes?.[token.id] : undefined
    if (!token || !note) {
      node.replaceChildren()
      return
    }
    const title = document.createElement("span")
    title.className = "hex-caption-title"
    title.textContent = token.label
    const tip = document.createElement("span")
    tip.className = "hex-caption-tip"
    tip.textContent = note
    node.replaceChildren(title, tip)
  }

  const onHover = useCallback((cell: OwnedCell | null) => {
    label.current(cell)
  }, [])

  return { captionRef, onHover, showTokenNote }
}
