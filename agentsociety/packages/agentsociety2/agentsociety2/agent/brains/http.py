"""HTTP transport shared by the model and decision adapters."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class BackendHTTPError(RuntimeError):
    def __init__(self, status: int) -> None:
        super().__init__(f"agent backend HTTP {status}")
        self.status = status


async def post_json(url: str, api_key: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=timeout_s, ceil_threshold=float("inf"))
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with asyncio.timeout(timeout_s if timeout_s > 0 else None), aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(2):
                try:
                    response = await session.post(url, json=payload, headers=headers, allow_redirects=False)
                    break
                except aiohttp.ClientConnectorError as exc:
                    # A connection failure happens before the provider receives the POST.
                    if attempt or isinstance(exc, aiohttp.ClientSSLError):
                        raise
                    await asyncio.sleep(0.1)
            async with response:
                if not 200 <= response.status < 300:
                    raise BackendHTTPError(response.status)
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        raise RuntimeError(f"agent backend response failed: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise RuntimeError("agent backend response is not an object")
    return data
