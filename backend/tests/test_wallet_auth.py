import base64
from datetime import timedelta

from eth_account import Account
from eth_account.messages import encode_defunct

from app.models import AuthChallenge, AuthSession, User, WalletIdentity, utcnow
from app.security import token_digest
from tests.conftest import create_player

ORIGIN = "http://localhost:3000"


def create_evm_challenge(client, wallet, *, chain_id=1):
    return client.post(
        "/api/v1/auth/evm/challenge",
        headers={"Origin": ORIGIN},
        json={"address": wallet.address, "chain_id": chain_id},
    )


def test_evm_wallet_sign_in_creates_and_reuses_a_separate_persistent_account(client):
    create_player(client, 987654, "Telegram player")

    wallet = Account.create()
    challenge_response = create_evm_challenge(client, wallet)
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()
    assert "Chain ID: 1" in challenge["message"]
    assert "will not trigger a blockchain transaction" in challenge["message"]

    signature = "0x" + Account.sign_message(
        encode_defunct(text=challenge["message"]), wallet.key
    ).signature.hex()
    payload = {
        "address": wallet.address,
        "chain_id": 1,
        "nonce": challenge["nonce"],
        "signature": signature,
    }
    response = client.post(
        "/api/v1/auth/evm/verify",
        headers={"Origin": ORIGIN},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["telegram_id"] is None
    assert response.json()["first_name"].startswith("Jugador 0x")
    assert response.cookies.get("cryptogo_session")
    assert client.get("/api/v1/players/me").json()["id"] == response.json()["id"]

    repeated = client.post(
        "/api/v1/auth/evm/verify",
        headers={"Origin": ORIGIN},
        json=payload,
    )
    assert repeated.status_code == 401

    with client.app.state.session_factory() as db:
        identity = (
            db.query(WalletIdentity)
            .filter_by(provider="evm", address=wallet.address.lower())
            .one()
        )
        assert identity.provider == "evm"
        assert identity.network == "evm"
        assert identity.address == wallet.address.lower()
        assert db.get(User, identity.user_id).telegram_id is None
        token = response.cookies.get("cryptogo_session")
        assert db.get(AuthSession, token_digest(token))
        assert db.query(User).count() == 2


def test_evm_wallet_rejects_bad_signatures_and_origins(client):
    wallet = Account.create()
    challenge_response = create_evm_challenge(client, wallet)
    challenge = challenge_response.json()
    bad_signature = "0x" + "00" * 65
    response = client.post(
        "/api/v1/auth/evm/verify",
        headers={"Origin": ORIGIN},
        json={
            "address": wallet.address,
            "chain_id": 1,
            "nonce": challenge["nonce"],
            "signature": bad_signature,
        },
    )
    assert response.status_code == 401

    rejected_origin = client.post(
        "/api/v1/auth/evm/challenge",
        headers={"Origin": "https://attacker.example"},
        json={"address": wallet.address, "chain_id": 1},
    )
    assert rejected_origin.status_code == 403


def test_evm_wallet_challenge_is_bound_to_chain_and_wallet(client):
    wallet = Account.create()
    challenge = create_evm_challenge(client, wallet).json()
    signature = "0x" + Account.sign_message(
        encode_defunct(text=challenge["message"]), wallet.key
    ).signature.hex()
    response = client.post(
        "/api/v1/auth/evm/verify",
        headers={"Origin": ORIGIN},
        json={
            "address": wallet.address,
            "chain_id": 137,
            "nonce": challenge["nonce"],
            "signature": signature,
        },
    )
    assert response.status_code == 401
    with client.app.state.session_factory() as db:
        assert db.query(WalletIdentity).count() == 0

def test_ton_wallet_challenge_uses_origin_and_rejects_unverified_proofs(client):
    challenge_response = client.post(
        "/api/v1/auth/ton/challenge",
        headers={"Origin": ORIGIN},
    )
    assert challenge_response.status_code == 200
    payload = challenge_response.json()["payload"]
    response = client.post(
        "/api/v1/auth/ton/verify",
        headers={"Origin": ORIGIN},
        json={
            "address": "0:" + "00" * 32,
            "network": "-1",
            "proof": {
                "timestamp": int(utcnow().timestamp()),
                "domain": {
                    "lengthBytes": len("localhost:3000"),
                    "value": "localhost:3000",
                },
                "signature": base64.b64encode(b"\x00" * 64).decode(),
                "payload": payload,
                "state_init": base64.b64encode(b"not-a-boc").decode(),
            },
        },
    )
    assert response.status_code == 401
    with client.app.state.session_factory() as db:
        assert db.query(WalletIdentity).count() == 0


def test_wallet_challenge_expires_and_cannot_be_replayed(client):
    wallet = Account.create()
    challenge = create_evm_challenge(client, wallet).json()
    with client.app.state.session_factory() as db:
        record = db.get(AuthChallenge, challenge["nonce"])
        record.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    signature = "0x" + Account.sign_message(
        encode_defunct(text=challenge["message"]), wallet.key
    ).signature.hex()
    response = client.post(
        "/api/v1/auth/evm/verify",
        headers={"Origin": ORIGIN},
        json={
            "address": wallet.address,
            "chain_id": 1,
            "nonce": challenge["nonce"],
            "signature": signature,
        },
    )
    assert response.status_code == 401
