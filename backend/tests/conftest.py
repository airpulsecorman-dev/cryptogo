import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Base, Collectible, PlayerProfile, SpawnInstance, User, Zone, utcnow


@pytest.fixture
def client():
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        redis_url="redis://localhost:6379/15",
        telegram_bot_token="test-bot-token",
        dev_auth_enabled=False,
        cors_origins="http://localhost:3000",
    )
    app = create_app(settings)
    engine = app.state.session_factory.kw["bind"]
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_player(client: TestClient, telegram_id: int = 123456, name: str = "Test Player") -> dict:
    response = client.post("/api/v1/auth/telegram", json={"init_data": telegram_init_data(telegram_id, name)})
    assert response.status_code == 200
    return response.json()


def telegram_init_data(telegram_id=123456, name="Test Player", *, auth_timestamp=None):
    import hashlib
    import hmac
    from urllib.parse import urlencode

    fields = {
        "auth_date": str(int((auth_timestamp or utcnow()).timestamp())),
        "user": json.dumps({"id": telegram_id, "first_name": name}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", b"test-bot-token", hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def collect_request(spawn_id, *, latitude=0.0, longitude=0.0, accuracy=5, timestamp=None):
    return {
        "spawn_instance_id": spawn_id,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_meters": accuracy,
        "client_timestamp": (timestamp or utcnow()).isoformat(),
    }


def create_spawn(client: TestClient, *, expires_at=None, latitude=0.0, longitude=0.0) -> str:
    factory = client.app.state.session_factory
    with factory() as db:
        zone = Zone(
            name="Test zone",
            enabled=True,
            boundary_geojson=json.dumps(
                {
                    "type": "Polygon",
                    "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]],
                }
            ),
        )
        collectible = Collectible(
            ticker="BTC", name="Bitcoin", symbol="₿", rarity="common", points_reward=10, xp_reward=10
        )
        db.add_all([zone, collectible])
        db.flush()
        spawn = SpawnInstance(
            zone_id=zone.id,
            collectible_id=collectible.id,
            latitude=latitude,
            longitude=longitude,
            visibility_radius_meters=1_500,
            collection_radius_meters=35,
            expires_at=expires_at or utcnow() + timedelta(hours=1),
        )
        db.add(spawn)
        db.commit()
        return str(spawn.id)
