import pytest
import redis
from fastapi import HTTPException, Request

from app.config import Settings
from app.main import create_app
from app.routers.auth import _rate_limit


class UnavailableRedis:
    def eval(self, *_args):
        raise redis.ConnectionError("Redis is unavailable")


def create_request(app):
    return Request(
        {
            "type": "http",
            "app": app,
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )


def test_development_uses_local_rate_limit_when_redis_is_unavailable():
    settings = Settings(
        _env_file=None,
        app_env="development",
        database_url="sqlite://",
        cors_origins="http://localhost:3000",
    )
    app = create_app(settings)
    app.state.redis = UnavailableRedis()
    request = create_request(app)

    try:
        for _ in range(10):
            _rate_limit(request, "wallet-challenge:test", 10, 600)

        with pytest.raises(HTTPException) as error:
            _rate_limit(request, "wallet-challenge:test", 10, 600)

        assert error.value.status_code == 429
    finally:
        app.state.engine.dispose()


def test_production_fails_closed_when_redis_is_unavailable():
    settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="sqlite://",
        telegram_bot_token="test-bot-token",
        session_cookie_secure=True,
        cors_origins="https://app.example.test",
    )
    app = create_app(settings)
    app.state.redis = UnavailableRedis()

    try:
        with pytest.raises(HTTPException) as error:
            _rate_limit(create_request(app), "wallet-challenge:test", 10, 600)

        assert error.value.status_code == 503
    finally:
        app.state.engine.dispose()
