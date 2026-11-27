import type { CampaignDetail, CampaignHex, MapCell } from "../api"
import { clearRoad, finishRoads, placeRoad } from "../api"
import { isImpassable } from "../game/hex/terrainContract"
import { useI18n } from "../i18n/language"

type KnownHex = Extract<CampaignHex, { known: true }>
type RoadSpot = Pick<MapCell, "q" | "r" | "road"> & {
  owner_id?: string | null
  ground?: string
}

const STEPS = [
  [1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1],
] as const

function touchesOwnNetwork(campaign: CampaignDetail, cell: RoadSpot): boolean {
  const you = campaign.you?.player_id
  if (!you) return false
  return STEPS.some(([dq, dr]) => {
    const q = cell.q + dq
    const r = cell.r + dr
    if (campaign.fortresses.some((fort) => fort.player_id === you && fort.q === q && fort.r === r)) {
      return true
    }
    const neighbor = campaign.hexes.find((hex) => hex.q === q && hex.r === r)
    return Boolean(neighbor && neighbor.known && neighbor.road && neighbor.owner_id === you)
  })
}

export function roadEdit(
  campaign: CampaignDetail,
  cell: RoadSpot,
): "add" | "clear" | null {
  if (!campaign.roads || campaign.roads.ready || !campaign.you) return null
  if (cell.owner_id !== campaign.you.player_id) return null
  if (campaign.fortresses.some((fort) => fort.q === cell.q && fort.r === cell.r)) return null
  if (isImpassable(cell.ground)) return null
  if (cell.road) return "clear"
  if (campaign.roads.left <= 0 || !touchesOwnNetwork(campaign, cell)) return null
  return "add"
}

export function RoadPreparation({
  campaign,
  busy = false,
  buttonOnly = false,
  onChange,
}: {
  campaign: CampaignDetail
  busy?: boolean
  buttonOnly?: boolean
  onChange: (action: () => Promise<CampaignDetail>) => void
}) {
  const { t } = useI18n()
  const roads = campaign.roads
  if (!roads) return null

  const readyNames = campaign.members
    .filter(member => campaign.road_ready.includes(member.player_id))
    .map(member => member.alias)
    .join(", ")

  const button = (
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
  )
  if (buttonOnly) return button
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
      {button}
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
  if (isImpassable(cell.ground)) return
  const { id, revision } = campaign
  if (cell.road) {
    onChange(() => clearRoad(id, revision, cell.q, cell.r, campaign))
    return
  }
  if (campaign.roads.left <= 0 || !touchesOwnNetwork(campaign, cell)) return
  onChange(() => placeRoad(id, revision, cell.q, cell.r, campaign))
}

export function isKnownHex(cell: CampaignHex): cell is KnownHex {
  return cell.known
}
