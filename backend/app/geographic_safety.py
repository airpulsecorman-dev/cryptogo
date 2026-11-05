import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .geo import _sqlite_covers_geometry, haversine_meters
from .models import (
    GeographicSecurityAuditLog,
    GeographicSecurityEvidence,
    utcnow,
)

POLICY_VERSION = "geo-safety-v1"
SAFE_CONFIDENCE_THRESHOLD = 0.9
MAX_LOCATION_UNCERTAINTY_METERS = 10_000
_PRECEDENCE = {"safe": 0, "caution": 1, "unknown": 2, "restricted": 3}
_ALLOWED_STATUSES = frozenset(_PRECEDENCE)
_EVIDENCE_LOCK_KEY = 72_059_763_481


@dataclass(frozen=True)
class GeographicSafetyDecision:
    status: str
    reason: str
    sources: tuple[dict[str, str | None], ...]
    confidence: float | None
    rule_applied: str
    policy_version: str
    valid_until: datetime | None
    allows_generation: bool
    allows_query: bool
    allows_collection: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "sources": list(self.sources),
            "confidence": self.confidence,
            "rule_applied": self.rule_applied,
            "policy_version": self.policy_version,
            "valid_until": self.valid_until,
            "allows_generation": self.allows_generation,
            "allows_query": self.allows_query,
            "allows_collection": self.allows_collection,
        }


def _validate_location(latitude: float, longitude: float, radius_meters: float) -> None:
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not math.isfinite(radius_meters)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
        or not 0 <= radius_meters <= MAX_LOCATION_UNCERTAINTY_METERS
    ):
        raise ValueError("Invalid geographic safety query location or uncertainty.")


def _segments_intersect(a, b, c, d) -> bool:
    def orientation(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p, q, r):
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    first = orientation(a, b, c)
    second = orientation(a, b, d)
    third = orientation(c, d, a)
    fourth = orientation(c, d, b)
    if first == 0 and on_segment(a, c, b):
        return True
    if second == 0 and on_segment(a, d, b):
        return True
    if third == 0 and on_segment(c, a, d):
        return True
    if fourth == 0 and on_segment(c, b, d):
        return True
    return (first > 0) != (second > 0) and (third > 0) != (fourth > 0)


def _ring_is_valid(ring: Any) -> bool:
    if not isinstance(ring, list) or len(ring) < 4:
        return False
    points = []
    for coordinate in ring:
        if (
            not isinstance(coordinate, list)
            or len(coordinate) < 2
            or not isinstance(coordinate[0], (int, float))
            or not isinstance(coordinate[1], (int, float))
            or not math.isfinite(coordinate[0])
            or not math.isfinite(coordinate[1])
            or not -180 <= coordinate[0] <= 180
            or not -90 <= coordinate[1] <= 90
        ):
            return False
        points.append((float(coordinate[0]), float(coordinate[1])))
    if points[0] != points[-1]:
        return False
    if sum(
        start[0] * end[1] - end[0] * start[1]
        for start, end in zip(points, points[1:])
    ) == 0:
        return False
    edges = list(zip(points, points[1:]))
    for first_index, (a, b) in enumerate(edges):
        for second_index in range(first_index + 1, len(edges)):
            if second_index in {first_index, first_index + 1}:
                continue
            if first_index == 0 and second_index == len(edges) - 1:
                continue
            c, d = edges[second_index]
            if _segments_intersect(a, b, c, d):
                return False
    return True


def _geometry_is_valid(geometry: Any) -> bool:
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        return False
    if not isinstance(polygons, list) or not polygons:
        return False
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            return False
        if not all(_ring_is_valid(ring) for ring in polygon):
            return False
        outer = polygon[0]
        for hole_index, hole in enumerate(polygon[1:]):
            if not _sqlite_covers_geometry(
                {"type": "Polygon", "coordinates": [outer]}, hole[0][1], hole[0][0]
            ):
                return False
            if _rings_intersect(outer, hole):
                return False
            for other_hole in polygon[1 : hole_index + 1]:
                if (
                    _rings_intersect(other_hole, hole)
                    or _sqlite_covers_geometry(
                        {"type": "Polygon", "coordinates": [other_hole]},
                        hole[0][1],
                        hole[0][0],
                    )
                    or _sqlite_covers_geometry(
                        {"type": "Polygon", "coordinates": [hole]},
                        other_hole[0][1],
                        other_hole[0][0],
                    )
                ):
                    return False
    return True


