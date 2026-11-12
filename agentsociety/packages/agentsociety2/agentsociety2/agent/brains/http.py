"""HTTP transport shared by the model and decision adapters."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


async def post_json(url: str, api_key: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=timeout_s, ceil_threshold=float("inf"))
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers, allow_redirects=False) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"agent backend HTTP {response.status}")
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        raise RuntimeError(f"agent backend response failed: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise RuntimeError("agent backend response is not an object")
    return data
