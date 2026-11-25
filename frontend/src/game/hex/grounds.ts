import type { MessageKey } from "../../i18n/catalog"

export const GROUND_LABEL: Record<string, MessageKey> = {
  llanura: "groundPlain",
  colina: "groundHill",
  bosque: "groundForest",
  bosque_profundo: "groundDeepForest",
  montana: "groundMountain",
  montana_rocosa: "groundRocky",
  desierto: "groundDesert",
  tundra: "groundTundra",
  orilla: "groundBank",
  rio: "groundRiver",
  pantano: "groundSwamp",
  lago: "groundLake",
  playa: "groundBeach",
  acantilado: "groundCliff",
  mina: "groundMine",
  campo: "groundField",
}

const WATER = new Set(["rio", "lago", "playa", "orilla", "pantano"])

export function isWater(ground: string): boolean {
  return WATER.has(ground)
}