def _rings_intersect(first_ring: list, second_ring: list) -> bool:
    return any(
        _segments_intersect(
            (first_start[0], first_start[1]),
            (first_end[0], first_end[1]),
            (second_start[0], second_start[1]),
            (second_end[0], second_end[1]),
        )
        for first_start, first_end in zip(first_ring, first_ring[1:])
        for second_start, second_end in zip(second_ring, second_ring[1:])
    )


def _point_to_segment_meters(
    latitude: float,
    longitude: float,
    start: list[float],
    end: list[float],
) -> float:
    reference_latitude = math.radians(latitude)
    scale_x = 111_320 * max(abs(math.cos(reference_latitude)), 1e-8)
    scale_y = 110_574
    x0 = (start[0] - longitude) * scale_x
    y0 = (start[1] - latitude) * scale_y
    x1 = (end[0] - longitude) * scale_x
    y1 = (end[1] - latitude) * scale_y
    delta_x, delta_y = x1 - x0, y1 - y0
    length_squared = delta_x * delta_x + delta_y * delta_y
    if length_squared == 0:
        return math.hypot(x0, y0)
    fraction = min(
        1,
        max(0, -(x0 * delta_x + y0 * delta_y) / length_squared),
    )
    return math.hypot(x0 + fraction * delta_x, y0 + fraction * delta_y)


def _geometry_intersects_uncertainty(
    geometry: dict, latitude: float, longitude: float, radius_meters: float
) -> bool:
    if _sqlite_covers_geometry(geometry, latitude, longitude):
        return True
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    for polygon in polygons:
        for ring in polygon:
            for start, end in zip(ring, ring[1:]):
                if (
                    _point_to_segment_meters(latitude, longitude, start, end)
                    <= radius_meters
                ):
                    return True
    return False


def _time_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _record_data(record: GeographicSecurityEvidence) -> dict[str, Any]:
    return {
        "id": record.id,
        "security_status": record.security_status,
        "place_type": record.place_type,
        "source_name": record.source_name,
        "source_identifier": record.source_identifier,
        "license_terms": record.license_terms,
        "access_status": record.access_status,
        "imported_at": record.imported_at,
        "verified_at": record.verified_at,
        "expires_at": record.expires_at,
        "confidence": record.confidence,
        "validation_status": record.validation_status,
        "rule_applied": record.rule_applied,
        "policy_version": record.policy_version,
        "reason": record.reason,
        "geometry_geojson": record.geometry_geojson,
        "geometry_valid": None,
        "intersects": None,
    }


def _fetch_candidates(
    db: Session,
    locations: list[tuple[float, float, float]],
) -> dict[int, list[dict[str, Any]]]:
    candidates: dict[int, list[dict[str, Any]]] = {index: [] for index in range(len(locations))}
    if not locations:
        return candidates

    if db.bind.dialect.name == "postgresql":
        values = []
        parameters: dict[str, Any] = {}
        for index, (latitude, longitude, radius) in enumerate(locations):
            values.append(
                f"(:index_{index}, :latitude_{index}, :longitude_{index}, :radius_{index})"
            )
            parameters.update(
                {
                    f"index_{index}": index,
                    f"latitude_{index}": latitude,
                    f"longitude_{index}": longitude,
                    f"radius_{index}": radius,
                }
            )
        query = text(
            "WITH locations(location_id, latitude, longitude, radius_meters) AS (VALUES "
            + ", ".join(values)
            + ") "
            "SELECT locations.location_id, evidence.id, evidence.security_status, "
            "evidence.place_type, evidence.source_name, evidence.source_identifier, "
            "evidence.license_terms, evidence.access_status, evidence.imported_at, "
            "evidence.verified_at, evidence.expires_at, evidence.confidence, "
            "evidence.validation_status, evidence.rule_applied, evidence.policy_version, "
            "evidence.reason, "
            "CASE WHEN evidence.geom IS NULL THEN false ELSE "
            "ST_IsValid(evidence.geom) AND "
            "ST_GeometryType(evidence.geom) IN ('ST_Polygon', 'ST_MultiPolygon') END "
            "AS geometry_valid, "
            "CASE WHEN evidence.geom IS NULL THEN true "
            "WHEN NOT ST_IsValid(evidence.geom) OR "
            "ST_GeometryType(evidence.geom) NOT IN ('ST_Polygon', 'ST_MultiPolygon') THEN true "
            "ELSE ST_DWithin(evidence.geom::geography, "
            "ST_SetSRID(ST_MakePoint(locations.longitude, locations.latitude), 4326)::geography, "
            "locations.radius_meters) END AS intersects "
            "FROM locations JOIN geographic_security_evidence AS evidence ON "
            "evidence.geom IS NULL OR evidence.geom && ST_Expand("
            "ST_SetSRID(ST_MakePoint(locations.longitude, locations.latitude), 4326), "
            "locations.radius_meters / 110574.0, "
            "LEAST(180.0, locations.radius_meters / "
            "(111320.0 * GREATEST(ABS(COS(RADIANS(locations.latitude))), 0.00000001))))"
        )
        rows = db.execute(query, parameters)
        for row in rows:
            item = dict(row._mapping)
            if item.pop("intersects"):
                candidates[item.pop("location_id")].append(item)
        return candidates

    records = db.scalars(select(GeographicSecurityEvidence)).all()
    parsed_records = []
    for record in records:
        item = _record_data(record)
        try:
            geometry = json.loads(record.geometry_geojson or "")
        except (TypeError, ValueError):
            item["geometry_valid"] = False
            item["intersects"] = True
            item["invalid_geometry"] = True
            parsed_records.append((item, None))
            continue
        item["geometry_valid"] = _geometry_is_valid(geometry)
        item["invalid_geometry"] = not item["geometry_valid"]
        parsed_records.append((item, geometry))

    for index, (latitude, longitude, radius) in enumerate(locations):
        for item, geometry in parsed_records:
            intersects = geometry is None or (
                _geometry_intersects_uncertainty(geometry, latitude, longitude, radius)
                if item["geometry_valid"]
                else _geometry_bbox_intersects(
                    geometry, latitude, longitude, radius
                )
            )
            if intersects:
                candidates[index].append({**item, "intersects": True})
    return candidates


