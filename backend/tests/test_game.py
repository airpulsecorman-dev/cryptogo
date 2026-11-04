from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import (
    AntiCheatEvent,
    AuthSession,
    Base,
    Collection,
    Collectible,
    IdempotencyRecord,
    PointTransaction,
    SpawnInstance,
    SpawnPoint,
    Zone,
    XPTransaction,
    utcnow,
)
from app.spawn_worker import generate_dynamic_spawns
from app.security import token_digest
from .conftest import collect_request, create_player, create_spawn, telegram_init_data


def submit_collection(
    client,
    spawn_id,
    *,
    latitude=0.0,
    longitude=0.0,
    accuracy=5,
    timestamp=None,
    key=None,
    payload=None,
):
    key = key or str(uuid4())
    return client.post(
        "/api/v1/collectibles/collect",
        headers={"Idempotency-Key": key},
        json=payload
        or collect_request(
            spawn_id,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            timestamp=timestamp,
        ),
    )


def test_registration_profile_inventory_and_ledger_persist(client):
    create_player(client)
    assert client.get("/api/v1/players/me").status_code == 200
    spawn_id = create_spawn(client)
    result = submit_collection(client, spawn_id)
    assert result.status_code == 200
    assert result.json()["rewards"] == {"points": 10, "xp": 10}

    inventory = client.get("/api/v1/inventory").json()
    assert inventory["total_collected"] == 1
    assert inventory["items"][0]["count"] == 1
    assert inventory["history"][0]["points"] == 10
    assert client.get("/api/v1/players/me/ledger").json()["points"][0]["amount"] == 10

    client.cookies.clear()
    create_player(client)
    profile = client.get("/api/v1/players/me").json()
    assert profile["points"] == 10
    assert profile["total_xp"] == 10
    assert profile["collected_count"] == 1


def test_game_endpoints_require_an_authenticated_session(client):
    protected_gets = (
        "/api/v1/players/me",
        "/api/v1/collectibles/nearby?latitude=0&longitude=0",
        "/api/v1/zones/nearby?latitude=0&longitude=0",
        "/api/v1/inventory",
        "/api/v1/missions",
        "/api/v1/leaderboard",
        "/api/v1/players/me/ledger",
    )
    for path in protected_gets:
        assert client.get(path).status_code == 401

    spawn_id = create_spawn(client)
    response = submit_collection(client, spawn_id)
    assert response.status_code == 401


def test_session_and_player_survive_application_restart(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'cryptogo.sqlite'}"
    settings = Settings(
        app_env="test",
        database_url=database_url,
        redis_url="redis://localhost:6379/15",
        telegram_bot_token="test-bot-token",
        dev_auth_enabled=False,
        cors_origins="http://localhost:3000",
    )
    first_app = create_app(settings)
    Base.metadata.create_all(first_app.state.engine)

    with TestClient(first_app) as first_client:
        player = create_player(first_client, 789001, "Restart Player")
        session_token = first_client.cookies.get(settings.session_cookie_name)
        assert session_token

    first_app.state.engine.dispose()
    restarted_app = create_app(settings)
    with TestClient(restarted_app) as restarted_client:
        restarted_client.cookies.set(settings.session_cookie_name, session_token)
        restored = restarted_client.get("/api/v1/players/me")
        assert restored.status_code == 200
        assert restored.json()["id"] == player["id"]
        assert restored.json()["telegram_id"] == 789001

        assert restarted_client.post("/api/v1/auth/logout").status_code == 204
        assert restarted_client.get("/api/v1/players/me").status_code == 401
    restarted_app.state.engine.dispose()


def test_collect_rejects_location_outside_collection_radius_and_logs_anomaly(client):
    create_player(client)
    spawn_id = create_spawn(client)
    response = submit_collection(client, spawn_id, latitude=0.001)
    assert response.status_code == 403
    factory = client.app.state.session_factory
    with factory() as db:
        assert (
            db.query(AntiCheatEvent)
            .filter_by(reason="outside_collection_radius")
            .count()
            == 1
        )
        assert db.query(Collection).count() == 0


