import argparse
import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

from .config import Settings
from .database import create_session_factory
from .geo import point_is_in_enabled_zone
from .models import Collectible, SpawnInstance, SpawnPoint, Zone, utcnow


def main():
    parser = argparse.ArgumentParser(description="Provision verified Crypto Go zones and spawn points.")
    commands = parser.add_subparsers(dest="command", required=True)
    create_zone = commands.add_parser("create-zone")
    create_zone.add_argument("--name", required=True)
    create_zone.add_argument("--boundary-file", required=True, type=Path)
    create_zone.add_argument("--enable", action="store_true", help="Enable only after safety and access review.")
    create_spawn = commands.add_parser("create-spawn")
    create_spawn.add_argument("--zone-id", required=True, type=UUID)
    create_spawn.add_argument("--ticker", required=True)
    create_spawn.add_argument("--latitude", required=True, type=float)
    create_spawn.add_argument("--longitude", required=True, type=float)
    create_spawn.add_argument("--dynamic", action="store_true")
    create_spawn.add_argument("--visibility-radius-meters", default=1500, type=int)
    create_spawn.add_argument("--collection-radius-meters", default=35, type=int)
    create_spawn.add_argument("--expires-after-seconds", default=86400, type=int)
    args = parser.parse_args()

    settings = Settings(_env_file=Path(__file__).resolve().parents[2] / ".env")
    factory = create_session_factory(settings.connection_url)
    with factory() as db:
        if args.command == "create-zone":
            boundary = json.loads(args.boundary_file.read_text(encoding="utf-8"))
            if boundary.get("type") != "Polygon" or not boundary.get("coordinates"):
                parser.error("boundary-file must contain a GeoJSON Polygon.")
            if any(ring[0] != ring[-1] for ring in boundary["coordinates"]):
                parser.error("Every GeoJSON polygon ring must be closed.")
            is_valid = db.execute(
                text("SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:boundary), 4326))"),
                {"boundary": json.dumps(boundary)},
            ).scalar_one()
            if not is_valid:
                parser.error("The GeoJSON polygon is invalid according to PostGIS.")
            zone = Zone(name=args.name, boundary_geojson=json.dumps(boundary), enabled=args.enable)
            db.add(zone)
            db.commit()
            print(f"Zone created with id {zone.id}; enabled={zone.enabled}")
            return

        zone = db.get(Zone, args.zone_id)
        collectible = db.scalar(select(Collectible).where(Collectible.ticker == args.ticker.upper()))
        if zone is None or not zone.enabled:
            parser.error("zone-id must identify an enabled, reviewed zone.")
        if collectible is None or not collectible.enabled:
            parser.error("ticker must identify an enabled catalog collectible.")
        if not point_is_in_enabled_zone(db, args.latitude, args.longitude, zone.id):
            parser.error("The spawn coordinates must lie inside the enabled zone.")
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
                    expires_at=utcnow() + timedelta(seconds=point.expires_after_seconds),
                )
            )
        db.commit()
        print(f"{'Dynamic spawn point' if args.dynamic else 'Fixed spawn'} created with id {point.id}.")


if __name__ == "__main__":
    main()
