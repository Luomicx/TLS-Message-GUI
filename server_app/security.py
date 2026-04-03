from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass


PBKDF2_ITERS = 120_000
SALT_BYTES = 16
DKLEN = 32


@dataclass(frozen=True)
class PasswordHash:
    salt: bytes
    digest: bytes


def hash_password(password: str) -> PasswordHash:
    if password is None:
        raise ValueError("password is required")
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERS, dklen=DKLEN
    )
    return PasswordHash(salt=salt, digest=digest)


def verify_password(password: str, salt: bytes, digest: bytes) -> bool:
    new_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERS, dklen=len(digest)
    )
    return hmac.compare_digest(new_digest, digest)