def test_expired_spawn_cannot_be_collected(client):
    create_player(client)
    spawn_id = create_spawn(client, expires_at=utcnow() - timedelta(seconds=1))
    response = submit_collection(client, spawn_id)
    assert response.status_code == 410
    factory = client.app.state.session_factory
    with factory() as db:
        assert db.get(SpawnInstance, UUID(spawn_id)).state == "expired"


def test_stale_and_imprecise_locations_are_rejected_and_logged(client):
    create_player(client)
    spawn_id = create_spawn(client)
    stale = submit_collection(
        client,
        spawn_id,
        timestamp=utcnow() - timedelta(minutes=5),
    )
    imprecise = submit_collection(client, spawn_id, accuracy=75)
    assert stale.status_code == imprecise.status_code == 422
    factory = client.app.state.session_factory
    with factory() as db:
        reasons = {event.reason for event in db.query(AntiCheatEvent).all()}
        assert reasons == {"stale_or_future_location", "low_location_accuracy"}


def test_collection_is_idempotent_and_different_request_is_rejected(
    client, monkeypatch
):
    create_player(client)
    spawn_id = create_spawn(client)
    key = str(uuid4())
    payload = collect_request(spawn_id)
    first = submit_collection(client, spawn_id, key=key, payload=payload)
    repeated = submit_collection(client, spawn_id, key=key, payload=payload)
    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
    monkeypatch.setattr(
        "app.routers.game.utcnow",
        lambda: utcnow() + timedelta(minutes=5),
    )
    delayed_retry = submit_collection(client, spawn_id, key=key, payload=payload)
    assert delayed_retry.status_code == 200
    assert delayed_retry.json() == first.json()
    changed = submit_collection(
        client,
        spawn_id,
        key=key,
        payload={**payload, "latitude": 0.00001},
    )
    assert changed.status_code == 409
    factory = client.app.state.session_factory
    with factory() as db:
        assert db.query(Collection).count() == 1
        assert db.query(PointTransaction).count() == 1
        assert db.query(XPTransaction).count() == 1
        assert db.query(IdempotencyRecord).count() == 1


def test_nearby_requires_a_real_enabled_zone_and_location(client):
    create_player(client)
    spawn_id = create_spawn(client)
    response = client.get("/api/v1/collectibles/nearby?latitude=0&longitude=0")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["id"] == spawn_id
    outside = client.get("/api/v1/collectibles/nearby?latitude=10&longitude=10")
    assert outside.json()["items"] == []


def test_invalid_or_expired_telegram_initdata_is_rejected(client):
    assert (
        client.post(
            "/api/v1/auth/telegram", json={"init_data": "user=%7B%7D"}
        ).status_code
        == 401
    )
    assert (
        client.post("/api/v1/auth/telegram", json={"init_data": ""}).status_code == 422
    )
    expired_data = telegram_init_data(auth_timestamp=utcnow() - timedelta(days=1))
    expired = client.post("/api/v1/auth/telegram", json={"init_data": expired_data})
    assert expired.status_code == 401
    assert "expiraron" in expired.json()["detail"]
    tampered_data = telegram_init_data().replace(
        "%22id%22%3A123456",
        "%22id%22%3A654321",
    )
    tampered = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": tampered_data},
    )
    assert tampered.status_code == 401


def test_telegram_initdata_rejects_duplicate_fields(client):
    init_data = telegram_init_data()
    duplicate_auth_date = f"{init_data}&auth_date=1"
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": duplicate_auth_date},
    )
    assert response.status_code == 401
    assert "duplicados" in response.json()["detail"]


def test_telegram_session_cookie_is_secure_and_only_its_digest_is_stored(client):
    client.app.state.settings.session_cookie_secure = True
    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": telegram_init_data()},
    )
    assert response.status_code == 200

    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=lax" in cookie_header

    session_token = response.cookies.get(client.app.state.settings.session_cookie_name)
    assert session_token
    factory = client.app.state.session_factory
    with factory() as db:
        assert db.get(AuthSession, token_digest(session_token)) is not None
        assert db.get(AuthSession, session_token) is None


