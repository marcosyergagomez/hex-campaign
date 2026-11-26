import type { CampaignDetail, CampaignHex, MapCell } from "../api"
import { clearRoad, finishRoads, placeRoad } from "../api"
import { useI18n } from "../i18n/language"

type KnownHex = Extract<CampaignHex, { known: true }>
type RoadSpot = Pick<MapCell, "q" | "r" | "road"> & { owner_id?: string | null }

export function RoadPreparation({
  campaign,
  busy = false,
  onChange,
}: {
  campaign: CampaignDetail
  busy?: boolean
  onChange: (action: () => Promise<CampaignDetail>) => void
}) {
  const { t } = useI18n()
  const roads = campaign.roads
  if (!roads) return null

  const readyNames = campaign.members
    .filter(member => campaign.road_ready.includes(member.player_id))
    .map(member => member.alias)
    .join(", ")

  return (
    <div className="roads-prep">
      <p>
        {t("roadsBudget", {
          laid: String(roads.laid),
          budget: String(roads.budget),
        })}
      </p>
      {readyNames ? (
        <p className="quiet">{t("roadsReadyList", { names: readyNames })}</p>
      ) : null}
      <button
        type="button"
        disabled={roads.ready || busy}
        onClick={() => {
          const { id, revision } = campaign
          onChange(() => finishRoads(id, revision, campaign))
        }}
      >
        {roads.ready ? t("roadsWaiting") : t("roadsFinish")}
      </button>
    </div>
  )
}

export function toggleOwnRoad(
  campaign: CampaignDetail,
  cell: RoadSpot,
  onChange: (action: () => Promise<CampaignDetail>) => void,
) {
  if (!campaign.roads || campaign.roads.ready || !campaign.you) return
  if (cell.owner_id !== campaign.you.player_id) return
  if (campaign.fortresses.some(fort => fort.q === cell.q && fort.r === cell.r)) return
  const { id, revision } = campaign
  if (cell.road) {
    onChange(() => clearRoad(id, revision, cell.q, cell.r, campaign))
    return
  }
  if (campaign.roads.left <= 0) return
  onChange(() => placeRoad(id, revision, cell.q, cell.r, campaign))
}

export function isKnownHex(cell: CampaignHex): cell is KnownHex {
  return cell.known
}
