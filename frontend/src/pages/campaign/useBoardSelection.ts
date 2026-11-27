import { useRef, useState } from "react"

export function useBoardSelection() {
  const [selectedToken, setSelectedToken] = useState<string | null>(null)
  const [spotlightId, setSpotlightId] = useState<string | null>(null)
  const [focusSpot, setFocusSpot] = useState<{ q: number; r: number; n: number } | null>(null)
  const [sheetArmy, setSheetArmy] = useState<string | null>(null)
  const spotAt = useRef<((clientX: number, clientY: number) => { q: number; r: number } | null) | null>(null)
  const skipClick = useRef(false)
  return {
    selectedToken,
    setSelectedToken,
    spotlightId,
    setSpotlightId,
    focusSpot,
    setFocusSpot,
    sheetArmy,
    setSheetArmy,
    spotAt,
    skipClick,
  }
}

export type BoardSelection = ReturnType<typeof useBoardSelection>
