import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

from .config import Settings
from .database import create_session_factory
from .geographic_safety import (
    _geometry_is_valid,
    classify_geographic_safety,
    persist_geographic_evidence,
)
from .geo import point_is_in_enabled_zone
from .models import (
    Collectible,
    GeographicSecurityEvidence,
    SpawnInstance,
    SpawnPoint,
    Zone,
    utcnow,
)


def main():
    parser = argparse.ArgumentParser(
        description="Provision verified Crypto Go zones and spawn points."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create_zone = commands.add_parser("create-zone")
    create_zone.add_argument("--name", required=True)
    create_zone.add_argument("--boundary-file", required=True, type=Path)
    create_zone.add_argument(
        "--enable",
        action="store_true",
        help="Enable only after safety and access review.",
    )
    create_spawn = commands.add_parser("create-spawn")
    create_spawn.add_argument("--zone-id", required=True, type=UUID)
    create_spawn.add_argument("--ticker", required=True)
    create_spawn.add_argument("--latitude", required=True, type=float)
    create_spawn.add_argument("--longitude", required=True, type=float)
    create_spawn.add_argument("--dynamic", action="store_true")
    create_spawn.add_argument("--visibility-radius-meters", default=1500, type=int)
    create_spawn.add_argument("--collection-radius-meters", default=35, type=int)
    create_spawn.add_argument("--expires-after-seconds", default=86400, type=int)
    list_zones = commands.add_parser("list-zones")
    list_zones.add_argument("--enabled-only", action="store_true")
    set_zone_state = commands.add_parser("set-zone-state")
    set_zone_state.add_argument("--zone-id", required=True, type=UUID)
    set_zone_state.add_argument("--enabled", dest="enabled", action="store_true")
    set_zone_state.add_argument("--disabled", dest="enabled", action="store_false")
    set_zone_state.set_defaults(enabled=None)
    create_evidence = commands.add_parser(
        "create-security-evidence",
        help="Record a manually reviewed, sourced geographic safety area.",
    )
    create_evidence.add_argument("--geometry-file", required=True, type=Path)
    create_evidence.add_argument(
        "--status",
        required=True,
        choices=("safe", "caution", "restricted", "unknown"),
    )
    create_evidence.add_argument("--place-type", required=True)
    create_evidence.add_argument("--source-name", required=True)
    create_evidence.add_argument("--source-identifier", required=True)
    create_evidence.add_argument("--license-terms", required=True)
    create_evidence.add_argument(
        "--access-status",
        required=True,
        choices=("unknown", "public", "authorized", "restricted"),
    )
    create_evidence.add_argument("--confidence", required=True, type=float)
    create_evidence.add_argument("--expires-at", required=True)
    create_evidence.add_argument("--reason", required=True)
    create_evidence.add_argument("--rule-applied", required=True)
    create_evidence.add_argument("--actor", required=True)
    args = parser.parse_args()

    settings = Settings(_env_file=Path(__file__).resolve().parents[2] / ".env")
    factory = create_session_factory(settings.connection_url)
    with factory() as db:
        if args.command == "create-security-evidence":
            geometry = json.loads(args.geometry_file.read_text(encoding="utf-8"))
            if not _geometry_is_valid(geometry):
                parser.error(
                    "geometry-file must contain a valid Polygon or MultiPolygon."
                )
            try:
                expires_at = datetime.fromisoformat(args.expires_at)
            except ValueError:
                parser.error("--expires-at must be an ISO-8601 datetime.")
            if expires_at.tzinfo is None or expires_at <= utcnow():
                parser.error("--expires-at must be a future ISO-8601 datetime with timezone.")
            if not math.isfinite(args.confidence) or not 0 <= args.confidence <= 1:
                parser.error("--confidence must be between 0 and 1.")
            if args.status == "safe" and (
                args.access_status not in {"public", "authorized"}
                or args.confidence < 0.9
            ):
                parser.error(
                    "Safe evidence requires public/authorized access and confidence >= 0.9."
                )
            evidence = GeographicSecurityEvidence(
                geometry_geojson=json.dumps(geometry),
                security_status=args.status,
                place_type=args.place_type,
                source_name=args.source_name,
                source_identifier=args.source_identifier,
                license_terms=args.license_terms,
                access_status=args.access_status,
                imported_at=utcnow(),
                verified_at=utcnow(),
                expires_at=expires_at,
                confidence=args.confidence,
                validation_status="verified",
                rule_applied=args.rule_applied,
                reason=args.reason,
            )
            persist_geographic_evidence(db, evidence, actor=args.actor)
            db.commit()
            print(f"Geographic security evidence created with id {evidence.id}.")
            return

        if args.command == "create-zone":
            boundary = json.loads(args.boundary_file.read_text(encoding="utf-8"))
            if boundary.get("type") != "Polygon" or not boundary.get("coordinates"):
                parser.error("boundary-file must contain a GeoJSON Polygon.")
            for ring in boundary["coordinates"]:
                if not ring or ring[0] != ring[-1]:
                    parser.error("Every GeoJSON polygon ring must be closed.")
            if db.bind.dialect.name == "postgresql":
                is_valid = db.execute(
                    text(
                        "SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:boundary), 4326))"
                    ),
                    {"boundary": json.dumps(boundary)},
                ).scalar_one()
                if not is_valid:
                    parser.error("The GeoJSON polygon is invalid according to PostGIS.")
            zone = Zone(
                name=args.name,
                boundary_geojson=json.dumps(boundary),
                enabled=args.enable,
            )
            db.add(zone)
            db.commit()
            print(f"Zone created with id {zone.id}; enabled={zone.enabled}")
            return

        if args.command == "list-zones":
            query = db.query(Zone)
            if args.enabled_only:
                query = query.filter(Zone.enabled.is_(True))
            for zone in query.order_by(Zone.created_at.asc()):
                print(f"{zone.id} | {zone.name} | enabled={zone.enabled}")
            return

        if args.command == "set-zone-state":
            if args.enabled is None:
                parser.error("Pass --enabled or --disabled to set the zone state.")
            zone = db.get(Zone, args.zone_id)
            if zone is None:
                parser.error("zone-id must identify an existing zone.")
            zone.enabled = bool(args.enabled)
            db.commit()
            print(f"Zone {zone.id} enabled={zone.enabled}")
            return

        zone = db.get(Zone, args.zone_id)
        collectible = db.scalar(
            select(Collectible).where(Collectible.ticker == args.ticker.upper())
        )
        if zone is None or not zone.enabled:
            parser.error("zone-id must identify an enabled, reviewed zone.")
        if collectible is None or not collectible.enabled:
            parser.error("ticker must identify an enabled catalog collectible.")
        if not point_is_in_enabled_zone(db, args.latitude, args.longitude, zone.id):
            parser.error("The spawn coordinates must lie inside the enabled zone.")
        decision = classify_geographic_safety(
            db, args.latitude, args.longitude, args.collection_radius_meters
        )
        if not decision.allows_generation:
            parser.error(
                "The spawn location is not classified safe by current geographic evidence."
            )
        point = SpawnPoint(
            zone_id=zone.id,
            collectible_id=collectible.id,
            latitude=args.latitude,
            longitude=args.longitude,
            dynamic=args.dynamic,
            visibility_radius_meters=args.visibility_radius_meters,
            collection_radius_meters=args.collection_radius_meters,
            expires_after_seconds=args.expires_after_seconds,
        )
        db.add(point)
        db.flush()
        if not args.dynamic:
            db.add(
                SpawnInstance(
                    spawn_point_id=point.id,
                    zone_id=zone.id,
                    collectible_id=collectible.id,
                    latitude=point.latitude,
                    longitude=point.longitude,
                    visibility_radius_meters=point.visibility_radius_meters,
                    collection_radius_meters=point.collection_radius_meters,
                    expires_at=utcnow()
                    + timedelta(seconds=point.expires_after_seconds),
                )
            )
        db.commit()
        print(
            f"{'Dynamic spawn point' if args.dynamic else 'Fixed spawn'} created with id {point.id}."
        )


if __name__ == "__main__":
    main()
