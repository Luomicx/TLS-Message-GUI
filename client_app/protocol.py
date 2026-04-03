from __future__ import annotations

import json
from typing import Any


def encode_request(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def decode_response(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="strict").strip()
    if not text:
        raise ValueError("empty response")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("response must be object")
    return payload
