# pyright: reportUnnecessaryIsInstance=false

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import httpx

from screener.config import Settings


class ConfigurationError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


JsonPayload = dict[str, object] | list[object]


class ProviderClient:
    def __init__(self, settings: Settings, provider_name: str) -> None:
        self.settings: Settings = settings
        self.provider_name: str = provider_name

    def _cache_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.settings.cache_root / self.provider_name / f"{digest}.json"

    def _write_cache(self, cache_path: Path, payload: JsonPayload) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        _ = cache_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8"
        )

    def _read_cache(self, cache_path: Path) -> JsonPayload | None:
        if not cache_path.exists():
            return None
        return cast(JsonPayload, json.loads(cache_path.read_text(encoding="utf-8")))

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | None] | None = None,
        headers: Mapping[str, str] | None = None,
        cache_key: str,
        allow_cache_fallback: bool = True,
    ) -> tuple[JsonPayload, bool]:
        cache_path = self._cache_path(cache_key)
        timeout = self.settings.http_timeout_seconds
        retries = self.settings.http_max_retries + 1
        client = httpx.Client(timeout=timeout, follow_redirects=True)
        try:
            last_error: Exception | None = None
            for attempt in range(retries):
                try:
                    response = client.get(url, params=params, headers=headers)
                    _ = response.raise_for_status()
                    payload = cast(JsonPayload, response.json())
                    self._write_cache(cache_path, payload)
                    return payload, False
                except Exception as exc:
                    last_error = exc
                    if not self._can_fallback_to_cache(exc):
                        break
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
            if allow_cache_fallback:
                cached = self._read_cache(cache_path)
                if cached is not None:
                    return cached, True
            raise ProviderError(
                f"{self.provider_name} request failed for {url}: {last_error}"
            )
        finally:
            client.close()

    def post_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | None] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, object] | list[object],
        cache_key: str,
        allow_cache_fallback: bool = True,
    ) -> tuple[JsonPayload, bool]:
        cache_path = self._cache_path(cache_key)
        timeout = self.settings.http_timeout_seconds
        retries = self.settings.http_max_retries + 1
        client = httpx.Client(timeout=timeout, follow_redirects=True)
        try:
            last_error: Exception | None = None
            for attempt in range(retries):
                try:
                    response = client.post(
                        url,
                        params=params,
                        headers=headers,
                        json=json_body,
                    )
                    _ = response.raise_for_status()
                    payload = cast(JsonPayload, response.json())
                    self._write_cache(cache_path, payload)
                    return payload, False
                except Exception as exc:
                    last_error = exc
                    if not self._can_fallback_to_cache(exc):
                        break
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
            if allow_cache_fallback:
                cached = self._read_cache(cache_path)
                if cached is not None:
                    return cached, True
            raise ProviderError(
                f"{self.provider_name} request failed for {url}: {last_error}"
            )
        finally:
            client.close()

    def _can_fallback_to_cache(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            return status == 429 or status >= 500
        return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
