import { GROUND_LABEL } from "../game/hex/grounds"
import { ApiError, csrfHeaders, readInt, request } from "./http"
import { isMapSize, type MapCell, type MapSize } from "./campaignTypes"

export type SavedMap = {
  id: string
  name: string
  size: MapSize
  seats: number | null
  generated: boolean
}

export type SavedMapDetail = SavedMap & {
  cells: MapCell[]
  anchors: { q: number; r: number }[]
}

export type MapScale = {
  key: "small" | "medium" | "large"
  size: MapSize
  seats: number[]
  recommend: number
  home_size: number
}

export async function listMapScales(): Promise<MapScale[]> {
  const data = await request("/api/map-scales", { method: "GET" })
  if (!Array.isArray(data) || data.length !== 3) throw new ApiError(200, {})
  const scales = data.map((value): MapScale => {
    if (!value || typeof value !== "object") throw new ApiError(200, {})
    const record = value as Record<string, unknown>
    if (
      (record.key !== "small" && record.key !== "medium" && record.key !== "large") ||
      !isMapSize(record.size) || !Array.isArray(record.seats) ||
      record.seats.length < 1 || record.seats.length > 3
    ) throw new ApiError(200, {})
    const seats = record.seats.map((seat: unknown) => {
      const parsed = readInt(seat, 2, 4)
      if (parsed === null) throw new ApiError(200, {})
      return parsed
    })
    const recommend = readInt(record.recommend, 2, 4)
    const home = readInt(record.home_size, 7, Math.floor(record.size / 2) - 1)
    if (recommend === null || home === null || !seats.includes(recommend)) {
      throw new ApiError(200, {})
    }
    return { key: record.key, size: record.size, seats, recommend, home_size: home }
  })
  if (new Set(scales.map(scale => scale.key)).size !== 3 ||
    new Set(scales.map(scale => scale.size)).size !== 3) throw new ApiError(200, {})
  return scales
}

export async function listMaps(): Promise<SavedMap[]> {
  const data = await request("/api/maps", { method: "GET" })
  if (!Array.isArray(data) || data.length > 100) {
    throw new ApiError(200, {})
  }
  return data.map(readSavedMap)
}

export async function generateMap(name: string, size: MapSize, seats: number): Promise<SavedMap> {
  return readSavedMap(
    await request("/api/maps", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name, size, seats }),
    }),
  )
}

export async function deleteMap(id: string): Promise<void> {
  await request(`/api/maps/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { ...csrfHeaders() },
  })
}

export async function saveDrawnMap(
  name: string,
  size: MapSize,
  cells: MapCell[],
  anchors: { q: number; r: number }[],
): Promise<SavedMap> {
  return readSavedMap(
    await request("/api/maps", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name, size, cells, anchors }),
    }),
  )
}

export async function updateDrawnMap(
  id: string,
  name: string,
  size: MapSize,
  cells: MapCell[],
  anchors: { q: number; r: number }[],
): Promise<SavedMap> {
  return readSavedMap(
    await request(`/api/maps/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name, size, cells, anchors }),
    }),
  )
}

export async function copyMapForEdit(id: string, name?: string): Promise<SavedMap> {
  return readSavedMap(
    await request(`/api/maps/${encodeURIComponent(id)}/copy`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ name: name ?? null }),
    }),
  )
}

export async function getMap(id: string): Promise<SavedMapDetail> {
  const data = await request(`/api/maps/${encodeURIComponent(id)}`, { method: "GET" })
  const summary = readSavedMap(data)
  if (!data || typeof data !== "object") {
    throw new ApiError(200, {})
  }
  const record = data as Record<string, unknown>
  if (!Array.isArray(record.cells) || !Array.isArray(record.anchors)) {
    throw new ApiError(200, {})
  }
  const cells: MapCell[] = []
  for (const item of record.cells) {
    if (!item || typeof item !== "object") {
      throw new ApiError(200, {})
    }
    const cell = item as Record<string, unknown>
    const q = readInt(cell.q, -64, 64)
    const r = readInt(cell.r, -64, 64)
    if (q === null || r === null || typeof cell.ground !== "string") {
      throw new ApiError(200, {})
    }
    if (!Object.hasOwn(GROUND_LABEL, cell.ground)) {
      throw new ApiError(200, {})
    }
    cells.push({
      q,
      r,
      ground: cell.ground,
      road: cell.road === true,
      bridge: cell.bridge === true,
    })
  }
  const anchors: { q: number; r: number }[] = []
  for (const item of record.anchors) {
    if (!item || typeof item !== "object") {
      throw new ApiError(200, {})
    }
    const spot = item as Record<string, unknown>
    const q = readInt(spot.q, -64, 64)
    const r = readInt(spot.r, -64, 64)
    if (q === null || r === null) {
      throw new ApiError(200, {})
    }
    anchors.push({ q, r })
  }
  return { ...summary, cells, anchors }
}

function readSavedMap(value: unknown): SavedMap {
  if (!value || typeof value !== "object") {
    throw new ApiError(200, {})
  }
  const record = value as Record<string, unknown>
  if (
    typeof record.id !== "string" ||
    typeof record.name !== "string" ||
    !isMapSize(record.size) ||
    typeof record.generated !== "boolean"
  ) {
    throw new ApiError(200, {})
  }
  const seats = record.seats === null ? null : readInt(record.seats, 2, 4)
  if (record.seats !== null && seats === null) {
    throw new ApiError(200, {})
  }
  return {
    id: record.id,
    name: record.name,
    size: record.size,
    seats,
    generated: record.generated,
  }
}
