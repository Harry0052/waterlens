"""Configuration ids. The hash names a seed and a split, not a score."""

import hashlib
import json


def config_hash(payload: dict) -> str:
    body = {key: payload[key] for key in payload if key != "config_hash"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
