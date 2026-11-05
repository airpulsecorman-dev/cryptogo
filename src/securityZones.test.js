import {
  securityZoneDescription,
  validateSecurityZoneCollection,
} from "./securityZones";

const geometry = {
  type: "Polygon",
  coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]],
};

test.each([
  ["safe", true],
  ["caution", false],
  ["restricted", false],
  ["unknown", false],
])("preserves the backend %s classification and polygon", (status, allowsPlay) => {
  const collection = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry,
        properties: { security_status: status, allows_play: allowsPlay },
      },
    ],
  };

  expect(validateSecurityZoneCollection(collection)).toBe(collection);
  expect(collection.features[0].geometry).toBe(geometry);
  expect(collection.features[0].properties).toEqual({
    security_status: status,
    allows_play: allowsPlay,
  });
  expect(securityZoneDescription(status).message).toBeTruthy();
});

test("rejects missing or unrecognized classifications instead of inventing a status", () => {
  expect(() =>
    validateSecurityZoneCollection({
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry,
          properties: { security_status: "enabled", allows_play: true },
        },
      ],
    }),
  ).toThrow(/zona de seguridad no válida/i);
});

test("keeps an empty response empty", () => {
  const empty = { type: "FeatureCollection", features: [] };
  expect(validateSecurityZoneCollection(empty)).toBe(empty);
});