def test_expired_telegram_session_is_rejected_and_removed(client):
    create_player(client)
    session_token = client.cookies.get(client.app.state.settings.session_cookie_name)
    assert session_token

    factory = client.app.state.session_factory
    with factory() as db:
        auth_session = db.get(AuthSession, token_digest(session_token))
        assert auth_session is not None
        auth_session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()

    response = client.get("/api/v1/players/me")
    assert response.status_code == 401
    with factory() as db:
        assert db.get(AuthSession, token_digest(session_token)) is None


def test_production_requires_https_cors_and_disables_development_auth(
    client, monkeypatch
):
    from pydantic import ValidationError

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-from-environment")
    assert (
        Settings(_env_file=None, app_env="test").telegram_bot_token
        == "test-token-from-environment"
    )

    with pytest.raises(ValidationError, match="Development authentication"):
        Settings(
            app_env="production",
            telegram_bot_token="test-bot-token",
            session_cookie_secure=True,
            dev_auth_enabled=True,
            cors_origins="https://app.example.test",
        )

    with pytest.raises(ValidationError, match="HTTPS origins"):
        Settings(
            app_env="production",
            telegram_bot_token="test-bot-token",
            session_cookie_secure=True,
            cors_origins="http://app.example.test",
        )


def test_production_auth_endpoint_rejects_development_login():
    settings = Settings(
        app_env="production",
        database_url="sqlite://",
        telegram_bot_token="test-bot-token",
        session_cookie_secure=True,
        cors_origins="https://app.example.test",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as production_client:
        response = production_client.post(
            "/api/v1/auth/dev",
            json={"telegram_id": 88, "first_name": "Local"},
            headers={"Origin": "https://app.example.test"},
        )
    assert response.status_code == 404
    assert response.headers["access-control-allow-origin"] == "https://app.example.test"
    assert response.headers["access-control-allow-credentials"] == "true"
    app.state.engine.dispose()


def test_second_player_cannot_collect_an_already_claimed_spawn(client):
    create_player(client, 123456, "First Player")
    spawn_id = create_spawn(client)
    assert submit_collection(client, spawn_id).status_code == 200

    client.cookies.clear()
    create_player(client, 654321, "Second Player")
    assert submit_collection(client, spawn_id).status_code == 409
    factory = client.app.state.session_factory
    with factory() as db:
        assert db.query(Collection).count() == 1
        assert db.query(PointTransaction).count() == 1
        assert db.query(XPTransaction).count() == 1


def test_development_login_is_not_available_in_test_or_production(client):
    response = client.post(
        "/api/v1/auth/dev",
        json={"telegram_id": 88, "first_name": "Local"},
    )
    assert response.status_code == 404


def test_missions_are_an_explicit_empty_state_not_fabricated_progress(client):
    create_player(client)
    result = client.get("/api/v1/missions")
    assert result.status_code == 200
    assert result.json()["items"] == []


def test_dynamic_spawns_are_generated_at_configured_points_and_expire(client):
    factory = client.app.state.session_factory
    with factory() as db:
        zone = Zone(
            name="Approved zone",
            enabled=True,
            boundary_geojson='{"type":"Polygon","coordinates":[[[-1,-1],[1,-1],[1,1],[-1,1],[-1,-1]]]}',
        )
        collectible = Collectible(
            ticker="BTC",
            name="Bitcoin",
            symbol="₿",
            rarity="common",
            points_reward=10,
            xp_reward=10,
        )
        db.add_all([zone, collectible])
        db.flush()
        point = SpawnPoint(
            zone_id=zone.id,
            collectible_id=collectible.id,
            latitude=0,
            longitude=0,
            dynamic=True,
            expires_after_seconds=60,
        )
        db.add(point)
        db.commit()
        point_id = point.id

    assert generate_dynamic_spawns(factory) == 1
    assert generate_dynamic_spawns(factory) == 0
    with factory() as db:
        active = (
            db.query(SpawnInstance)
            .filter_by(spawn_point_id=point_id, state="available")
            .one()
        )
        active.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert generate_dynamic_spawns(factory) == 1
    with factory() as db:
        assert (
            db.query(SpawnInstance)
            .filter_by(spawn_point_id=point_id, state="available")
            .count()
            == 1
        )
        assert (
            db.query(SpawnInstance)
            .filter_by(spawn_point_id=point_id, state="expired")
            .count()
            == 1
        )
