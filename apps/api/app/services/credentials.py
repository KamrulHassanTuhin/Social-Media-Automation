from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialCipher:
    """AES-GCM envelope encryption for provider credentials."""

    def __init__(self, key_material: str) -> None:
        if not key_material or key_material == "local-only-change-me":
            raise ValueError("A dedicated ENCRYPTION_KEY is required for credential storage.")
        self.key = hashlib.sha256(key_material.encode("utf-8")).digest()

    def encrypt(self, credentials: dict[str, str]) -> tuple[str, str]:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.key).encrypt(nonce, json.dumps(credentials).encode("utf-8"), None)
        return base64.urlsafe_b64encode(ciphertext).decode("ascii"), base64.urlsafe_b64encode(nonce).decode("ascii")

    def decrypt(self, ciphertext: str, nonce: str) -> dict[str, str]:
        raw = AESGCM(self.key).decrypt(base64.urlsafe_b64decode(nonce), base64.urlsafe_b64decode(ciphertext), None)
        return json.loads(raw.decode("utf-8"))
