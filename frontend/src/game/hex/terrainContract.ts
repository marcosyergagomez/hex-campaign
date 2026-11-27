import contract from "../../../../shared/terrain.json"

const impassable = new Set<string>(contract.impassable)
const openGrounds = new Set<string>(contract.open_grounds)
const exitCosts: Record<string, number> = { ...contract.exit }
const gaze: Record<string, number> = { ...contract.gaze }

export const EXPLORER_MOVE_BONUS = contract.explorer_move_bonus
export const EXPLORER_GAZE_BONUS = contract.explorer_gaze_bonus

export function isImpassable(ground: string | undefined): boolean {
  return ground !== undefined && impassable.has(ground)
}

/** Points to leave a known hex. A road or a bridge makes that exit cost 1. */
export function exitCostOfGround(ground: string | undefined, road: boolean, bridge: boolean): number {
  if (road || bridge) return 1
  if (!ground) return 1
  return exitCosts[ground] ?? 1
}

export function gazeOf(ground: string | undefined): number {
  if (!ground) return contract.base_gaze
  return gaze[ground] ?? contract.base_gaze
}

/** A road on rough ground returns one point after the exit is paid. */
export function roadRefundOf(ground: string | undefined, road: boolean): number {
  if (!road || !ground || openGrounds.has(ground)) return 0
  return 1
}
