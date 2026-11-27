import { ArmyModal } from "../ArmySheets"
import { DeployTray } from "../DeployTray"
import { HexBoard } from "../../game/hex/HexBoard"
import type { MarchPath } from "../../game/hex/useMarchFilm"
import { useI18n } from "../../i18n/language"
import { presentError } from "../../presentError"
import { CampaignDock } from "./CampaignDock"
import type { BoardSelection } from "./useBoardSelection"
import { useBoardView } from "./useBoardView"
import type { CampaignSession } from "./useCampaignSession"
import type { Orders } from "./useOrders"
import type { Preparation } from "./usePreparation"

export function CampaignBoard({
  session,
  selection,
  prep,
  orders,
  film,
}: {
  session: CampaignSession
  selection: BoardSelection
  prep: Preparation
  orders: Orders
  film: { playing: boolean; paths: MarchPath[] | null; canReplay: boolean; replay: () => void }
}) {
  const { t } = useI18n()
  const view = useBoardView(session, selection, orders, film.playing)
  const campaign = session.campaign
  if (!campaign || campaign.hexes.length === 0 || campaign.phase === "recruiting") return null
  const { stage, locator, shownTokens, deployPieces } = view
  return (
    <section className="campaign-map is-play" aria-label={t("territoryTitle")}>
      <div className="play-map-meta">
        <ul className="territory-legend">
          {campaign.members.filter((member) => member.color).map((member) => {
            const faction = session.options?.factions.find((item) => item.id === member.faction)
            return (
              <li key={member.player_id}>
                <span className="territory-dot" style={{ backgroundColor: member.color }} aria-hidden="true" />
                <span><strong>{member.alias}</strong>{faction ? <> · {t(faction.label)}</> : null}</span>
              </li>
            )
          })}
        </ul>
      </div>
      <div className={[
        "play-board",
        stage === "armies" ? "has-tray" : "",
        locator.length > 0 ? "has-rail" : "",
      ].filter(Boolean).join(" ")}>
        {stage === "armies" ? (
          <DeployTray
            pieces={deployPieces}
            selectedId={selection.selectedToken}
            onSelect={selection.setSelectedToken}
            onOpen={selection.setSheetArmy}
            onDropAt={prep.dropPiece}
            spotAt={selection.spotAt}
          />
        ) : null}
        <HexBoard
          cells={view.known}
          unknown={view.unknown}
          dimmed={view.dimmed}
          traces={view.traces}
          clashes={view.clashes}
          mapTools={false}
          anchors={campaign.fortresses}
          players={view.players}
          tokens={stage === "fort" || stage === "roads" ? [] : shownTokens}
          tokensQuiet={stage === "fort"}
          marks={view.marks}
          markColor={campaign.you?.color || undefined}
          tokenNotes={view.tokenNotes}
          orderPaths={view.drawnPaths}
          march={film.playing ? film.paths : null}
          movableIds={view.movableIds}
          selectedTokenId={selection.selectedToken}
          focusSpot={selection.focusSpot}
          spotlightId={selection.spotlightId}
          spotAtRef={selection.spotAt}
          onOrderToken={orders.ordering ? (id, spot, phase) => {
            selection.setSelectedToken(id)
            if (phase === "move") orders.plan(id, spot)
          } : undefined}
          onTokenDrop={stage === "armies" && !session.busy ? prep.dropPiece : undefined}
          onTokenInspect={(id) => {
            const army = campaign.armies.find((item) => item.id === id)
            if (army?.kind === "army") selection.setSheetArmy(id)
          }}
          onCellClick={
            orders.ordering
              ? (cell) => {
                  const token = campaign.armies.find((army) =>
                    army.player_id === campaign.you?.player_id &&
                    !army.destroyed &&
                    army.q === cell.q &&
                    army.r === cell.r,
                  )
                  if (token) {
                    selection.setSelectedToken(token.id)
                    return
                  }
                  if (selection.selectedToken) orders.plan(selection.selectedToken, cell)
                }
              : stage === "armies" && selection.selectedToken && !session.busy
                ? (cell) => {
                    if (selection.skipClick.current) return
                    void prep.placePiece(cell)
                  }
                : stage === "fort"
                  ? (cell) => { void prep.placeFort(cell) }
                  : stage === "roads" && campaign.roads && !campaign.roads.ready
                    ? (cell) => prep.queueRoad(cell)
                    : undefined
          }
        />
        {locator.length > 0 ? (
          <ul className="piece-rail" aria-label={t("piecesRail")}>
            {locator.map((token) => (
              <li key={token.id}>
                <button
                  type="button"
                  className={selection.spotlightId === token.id ? "is-selected" : undefined}
                  onClick={() => {
                    selection.setSpotlightId(token.id)
                    selection.setFocusSpot((current) => ({
                      q: token.q,
                      r: token.r,
                      n: (current?.n ?? 0) + 1,
                    }))
                  }}
                >
                  <span className="piece-rail-dot" style={{ background: token.color }} aria-hidden="true" />
                  <span>{token.label}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <CampaignDock
        campaign={campaign}
        view={view}
        filmPlaying={film.playing}
        canReplay={film.canReplay}
        onReplay={film.replay}
        ordering={orders.ordering}
        locking={orders.locking}
        busy={session.busy}
        onSaveFort={() => { void prep.saveFort() }}
        onFinishRoads={() => { void prep.finishRoadStep() }}
        onLock={() => { void orders.lockTurn() }}
      />
      {selection.sheetArmy ? (
        <ArmyModal
          campaign={campaign}
          armyId={selection.sheetArmy}
          busy={session.busy}
          onClose={() => selection.setSheetArmy(null)}
          onSave={async (action) => {
            session.setBusy(true)
            try {
              session.accept(await action())
              if (session.mounted.current) session.setErrors({})
            } catch (error: unknown) {
              if (session.mounted.current) session.setErrors(presentError(error, "identitySaveFailed"))
              throw error
            } finally {
              if (session.mounted.current) session.setBusy(false)
            }
          }}
        />
      ) : null}
    </section>
  )
}
