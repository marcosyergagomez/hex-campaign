import type { CampaignDetail } from "../../api"
import { useI18n } from "../../i18n/language"
import { MissingSheets, WaitingNames } from "./PrepStatus"
import type { BoardView } from "./useBoardView"

export function CampaignDock({
  campaign,
  view,
  filmPlaying,
  canReplay,
  onReplay,
  ordering,
  locking,
  busy,
  onSaveFort,
  onFinishRoads,
  onLock,
}: {
  campaign: CampaignDetail
  view: BoardView
  filmPlaying: boolean
  canReplay: boolean
  onReplay: () => void
  ordering: boolean
  locking: boolean
  busy: boolean
  onSaveFort: () => void
  onFinishRoads: () => void
  onLock: () => void
}) {
  const { t } = useI18n()
  const { stage, lostNames, deployPieces } = view
  if (!stage && !filmPlaying && !canReplay && campaign.phase !== "orders" && !lostNames) return null
  return (
    <div className="play-dock">
      <div className="play-dock-copy">
        {stage && campaign.you ? (
          <p className="play-dock-title">
            {stage === "waiting" ? null : (
              <span>{stage === "fort" ? "1" : stage === "roads" ? "2" : "3"} / 3</span>
            )}
            {stage === "fort"
              ? t("prepFortTitle")
              : stage === "roads"
                ? t("prepRoadsTitle")
                : stage === "armies"
                  ? t("prepNamesTitle")
                  : t("prepWaitingTitle")}
          </p>
        ) : null}
        {filmPlaying || stage || campaign.phase === "orders" || lostNames || canReplay ? (
          <p className="hint">
            {filmPlaying
              ? t("ordersFilm")
              : stage === "fort"
                ? t("prepFortHint")
                : stage === "roads"
                  ? t("roadsHint")
                  : stage === "armies"
                    ? t("prepNamesHint")
                    : stage === "waiting"
                      ? t("prepWaitingHint")
                      : campaign.phase === "orders"
                        ? t("ordersHint")
                        : lostNames
                          ? t("sightLost", { name: lostNames })
                          : t("ordersReplayHint")}
          </p>
        ) : null}
        {stage === "armies" ? (
          <MissingSheets pieces={deployPieces} rosterRequired={campaign.rules.roster_required} />
        ) : null}
        {stage === "waiting" ? <WaitingNames campaign={campaign} /> : null}
        {stage === "roads" && campaign.roads ? (
          <p className="quiet">
            {t("roadsBudget", {
              laid: String(campaign.roads.laid),
              budget: String(campaign.roads.budget),
            })}
            {campaign.road_ready.length > 0
              ? ` · ${t("roadsReadyList", {
                names: campaign.members
                  .filter((member) => campaign.road_ready.includes(member.player_id))
                  .map((member) => member.alias)
                  .join(", "),
              })}`
              : ""}
          </p>
        ) : null}
        {campaign.phase === "orders" && campaign.you?.orders_locked ? (
          <p className="quiet" role="status">{t("ordersFixed")}</p>
        ) : null}
        {campaign.phase === "orders" && campaign.members.some((member) => member.orders_locked && member.player_id !== campaign.you?.player_id) ? (
          <p className="quiet">
            {t("ordersFixedNames", {
              names: campaign.members
                .filter((member) => member.orders_locked && member.player_id !== campaign.you?.player_id)
                .map((member) => member.alias)
                .join(", "),
            })}
          </p>
        ) : null}
      </div>
      <div className="play-dock-actions">
        {canReplay ? (
          <button type="button" className="button-quiet" onClick={onReplay}>
            {t("ordersReplay")}
          </button>
        ) : null}
        {stage === "fort" ? (
          <button
            type="button"
            disabled={busy || !campaign.fortresses.some((fort) => fort.player_id === campaign.you?.player_id)}
            onClick={onSaveFort}
          >
            {t("prepSave")}
          </button>
        ) : null}
        {stage === "roads" && campaign.roads ? (
          <button type="button" disabled={campaign.roads.ready || busy} onClick={onFinishRoads}>
            {campaign.roads.ready ? t("roadsWaiting") : t("roadsFinish")}
          </button>
        ) : null}
        {campaign.phase === "orders" && !campaign.you?.orders_locked ? (
          <button type="button" disabled={!ordering || locking || busy} onClick={onLock}>
            {locking ? t("ordersFixing") : t("ordersFix")}
          </button>
        ) : null}
      </div>
    </div>
  )
}
