import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Base
from .conftest import create_player, create_spawn, collect_request

POSTGRES_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="Set POSTGRES_TEST_DATABASE_URL to run PostGIS concurrency tests.")


def test_only_one_player_collects_a_spawn_concurrently():
    app = create_app(
        Settings(
            app_env="test",
            database_url=POSTGRES_URL,
            telegram_bot_token="test-bot-token",
            cors_origins="http://localhost:3000",
        )
    )
    engine = app.state.session_factory.kw["bind"]
    Base.metadata.create_all(engine)
    with TestClient(app) as first_client, TestClient(app) as second_client:
        create_player(first_client, 900001, "Player One")
        create_player(second_client, 900002, "Player Two")
        spawn_id = create_spawn(first_client)
        barrier = Barrier(2)

        def attempt(client):
            barrier.wait()
            return client.post(
                "/api/v1/collectibles/collect",
                headers={"Idempotency-Key": str(uuid4())},
                json=collect_request(spawn_id),
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (first_client, second_client)))
        assert sorted(outcomes) == [200, 409]
    Base.metadata.drop_all(engine)
    engine.dispose()
