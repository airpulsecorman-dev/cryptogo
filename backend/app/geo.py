import json
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Zone


def haversine_meters(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    earth_radius_meters = 6_371_000
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * earth_radius_meters * math.asin(math.sqrt(value))


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[:2]
        x2, y2 = current[:2]
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses and longitude < (x2 - x1) * (latitude - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def _sqlite_covers(zone: Zone, latitude: float, longitude: float) -> bool:
    geometry = json.loads(zone.boundary_geojson)
    if geometry.get("type") != "Polygon" or not geometry.get("coordinates"):
        return False
    rings = geometry["coordinates"]
    return _point_in_ring(longitude, latitude, rings[0]) and not any(
        _point_in_ring(longitude, latitude, hole) for hole in rings[1:]
    )


def point_is_in_enabled_zone(
    db: Session,
    latitude: float,
    longitude: float,
    zone_id: Any | None = None,
) -> bool:
    if db.bind.dialect.name == "postgresql":
        parameters: dict[str, Any] = {"latitude": latitude, "longitude": longitude}
        zone_filter = ""
        if zone_id is not None:
            zone_filter = "AND id = :zone_id"
            parameters["zone_id"] = zone_id
        return bool(
            db.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM zones WHERE enabled "
                    f"{zone_filter} "
                    "AND ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(boundary_geojson), 4326), "
                    "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)))"
                ),
                parameters,
            ).scalar_one()
        )
    zones = db.query(Zone).filter(Zone.enabled.is_(True))
    if zone_id is not None:
        zones = zones.filter(Zone.id == zone_id)
    return any(_sqlite_covers(zone, latitude, longitude) for zone in zones)


def nearby_rows(
    db: Session,
    latitude: float,
    longitude: float,
    radius_meters: int,
    now,
) -> list[dict]:
    if db.bind.dialect.name == "postgresql":
        rows = db.execute(
            text(
                "SELECT s.id, s.latitude, s.longitude, s.collection_radius_meters, s.expires_at, "
                "c.ticker, c.name, c.symbol, c.rarity, "
                "ST_Distance("
                "ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography, "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography"
                ") AS distance_meters "
                "FROM spawn_instances s "
                "JOIN collectibles c ON c.id = s.collectible_id AND c.enabled "
                "JOIN zones z ON z.id = s.zone_id AND z.enabled "
                "WHERE s.state = 'available' AND s.expires_at > :now "
                "AND ST_DWithin("
                "ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography, "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography, "
                ":radius_meters) "
                "AND ST_Distance("
                "ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography, "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography"
                ") <= s.visibility_radius_meters "
                "AND ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(z.boundary_geojson), 4326), "
                "ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)) "
                "AND ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(z.boundary_geojson), 4326), "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)) "
                "ORDER BY distance_meters, s.id"
            ),
            {
                "latitude": latitude,
                "longitude": longitude,
                "radius_meters": radius_meters,
                "now": now,
            },
        )
        return [dict(row._mapping) for row in rows]

    from .models import Collectible, SpawnInstance

    spawns = (
        db.query(SpawnInstance, Collectible, Zone)
        .join(Collectible, Collectible.id == SpawnInstance.collectible_id)
        .join(Zone, Zone.id == SpawnInstance.zone_id)
        .filter(
            SpawnInstance.state == "available",
            SpawnInstance.expires_at > now,
            Collectible.enabled.is_(True),
            Zone.enabled.is_(True),
        )
        .all()
    )
    results = []
    for spawn, collectible, zone in spawns:
        distance = haversine_meters(latitude, longitude, spawn.latitude, spawn.longitude)
        if (
            distance <= min(radius_meters, spawn.visibility_radius_meters)
            and _sqlite_covers(zone, spawn.latitude, spawn.longitude)
            and _sqlite_covers(zone, latitude, longitude)
        ):
            results.append(
                {
                    "id": spawn.id,
                    "latitude": spawn.latitude,
                    "longitude": spawn.longitude,
                    "collection_radius_meters": spawn.collection_radius_meters,
                    "expires_at": spawn.expires_at,
                    "ticker": collectible.ticker,
                    "name": collectible.name,
                    "symbol": collectible.symbol,
                    "rarity": collectible.rarity,
                    "distance_meters": distance,
                }
            )
    return sorted(results, key=lambda row: row["distance_meters"])
