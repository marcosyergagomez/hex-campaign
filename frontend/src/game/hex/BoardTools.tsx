import { useI18n } from "../../i18n/language"

export function BoardTools({
  shown,
  zoom,
  zoomOutDisabled,
  zoomInDisabled,
  grid,
  showTerritories,
  mapTools,
  territoryCount,
  onZoomOut,
  onFit,
  onZoomIn,
  onToggleGrid,
  onToggleTerritories,
}: {
  shown: boolean
  zoom: number
  zoomOutDisabled: boolean
  zoomInDisabled: boolean
  grid: boolean
  showTerritories: boolean
  mapTools: boolean
  territoryCount: number
  onZoomOut: () => void
  onFit: () => void
  onZoomIn: () => void
  onToggleGrid: () => void
  onToggleTerritories: () => void
}) {
  const { t } = useI18n()
  if (!shown) return null
  return (
    <div className="hex-tools">
      <button type="button" onClick={onZoomOut} disabled={zoomOutDisabled} aria-label={t("mapZoomOut")}>−</button>
      <button type="button" onClick={onFit} aria-label={t("mapFit")}>{Math.round(zoom * 100)}%</button>
      <button type="button" onClick={onZoomIn} disabled={zoomInDisabled} aria-label={t("mapZoomIn")}>+</button>
      {mapTools ? (
        <button type="button" onClick={onToggleGrid} aria-pressed={grid}>{t("mapGrid")}</button>
      ) : null}
      {mapTools && territoryCount > 0 ? (
        <button type="button" onClick={onToggleTerritories} aria-pressed={showTerritories}>
          {t("territoryToggle")}
        </button>
      ) : null}
    </div>
  )
}
