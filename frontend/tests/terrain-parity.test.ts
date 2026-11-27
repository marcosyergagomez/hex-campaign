import { spawnSync } from "node:child_process"
import { delimiter, dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

import { exitCostOf, gazeReach, moveBudget, roadRefund } from "../src/game/hex/orders"
import { isImpassable } from "../src/game/hex/terrainContract"

type Row = {
  ground: string
  passable: boolean
  gaze: number
  refund: number
  exit?: number
  road?: number
  road_refund?: number
  bridge?: number
}

type Domain = {
  rows: Row[]
  impassable: string[]
  unknown_gaze: number
  explorer_move_bonus: number
  explorer_gaze_bonus: number
  army_budget: number
  explorer_budget: number
  explorer_gaze_hill: number
  army_gaze_plain: number
}

function domainTable(): Domain {
  const here = dirname(fileURLToPath(import.meta.url))
  const root = join(here, "..", "..")
  const backendSrc = join(root, "backend", "src")
  const script = join(here, "domain_movement.py")
  const pythonPath = [backendSrc, process.env.PYTHONPATH].filter(Boolean).join(delimiter)
  const env = { ...process.env, PYTHONPATH: pythonPath }
  const commands = process.platform === "win32"
    ? [["py", ["-3", script]], ["python", [script]]]
    : [["python3", [script]], ["python", [script]]]
  const errors: string[] = []
  for (const [command, args] of commands) {
    const result = spawnSync(command, args, { cwd: root, env, encoding: "utf8" })
    if (result.status === 0 && result.stdout.trim()) {
      return JSON.parse(result.stdout) as Domain
    }
    errors.push(`${command}: ${result.error?.message ?? result.stderr}`)
  }
  throw new Error(errors.join("\n"))
}

describe("movement costs match the campaign domain", () => {
  const domain = domainTable()

  it("charges the same exit, road, bridge, gaze and refund as the server", () => {
    expect(domain.rows.length).toBeGreaterThan(0)
    for (const row of domain.rows) {
      expect(isImpassable(row.ground)).toBe(!row.passable)
      expect(gazeReach(row.ground, false)).toBe(row.gaze)
      expect(roadRefund({ known: true, ground: row.ground, road: false, bridge: false })).toBe(row.refund)
      if (!row.passable) continue
      const plain = { known: true, ground: row.ground, road: false, bridge: false }
      expect(exitCostOf(plain)).toBe(row.exit)
      expect(exitCostOf({ ...plain, road: true })).toBe(row.road)
      expect(roadRefund({ ...plain, road: true })).toBe(row.road_refund)
      if (row.bridge !== undefined) {
        expect(exitCostOf({ ...plain, bridge: true })).toBe(row.bridge)
      }
    }
    expect(domain.impassable.every((ground) => isImpassable(ground))).toBe(true)
    expect(gazeReach(undefined, false)).toBe(domain.unknown_gaze)
    expect(exitCostOf({ known: false })).toBe(1)
    expect(moveBudget(3, "army")).toBe(domain.army_budget)
    expect(moveBudget(3, "explorer")).toBe(domain.explorer_budget)
    expect(gazeReach("colina", true)).toBe(domain.explorer_gaze_hill)
    expect(gazeReach("llanura", false)).toBe(domain.army_gaze_plain)
    expect(domain.explorer_budget - domain.army_budget).toBe(domain.explorer_move_bonus)
    expect(domain.explorer_gaze_hill - gazeReach("colina", false)).toBe(domain.explorer_gaze_bonus)
  })
})
