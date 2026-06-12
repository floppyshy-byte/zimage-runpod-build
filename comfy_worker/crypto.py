"""AES-256-GCM payload encryption helpers."""

import base64
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .env import env

_RAW_KEY = env.comfy_encryption_key
if _RAW_KEY:
    _key_bytes = bytes.fromhex(_RAW_KEY)
    if len(_key_bytes) != 32:
        raise RuntimeError("COMFY_ENCRYPTION_KEY must be 64 hex characters (32 bytes)")
    ENCRYPTION_KEY: bytes | None = _key_bytes
else:
    ENCRYPTION_KEY = None


def aes_decrypt(encoded: str) -> bytes:
    data = base64.b64decode(encoded)
    nonce, ciphertext = data[:12], data[12:]
    return AESGCM(ENCRYPTION_KEY).decrypt(nonce, ciphertext, None)


def aes_encrypt(plaintext: bytes) -> str:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(ENCRYPTION_KEY).encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()
