import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLAlchemySession

from app.config import Settings
from app.main import create_app
from app.models import (
    Base,
    Collection,
    IdempotencyRecord,
    PlayerProfile,
    PointTransaction,
    SpawnInstance,
    XPTransaction,
    utcnow,
)
from .conftest import collect_request, create_player, create_spawn

POSTGRES_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set POSTGRES_TEST_DATABASE_URL to a dedicated PostGIS test database.",
)


def test_only_one_player_collects_a_spawn_concurrently(monkeypatch):
    database_name = (make_url(POSTGRES_URL).database or "").lower()
    assert database_name == "test" or database_name.endswith(("_test", "-test")), (
        "POSTGRES_TEST_DATABASE_URL must point to a database named with a _test or -test suffix."
    )

    schema_name = f"cryptogo_concurrency_{uuid4().hex}"
    bootstrap_engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    app_engine = None
    try:
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        app = create_app(
            Settings(
                app_env="test",
                database_url=POSTGRES_URL,
                telegram_bot_token="test-bot-token",
                cors_origins="http://localhost:3000",
            )
        )
        app_engine = app.state.session_factory.kw["bind"]

        @event.listens_for(app_engine, "connect")
        def set_test_search_path(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(f'SET search_path TO "{schema_name}", public')
            finally:
                cursor.close()

        with app_engine.connect() as connection:
            connection.execute(text("SELECT PostGIS_Full_Version()")).scalar_one()
        Base.metadata.create_all(app_engine)

        with TestClient(app) as first_client, TestClient(app) as second_client:
            create_player(first_client, 900001, "Player One")
            create_player(second_client, 900002, "Player Two")
            spawn_id = create_spawn(first_client)
            barrier = Barrier(2)
            clients = (first_client, second_client)
            keys = (str(uuid4()), str(uuid4()))
            payload = collect_request(spawn_id)

            def attempt(client, key):
                barrier.wait()
                response = client.post(
                    "/api/v1/collectibles/collect",
                    headers={"Idempotency-Key": key},
                    json=payload,
                )
                return response.status_code, response.json()

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(attempt, clients, keys))

            assert sorted(status_code for status_code, _ in outcomes) == [200, 409]
            winner_index = next(
                index for index, (status_code, _) in enumerate(outcomes) if status_code == 200
            )
            winner = clients[winner_index]
            original_response = outcomes[winner_index][1]

            repeated = winner.post(
                "/api/v1/collectibles/collect",
                headers={"Idempotency-Key": keys[winner_index]},
                json=payload,
            )
            assert repeated.status_code == 200
            assert repeated.json() == original_response

            changed_payload = {**payload, "latitude": 0.00001}
            changed_request = winner.post(
                "/api/v1/collectibles/collect",
                headers={"Idempotency-Key": keys[winner_index]},
                json=changed_payload,
            )
            assert changed_request.status_code == 409

            with app.state.session_factory() as db:
                assert db.query(Collection).count() == 1
                assert db.query(PointTransaction).count() == 1
                assert db.query(XPTransaction).count() == 1
                assert db.query(IdempotencyRecord).count() == 1
                assert {
                    (profile.points, profile.total_xp, profile.collected_count)
                    for profile in db.query(PlayerProfile).all()
                } == {(10, 10, 1), (0, 0, 0)}

                collected_spawn = db.get(SpawnInstance, UUID(spawn_id))
                failed_spawn = SpawnInstance(
                    zone_id=collected_spawn.zone_id,
                    collectible_id=collected_spawn.collectible_id,
                    latitude=collected_spawn.latitude,
                    longitude=collected_spawn.longitude,
                    visibility_radius_meters=collected_spawn.visibility_radius_meters,
                    collection_radius_meters=collected_spawn.collection_radius_meters,
                    expires_at=utcnow() + timedelta(hours=1),
                )
                db.add(failed_spawn)
                db.commit()
                failed_spawn_id = str(failed_spawn.id)

            def fail_commit(_session):
                raise SQLAlchemyError("Injected commit failure for rollback verification.")

            with monkeypatch.context() as patch:
                patch.setattr(SQLAlchemySession, "commit", fail_commit)
                failed_collection = winner.post(
                    "/api/v1/collectibles/collect",
                    headers={"Idempotency-Key": str(uuid4())},
                    json=collect_request(failed_spawn_id),
                )

            assert failed_collection.status_code == 503
            with app.state.session_factory() as db:
                assert db.query(Collection).count() == 1
                assert db.query(PointTransaction).count() == 1
                assert db.query(XPTransaction).count() == 1
                assert db.query(IdempotencyRecord).count() == 1
                assert db.get(SpawnInstance, UUID(failed_spawn_id)).state == "available"
                winner_profile = db.get(PlayerProfile, UUID(original_response["player"]["id"]))
                assert (winner_profile.points, winner_profile.total_xp) == (10, 10)
    finally:
        if app_engine is not None:
            app_engine.dispose()
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        bootstrap_engine.dispose()
