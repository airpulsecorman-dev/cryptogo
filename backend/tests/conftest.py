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
    response = client.post(
        "/api/v1/auth/dev",
        json={"telegram_id": telegram_id, "first_name": name},
    )
    assert response.status_code == 404
    # Tests provision a session with the same database models as the app;
    # development authentication is separately covered as disabled here.
    factory = client.app.state.session_factory
    with factory() as db:
        user = db.query(User).filter_by(telegram_id=telegram_id).one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, first_name=name)
            db.add(user)
            db.flush()
        if db.get(PlayerProfile, user.id) is None:
            db.add(PlayerProfile(user_id=user.id))
        db.commit()
    # Sign a valid Telegram initData payload using the configured test token.
    import hashlib
    import hmac
    from urllib.parse import urlencode

    fields = {
        "auth_date": str(int(utcnow().timestamp())),
        "user": json.dumps({"id": telegram_id, "first_name": name}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", b"test-bot-token", hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    auth = client.post("/api/v1/auth/telegram", json={"init_data": urlencode(fields)})
    assert auth.status_code == 200
    return auth.json()


def collect_request(spawn_id, *, latitude=0.0, longitude=0.0):
    return {
        "spawn_instance_id": spawn_id,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_meters": 5,
        "client_timestamp": utcnow().isoformat(),
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