def _geometry_bbox_intersects(
    geometry: dict, latitude: float, longitude: float, radius_meters: float
) -> bool:
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not coordinates:
        return True
    points = []

    def collect(value):
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(coordinates)
    if not points:
        return True
    min_longitude = min(point[0] for point in points)
    max_longitude = max(point[0] for point in points)
    min_latitude = min(point[1] for point in points)
    max_latitude = max(point[1] for point in points)
    nearest_latitude = min(max(latitude, min_latitude), max_latitude)
    nearest_longitude = min(max(longitude, min_longitude), max_longitude)
    return (
        haversine_meters(latitude, longitude, nearest_latitude, nearest_longitude)
        <= radius_meters + 1
    )


def _evaluate_candidates(
    records: list[dict[str, Any]], now: datetime
) -> GeographicSafetyDecision:
    resolved = []
    for record in records:
        reason = record.get("reason") or ""
        status = record.get("security_status")
        rule = record.get("rule_applied")
        expiry = _time_utc(record.get("expires_at"))
        verified = _time_utc(record.get("verified_at"))
        imported = _time_utc(record.get("imported_at"))
        provenance_present = all(
            isinstance(record.get(field), str) and record[field].strip()
            for field in ("source_name", "source_identifier", "license_terms")
        )
        if (
            record.get("geometry_valid") is False
            or record.get("validation_status") != "verified"
            or not provenance_present
            or imported is None
            or imported > now
            or verified is None
            or expiry is None
            or expiry <= now
            or verified > now
            or record.get("policy_version") != POLICY_VERSION
            or status not in _ALLOWED_STATUSES
        ):
            status = "unknown"
            reason = (
                "Evidence is invalid, expired, unverified, lacks provenance, "
                "or uses an obsolete policy version."
            )
            rule = "evidence_invalid_or_stale"
        elif record.get("access_status") == "restricted":
            status = "restricted"
            reason = reason or "The verified evidence marks this area as restricted."
            rule = "restricted_access"
        elif status == "safe" and (
            not isinstance(record.get("confidence"), (int, float))
            or not math.isfinite(record["confidence"])
            or not SAFE_CONFIDENCE_THRESHOLD
            <= record["confidence"]
            <= 1
            or record.get("access_status") not in {"public", "authorized"}
        ):
            status = "unknown"
            reason = "Safe access and confidence requirements are not met."
            rule = "safe_requirements_not_met"
        resolved.append((status, record, reason or status, rule or f"evidence_{status}"))

    if not resolved:
        return GeographicSafetyDecision(
            status="unknown",
            reason="No current, verified geographic evidence covers this location.",
            sources=(),
            confidence=None,
            rule_applied="no_verified_evidence",
            policy_version=POLICY_VERSION,
            valid_until=None,
            allows_generation=False,
            allows_query=False,
            allows_collection=False,
        )

    winning_status = max(
        (status for status, _record, _reason, _rule in resolved),
        key=lambda status: _PRECEDENCE[status],
    )
    winning_records = [
        (record, reason, rule)
        for status, record, reason, rule in resolved
        if status == winning_status
    ]
    ordered_records = sorted(
        (record for record, _reason, _rule in winning_records),
        key=lambda record: str(record.get("id") or ""),
    )
    sources = tuple(
        {
            "name": record.get("source_name"),
            "identifier": record.get("source_identifier"),
        }
        for record in ordered_records
    )
    confidences = [
        record["confidence"]
        for record in ordered_records
        if isinstance(record.get("confidence"), (int, float))
    ]
    expiries = [
        expiry
        for record in ordered_records
        if (expiry := _time_utc(record.get("expires_at"))) is not None
    ]
    rules = sorted(
        {rule for _record, _reason, rule in winning_records}
    )
    reasons = sorted({reason for _record, reason, _rule in winning_records})
    allowed = winning_status == "safe"
    return GeographicSafetyDecision(
        status=winning_status,
        reason="; ".join(reasons),
        sources=sources,
        confidence=min(confidences) if confidences else None,
        rule_applied=",".join(rules),
        policy_version=POLICY_VERSION,
        valid_until=min(expiries) if expiries else None,
        allows_generation=allowed,
        allows_query=allowed,
        allows_collection=allowed,
    )


