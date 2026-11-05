import json
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Zone


def haversine_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius_meters = 6_371_000
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_meters * math.asin(math.sqrt(value))


def _point_on_segment(
    longitude: float,
    latitude: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    tolerance: float = 1e-9,
) -> bool:
    cross_product = (x2 - x1) * (latitude - y1) - (y2 - y1) * (longitude - x1)
    if abs(cross_product) > tolerance:
        return False
    min_x, max_x = sorted((x1, x2))
    min_y, max_y = sorted((y1, y2))
    return (
        min_x - tolerance <= longitude <= max_x + tolerance
        and min_y - tolerance <= latitude <= max_y + tolerance
    )


def _ring_has_boundary_point(
    longitude: float, latitude: float, ring: list[list[float]]
) -> bool:
    if len(ring) < 3:
        return False
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][:2]
        x2, y2 = ring[index + 1][:2]
        if _point_on_segment(longitude, latitude, x1, y1, x2, y2):
            return True
    return False


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    if len(ring) < 3:
        return False
    if _ring_has_boundary_point(longitude, latitude, ring):
        return True
    previous = ring[-1]
    inside = False
    for current in ring:
        x1, y1 = previous[:2]
        x2, y2 = current[:2]
        x1, y1, x2, y2 = (float(x1), float(y1), float(x2), float(y2))
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            intersection_x = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection_x:
                inside = not inside
        previous = current
    return inside


def _sqlite_covers_geometry(geometry: dict, latitude: float, longitude: float) -> bool:
    if not geometry or not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return False

    if geometry_type == "MultiPolygon":
        for polygon in coordinates:
            if _sqlite_covers_geometry(
                {"type": "Polygon", "coordinates": polygon}, latitude, longitude
            ):
                return True
        return False

    if geometry_type != "Polygon":
        return False

    rings = coordinates
    outer_ring = rings[0]
    if not isinstance(outer_ring, list) or len(outer_ring) < 3:
        return False

    if _ring_has_boundary_point(longitude, latitude, outer_ring):
        return True
    if not _point_in_ring(longitude, latitude, outer_ring):
        return False

    for hole in rings[1:]:
        if _ring_has_boundary_point(longitude, latitude, hole):
            return True
        if _point_in_ring(longitude, latitude, hole):
            return False
    return True


def _sqlite_covers(zone: Zone, latitude: float, longitude: float) -> bool:
    try:
        geometry = json.loads(zone.boundary_geojson)
    except (TypeError, ValueError):
        return False
    return _sqlite_covers_geometry(geometry, latitude, longitude)


def point_is_in_enabled_zone(
    db: Session,
    latitude: float,
    longitude: float,
    zone_id: Any | None = None,
) -> bool:
    return _point_in_zone(db, latitude, longitude, zone_id, require_enabled=True)


def point_is_in_zone(
    db: Session,
    latitude: float,
    longitude: float,
    zone_id: Any | None = None,
) -> bool:
    return _point_in_zone(db, latitude, longitude, zone_id, require_enabled=False)


def _point_in_zone(
    db: Session,
    latitude: float,
    longitude: float,
    zone_id: Any | None,
    *,
    require_enabled: bool,
) -> bool:
    if db.bind.dialect.name == "postgresql":
        parameters: dict[str, Any] = {"latitude": latitude, "longitude": longitude}
        conditions = ["enabled"] if require_enabled else []
        if zone_id is not None:
            conditions.append("id = :zone_id")
            parameters["zone_id"] = zone_id
        where_clause = f"{' AND '.join(conditions)} AND " if conditions else ""
        return bool(
            db.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM zones WHERE "
                    f"{where_clause}"
                    "ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(boundary_geojson), 4326), "
                    "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)))"
                ),
                parameters,
            ).scalar_one()
        )
    zones = db.query(Zone)
    if require_enabled:
        zones = zones.filter(Zone.enabled.is_(True))
    if zone_id is not None:
        zones = zones.filter(Zone.id == zone_id)
    return any(_sqlite_covers(zone, latitude, longitude) for zone in zones)


def nearby_rows(
    db: Session,
    latitude: float,
    longitude: float,
    radius_meters: int,
    now,
    limit: int = 100,
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
                "WHERE s.state = 'available' AND s.expires_at > :now "
                "AND ST_DWithin("
                "ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography, "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography, "
                ":radius_meters) "
                "AND ST_Distance("
                "ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)::geography, "
                "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography"
                ") <= s.visibility_radius_meters "
                "ORDER BY distance_meters, s.id LIMIT :limit"
            ),
            {
                "latitude": latitude,
                "longitude": longitude,
                "radius_meters": radius_meters,
                "now": now,
                "limit": limit,
            },
        )
        return [dict(row._mapping) for row in rows]

    from .models import Collectible, SpawnInstance

    spawns = (
        db.query(SpawnInstance, Collectible)
        .join(Collectible, Collectible.id == SpawnInstance.collectible_id)
        .filter(
            SpawnInstance.state == "available",
            SpawnInstance.expires_at > now,
            Collectible.enabled.is_(True),
        )
        .all()
    )
    results = []
    for spawn, collectible in spawns:
        distance = haversine_meters(
            latitude, longitude, spawn.latitude, spawn.longitude
        )
        if distance <= min(radius_meters, spawn.visibility_radius_meters):
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
    return sorted(results, key=lambda row: row["distance_meters"])[:limit]
