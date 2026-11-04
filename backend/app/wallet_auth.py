import base64
import binascii
import hashlib
import struct
import time
from urllib.parse import urlsplit

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import is_address, to_checksum_address
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from tonsdk.boc import Cell
from tonsdk.utils import Address
from tonsdk.utils._address import InvalidAddressError

from .config import Settings
from .schemas import TonProof

WALLET_TG_CODE_HASH = "9149ae51c1e4689710cebf7830297b16acfbadb363a920a537893e7ffeeca768"
TON_NETWORKS = {
    "-239": "mainnet",
    "-3": "testnet",
}


def canonical_evm_address(address: str) -> str:
    if not is_address(address):
        raise ValueError("La dirección EVM no es válida.")
    return to_checksum_address(address)


def recover_evm_signer(message: str, signature: str) -> str:
    return Account.recover_message(encode_defunct(text=message), signature=signature)


def canonical_ton_address(address: str) -> Address:
    try:
        parsed = Address(address)
    except (InvalidAddressError, ValueError) as error:
        raise ValueError("La dirección TON no es válida.") from error
    if parsed.wc != 0:
        raise ValueError("La billetera TON debe estar en el workchain base.")
    return parsed


def _state_init_code_and_address(state_init_boc: str, address: Address) -> tuple[str, str]:
    try:
        serialized = base64.b64decode(state_init_boc, validate=True)
        if not serialized or len(serialized) > 16_384:
            raise ValueError("StateInit inválido.")
        state_init = Cell.one_from_boc(serialized)
        state = state_init.begin_parse()
        if state.read_bit():
            state.skip_bits(5)
        if state.read_bit():
            state.skip_bits(2)
        code = state.read_ref() if state.read_bit() else None
        data = state.read_ref() if state.read_bit() else None
        if code is None or data is None:
            raise ValueError("StateInit no contiene code/data.")
        calculated_address = f"{address.wc}:{state_init.bytes_hash().hex()}"
        requested_address = address.to_string(is_user_friendly=False)
        if calculated_address != requested_address:
            raise ValueError("La dirección no coincide con StateInit.")
        return code.bytes_hash().hex(), requested_address
    except (binascii.Error, IndexError, TypeError) as error:
        raise ValueError("StateInit de TON inválido.") from error


def _toncenter_call(
    settings: Settings,
    network: str,
    method: str,
    address: str,
) -> dict:
    network_name = TON_NETWORKS[network]
    base_url = (
        settings.toncenter_api_url
        if network_name == "mainnet"
        else settings.toncenter_testnet_api_url
    ).rstrip("/")
    headers = {}
    if settings.toncenter_api_key:
        headers["X-API-Key"] = settings.toncenter_api_key
    try:
        if method == "getAddressInformation":
            response = httpx.get(
                f"{base_url}/{method}",
                params={"address": address},
                headers=headers,
                timeout=5,
            )
        else:
            response = httpx.post(
                f"{base_url}/{method}",
                json={"address": address, "method": "get_public_key", "stack": []},
                headers=headers,
                timeout=5,
            )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("No se pudo verificar la billetera TON.") from error
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("El proveedor TON no pudo verificar la billetera.")
    return result.get("result", {})


def _ton_wallet_public_key(
    settings: Settings, network: str, address: str, state_init_boc: str
) -> bytes:
    address_object = canonical_ton_address(address)
    state_code_hash, raw_address = _state_init_code_and_address(
        state_init_boc, address_object
    )
    if state_code_hash != WALLET_TG_CODE_HASH:
        raise ValueError("Solo se admiten billeteras Telegram Wallet verificables.")

    account = _toncenter_call(settings, network, "getAddressInformation", raw_address)
    if account.get("state") != "active" or not account.get("code"):
        raise ValueError("La billetera Telegram debe estar activa en la red.")
    try:
        active_code = Cell.one_from_boc(base64.b64decode(account["code"], validate=True))
    except (binascii.Error, IndexError, TypeError) as error:
        raise RuntimeError("El proveedor TON devolvió un código inválido.") from error
    if active_code.bytes_hash().hex() != WALLET_TG_CODE_HASH:
        raise ValueError("El código activo no corresponde a Telegram Wallet.")

    public_key_result = _toncenter_call(
        settings, network, "runGetMethod", raw_address
    )
    stack = public_key_result.get("stack")
    if not isinstance(stack, list) or not stack:
        raise RuntimeError("El proveedor TON no devolvió la clave pública.")
    first = stack[0]
    value = first[1] if isinstance(first, list) and len(first) == 2 else None
    if not isinstance(value, str):
        raise RuntimeError("El proveedor TON devolvió una clave pública inválida.")
    try:
        public_key_int = int(value, 0)
    except ValueError as error:
        raise RuntimeError("El proveedor TON devolvió una clave pública inválida.") from error
    if not 0 <= public_key_int < 2**256:
        raise RuntimeError("El proveedor TON devolvió una clave pública inválida.")
    return public_key_int.to_bytes(32, "big")


def verify_ton_proof(
    *,
    settings: Settings,
    address: str,
    network: str,
    claimed_public_key: str | None,
    proof: TonProof,
    expected_domain: str,
    expected_payload: str,
) -> tuple[str, str]:
    if network not in TON_NETWORKS:
        raise ValueError("La red TON no está permitida.")
    address_object = canonical_ton_address(address)
    if proof.payload != expected_payload:
        raise ValueError("El desafío TON no coincide.")
    domain_bytes = proof.domain.value.encode("utf-8")
    if (
        proof.domain.value != expected_domain
        or proof.domain.lengthBytes != len(domain_bytes)
    ):
        raise ValueError("El dominio de la prueba TON no coincide.")
    now = int(time.time())
    if proof.timestamp > now + 30 or now - proof.timestamp > settings.wallet_auth_max_age_seconds:
        raise ValueError("La prueba de la billetera TON expiró.")

    public_key = _ton_wallet_public_key(
        settings, network, address, proof.state_init
    )
    if claimed_public_key and claimed_public_key.lower() != public_key.hex():
        raise ValueError("La clave pública TON no coincide.")

    try:
        signature = base64.b64decode(proof.signature, validate=True)
    except binascii.Error as error:
        raise ValueError("La firma TON no es válida.") from error
    if len(signature) != 64:
        raise ValueError("La firma TON no es válida.")

    message = (
        b"ton-proof-item-v2/"
        + struct.pack(">i", address_object.wc)
        + bytes(address_object.hash_part)
        + struct.pack("<I", len(domain_bytes))
        + domain_bytes
        + struct.pack("<Q", proof.timestamp)
        + proof.payload.encode("utf-8")
    )
    digest = hashlib.sha256(
        b"\xff\xffton-connect" + hashlib.sha256(message).digest()
    ).digest()
    try:
        VerifyKey(public_key).verify(digest, signature)
    except BadSignatureError as error:
        raise ValueError("La firma TON no es válida.") from error

    return address_object.to_string(is_user_friendly=False), network


def domain_from_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if not parsed.hostname:
        raise ValueError("El origen de la aplicación no es válido.")
    return parsed.netloc.lower()
