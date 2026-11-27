import { diskCells } from "../src/game/hex/disk"
import type { Page, Route } from "@playwright/test"

const player = { email: "ada@example.com", alias: "Ada" }

const identity = {
  factions: [{ id: "empire", legacy: false }],
  colors: [
    { id: "garnet", value: "#7a1f2b" },
    { id: "copper", value: "#b87333" },
    { id: "ochre", value: "#c7a008" },
    { id: "lime", value: "#8fbf3f" },
  ],
}

function campaignDocument() {
  const you = {
    player_id: "ada",
    alias: "Ada",
    role: "owner",
    status: "active",
    faction: "",
    color: "#7a1f2b",
    ready: true,
    orders_locked: false,
  }
  return {
    id: "mesa",
    name: "La mesa",
    description: "",
    phase: "orders",
    revision: 1,
    turn: 1,
    rules: {
      seats: 2,
      armies: 1,
      movement: 3,
      map_size: 19,
      visibility: "home",
      victory: "armies",
      hold_turns: 3,
      placement: "app",
      order_days: 7,
      battle_days: 7,
      missed_turns: 2,
      roster_required: false,
    },
    members: [you],
    joined: true,
    you,
    hexes: diskCells(19).map((cell) => ({
      ...cell,
      known: true,
      ground: "llanura",
      road: false,
      bridge: false,
      owner_id: null,
      sight: true,
    })),
    fortresses: [],
    armies: [],
    battles: [],
    orders: {},
    playback: { turn: 0, moves: [] },
    chronicle: [],
    road_ready: [],
    lobby_ready: [],
    naming: false,
    fort_open: false,
    prep_done: [],
    prep: null,
    roads: null,
  }
}

const summary = [{
  id: "mesa",
  name: "La mesa",
  role: "owner",
  status: "active",
  phase: "orders",
}]

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}

/** Answer /api in the browser so the walk does not need the server. */
export async function installApi(page: Page): Promise<void> {
  let signedIn = false
  const campaign = campaignDocument()
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const path = new URL(route.request().url()).pathname
    const method = route.request().method()
    if (path === "/api/events") {
      await route.abort()
      return
    }
    if (path === "/api/session" && method === "POST") {
      signedIn = true
      await json(route, 200, player)
      return
    }
    if (path === "/api/session" && method === "GET") {
      await json(route, signedIn ? 200 : 401, signedIn ? player : {})
      return
    }
    if (path === "/api/notifications") {
      await json(route, 200, [])
      return
    }
    if (path === "/api/campaigns" && method === "GET") {
      await json(route, 200, summary)
      return
    }
    if (path === "/api/campaigns/mesa/pulse") {
      await json(route, 200, { revision: 1, phase: "orders" })
      return
    }
    if (path === "/api/campaigns/mesa") {
      await json(route, 200, campaign)
      return
    }
    if (path === "/api/campaign-identity") {
      await json(route, 200, identity)
      return
    }
    await json(route, 404, {})
  })
}
