"""Signatures. Ed25519 (third-party verifiable) when `cryptography` is available;
HMAC-SHA256 development fallback (symmetric: NOT third-party verifiable, flagged in evidence)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

try:  # optional dependency
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    HAVE_ED25519 = True
except Exception:  # pragma: no cover
    HAVE_ED25519 = False


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Verifier(ABC):
    key_id: str
    alg: str
    third_party_verifiable: bool

    @abstractmethod
    def verify(self, data: bytes, signature: str) -> bool: ...

    @abstractmethod
    def public_info(self) -> dict: ...


class Signer(ABC):
    key_id: str
    alg: str
    third_party_verifiable: bool

    @abstractmethod
    def sign(self, data: bytes) -> str: ...

    @abstractmethod
    def verifier(self) -> Verifier: ...

    def identity(self) -> dict:
        return {"key_id": self.key_id, "alg": self.alg, "third_party_verifiable": self.third_party_verifiable}


class Ed25519Verifier(Verifier):
    alg = "ed25519"
    third_party_verifiable = True

    def __init__(self, public_raw: bytes):
        self._raw = public_raw
        self._pk = Ed25519PublicKey.from_public_bytes(public_raw)
        self.key_id = hashlib.sha256(public_raw).hexdigest()[:16]

    def verify(self, data: bytes, signature: str) -> bool:
        try:
            self._pk.verify(unb64(signature), data)
            return True
        except Exception:
            return False

    def public_info(self) -> dict:
        return {"key_id": self.key_id, "alg": self.alg, "public_key": b64(self._raw)}

    @classmethod
    def from_info(cls, info: dict) -> "Ed25519Verifier":
        return cls(unb64(info["public_key"]))


class Ed25519Signer(Signer):
    alg = "ed25519"
    third_party_verifiable = True

    def __init__(self, private_raw: bytes | None = None):
        self._sk = Ed25519PrivateKey.from_private_bytes(private_raw) if private_raw else Ed25519PrivateKey.generate()
        raw = self._sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self._verifier = Ed25519Verifier(raw)
        self.key_id = self._verifier.key_id

    def private_raw(self) -> bytes:
        return self._sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                      serialization.NoEncryption())

    def sign(self, data: bytes) -> str:
        return b64(self._sk.sign(data))

    def verifier(self) -> Verifier:
        return self._verifier


class HmacVerifier(Verifier):
    alg = "hmac-sha256-dev"
    third_party_verifiable = False

    def __init__(self, secret: bytes):
        self._s = secret
        self.key_id = hashlib.sha256(b"hmac:" + secret).hexdigest()[:16]

    def verify(self, data: bytes, signature: str) -> bool:
        return hmac.compare_digest(b64(hmac.new(self._s, data, hashlib.sha256).digest()), signature)

    def public_info(self) -> dict:
        return {"key_id": self.key_id, "alg": self.alg, "note": "symmetric development key; not publishable"}


class HmacSigner(Signer):
    alg = "hmac-sha256-dev"
    third_party_verifiable = False

    def __init__(self, secret: bytes | None = None):
        self._s = secret or secrets.token_bytes(32)
        self._v = HmacVerifier(self._s)
        self.key_id = self._v.key_id

    def secret(self) -> bytes:
        return self._s

    def sign(self, data: bytes) -> str:
        return b64(hmac.new(self._s, data, hashlib.sha256).digest())

    def verifier(self) -> Verifier:
        return self._v


def load_or_create_signer(home: str | Path, prefer: str = "ed25519") -> Signer:
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    kf = home / "signing_key.json"
    if kf.exists():
        d = json.loads(kf.read_text())
        if d["alg"] == "ed25519":
            return Ed25519Signer(bytes.fromhex(d["private"]))
        return HmacSigner(bytes.fromhex(d["private"]))
    s: Signer = Ed25519Signer() if (prefer == "ed25519" and HAVE_ED25519) else HmacSigner()
    priv = s.private_raw() if isinstance(s, Ed25519Signer) else s.secret()  # type: ignore[attr-defined]
    fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"alg": s.alg, "private": priv.hex()}, f)
    (home / "public_key.json").write_text(json.dumps(s.verifier().public_info(), indent=2))
    return s


def verifier_from_info(info: dict, hmac_secret: bytes | None = None) -> Verifier:
    if info.get("alg") == "ed25519":
        if not HAVE_ED25519:
            raise RuntimeError("install 'cryptography' to verify Ed25519 signatures")
        return Ed25519Verifier.from_info(info)
    if hmac_secret is None:
        raise RuntimeError("HMAC development signatures need the shared secret to verify")
    return HmacVerifier(hmac_secret)
