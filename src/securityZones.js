const SECURITY_STATUSES = new Set([
  "safe",
  "caution",
  "restricted",
  "unknown",
]);

export function validateSecurityZoneCollection(collection) {
  if (
    collection?.type !== "FeatureCollection" ||
    !Array.isArray(collection.features)
  ) {
    throw new Error("La API devolvió datos de seguridad no válidos.");
  }

  for (const feature of collection.features) {
    if (
      feature?.type !== "Feature" ||
      !["Polygon", "MultiPolygon"].includes(feature.geometry?.type) ||
      !Array.isArray(feature.geometry.coordinates) ||
      feature.geometry.coordinates.length === 0 ||
      !SECURITY_STATUSES.has(feature.properties?.security_status) ||
      typeof feature.properties?.allows_play !== "boolean"
    ) {
      throw new Error("La API devolvió una zona de seguridad no válida.");
    }
  }

  return collection;
}

export function securityZoneDescription(status) {
  return {
    safe: {
      label: "Zona segura",
      message: "Zona segura. Puedes explorar y recoger objetos.",
    },
    caution: {
      label: "Precaución",
      message: "Precaución. Esta ubicación tiene restricciones de seguridad.",
    },
    restricted: {
      label: "Zona restringida",
      message: "Zona restringida. No puedes jugar ni recoger objetos aquí.",
    },
    unknown: {
      label: "Sin verificar",
      message: "Ubicación sin verificar. El juego no está habilitado aquí.",
    },
  }[status];
}