def classify_geographic_safety(
    db: Session,
    latitude: float,
    longitude: float,
    radius_meters: float = 0,
    *,
    now: datetime | None = None,
) -> GeographicSafetyDecision:
    return classify_geographic_safety_batch(
        db, [(latitude, longitude, radius_meters)], now=now
    )[0]


def classify_geographic_safety_batch(
    db: Session,
    locations: list[tuple[float, float, float]],
    *,
    now: datetime | None = None,
) -> list[GeographicSafetyDecision]:
    for latitude, longitude, radius_meters in locations:
        _validate_location(latitude, longitude, radius_meters)
    current_time = _time_utc(now or utcnow())
    if locations and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock_shared(:lock_key)"),
            {"lock_key": _EVIDENCE_LOCK_KEY},
        )
    candidate_rows = _fetch_candidates(db, locations)
    return [
        _evaluate_candidates(candidate_rows[index], current_time)
        for index in range(len(locations))
    ]


def persist_geographic_evidence(
    db: Session,
    evidence: GeographicSecurityEvidence,
    *,
    actor: str,
    action: str = "created",
    previous_value: dict[str, Any] | None = None,
) -> GeographicSecurityEvidence:
    if db.bind.dialect.name == "postgresql":
        # Serialize evidence edits with any in-flight spawn or collection decision.
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _EVIDENCE_LOCK_KEY},
        )
    db.add(evidence)
    db.flush()
    if db.bind.dialect.name == "postgresql" and evidence.geometry_geojson:
        try:
            json.loads(evidence.geometry_geojson)
        except (TypeError, ValueError):
            evidence.geom = None
        else:
            db.execute(
                text(
                    "UPDATE geographic_security_evidence "
                    "SET geom = ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326) "
                    "WHERE id = :evidence_id"
                ),
                {"geometry": evidence.geometry_geojson, "evidence_id": evidence.id},
            )
    new_value = {
        "security_status": evidence.security_status,
        "place_type": evidence.place_type,
        "source_name": evidence.source_name,
        "source_identifier": evidence.source_identifier,
        "license_terms": evidence.license_terms,
        "access_status": evidence.access_status,
        "confidence": evidence.confidence,
        "validation_status": evidence.validation_status,
        "rule_applied": evidence.rule_applied,
        "policy_version": evidence.policy_version,
        "reason": evidence.reason,
        "geometry_sha256": hashlib.sha256(
            (evidence.geometry_geojson or "").encode("utf-8")
        ).hexdigest(),
        "expires_at": evidence.expires_at.isoformat() if evidence.expires_at else None,
    }
    db.add(
        GeographicSecurityAuditLog(
            evidence_id=evidence.id,
            action=action,
            actor=actor,
            previous_value=previous_value,
            new_value=new_value,
        )
    )
    return evidence
