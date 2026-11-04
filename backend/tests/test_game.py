from datetime import timedelta
from uuid import uuid4

from app.models import (
    AntiCheatEvent,
    Collection,
    IdempotencyRecord,
    PlayerProfile,
    PointTransaction,
    User,
    XPTransaction,
    utcnow,
)
from .conftest import collect_request, create_player, create_spawn


def submit_collection(client, spawn_id, *, latitude=0.0, longitude=0.0, key=None, payload=None):
    key = key or str(uuid4())
    return client.post(
        "/api/v1/collectibles/collect",
        headers={"Idempotency-Key": key},
        json=payload or collect_request(spawn_id, latitude=latitude, longitude=longitude),
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


def test_collect_rejects_location_outside_collection_radius_and_logs_anomaly(client):
    create_player(client)
    spawn_id = create_spawn(client)
    response = submit_collection(client, spawn_id, latitude=0.001)
    assert response.status_code == 403
    factory = client.app.state.session_factory
    with factory() as db:
        assert db.query(AntiCheatEvent).filter_by(reason="outside_collection_radius").count() == 1
        assert db.query(Collection).count() == 0


def test_expired_spawn_cannot_be_collected(client):
    create_player(client)
    spawn_id = create_spawn(client, expires_at=utcnow() - timedelta(seconds=1))
    response = submit_collection(client, spawn_id)
    assert response.status_code == 410


def test_collection_is_idempotent_and_different_request_is_rejected(client):
    create_player(client)
    spawn_id = create_spawn(client)
    key = str(uuid4())
    payload = collect_request(spawn_id)
    first = submit_collection(client, spawn_id, key=key, payload=payload)
    repeated = submit_collection(client, spawn_id, key=key, payload=payload)
    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
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
    assert client.post("/api/v1/auth/telegram", json={"init_data": "user=%7B%7D"}).status_code == 401
    assert client.post("/api/v1/auth/telegram", json={"init_data": ""}).status_code == 422


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
