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

export const GROUND_ART: Record<string, string> = {
  llanura: "/terrain/llanura.jpg",
  colina: "/terrain/colina.jpg",
  bosque: "/terrain/bosque.jpg",
  bosque_profundo: "/terrain/bosque-profundo.jpg",
  montana: "/terrain/montana.jpg",
  montana_rocosa: "/terrain/montana-rocosa.jpg",
  desierto: "/terrain/desierto.jpg",
  tundra: "/terrain/tundra.jpg",
  orilla: "/terrain/orilla.jpg",
  rio: "/terrain/rio.jpg",
  pantano: "/terrain/pantano.jpg",
  lago: "/terrain/lago.jpg",
  playa: "/terrain/playa.jpg",
  acantilado: "/terrain/acantilado.jpg",
  mina: "/terrain/mina.jpg",
  campo: "/terrain/campo.jpg",
}

const WATER = new Set(["rio", "lago", "playa", "orilla", "pantano"])

export function isWater(ground: string): boolean {
  return WATER.has(ground)
}
