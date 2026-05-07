from __future__ import annotations

import hashlib


def url_to_id(url: str) -> int:
    return int(hashlib.md5(url.encode()).hexdigest()[:16], 16)
