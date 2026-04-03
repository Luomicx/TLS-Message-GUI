from __future__ import annotations

import base64
import json
from typing import Any


def decode_request_line(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="strict").strip()
    if not text:
        raise ValueError("empty request")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("request must be object")
    action = payload.get("action")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action is required")
    payload["action"] = action.strip()
    return payload


def encode_response_line(
    *, ok: bool, code: str, message: str, data: dict[str, Any] | None = None
) -> bytes:
    payload = {
        "ok": bool(ok),
        "code": code,
        "message": message,
        "data": data or {},
    }
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def encode_sensitive_text(text: str, rule: list[str]) -> str:
    data = text.encode("utf-8")
    for token in rule:
        if token == "base64":
            data = base64.b64encode(data)
        elif token == "hex":
            data = data.hex().encode("ascii")
        elif token == "caesar":
            shifted = bytes((byte + 3) % 256 for byte in data)
            data = shifted
    return data.decode("utf-8", errors="ignore")


def decode_sensitive_text(text: str, rule: list[str]) -> str:
    data = text.encode("utf-8")
    for token in reversed(rule):
        if token == "base64":
            data = base64.b64decode(data)
        elif token == "hex":
            data = bytes.fromhex(data.decode("ascii"))
        elif token == "caesar":
            data = bytes((byte - 3) % 256 for byte in data)
    return data.decode("utf-8")
