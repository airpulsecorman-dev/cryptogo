import time
from datetime import timedelta

from sqlalchemy import select

from .config import Settings
from pathlib import Path

from .database import create_session_factory
from .models import SpawnInstance, SpawnPoint, Zone, utcnow


def generate_dynamic_spawns(session_factory) -> int:
    created = 0
    now = utcnow()
    with session_factory() as db:
        db.query(SpawnInstance).filter(
            SpawnInstance.state == "available",
            SpawnInstance.expires_at <= now,
        ).update({SpawnInstance.state: "expired"}, synchronize_session=False)
        points = db.scalars(
            select(SpawnPoint)
            .join(Zone, Zone.id == SpawnPoint.zone_id)
            .where(SpawnPoint.enabled.is_(True), SpawnPoint.dynamic.is_(True), Zone.enabled.is_(True))
            .with_for_update(skip_locked=True)
        ).all()
        for point in points:
            active = db.scalar(
                select(SpawnInstance.id)
                .where(
                    SpawnInstance.spawn_point_id == point.id,
                    SpawnInstance.state == "available",
                    SpawnInstance.expires_at > now,
                )
                .limit(1)
            )
            if active is not None:
                continue
            db.add(
                SpawnInstance(
                    spawn_point_id=point.id,
                    zone_id=point.zone_id,
                    collectible_id=point.collectible_id,
                    latitude=point.latitude,
                    longitude=point.longitude,
                    visibility_radius_meters=point.visibility_radius_meters,
                    collection_radius_meters=point.collection_radius_meters,
                    expires_at=now + timedelta(seconds=point.expires_after_seconds),
                )
            )
            created += 1
        db.commit()
    return created


def run():
    settings = Settings(_env_file=Path(__file__).resolve().parents[2] / ".env")
    session_factory = create_session_factory(settings.connection_url)
    while True:
        generate_dynamic_spawns(session_factory)
        time.sleep(15)


if __name__ == "__main__":
    run()
