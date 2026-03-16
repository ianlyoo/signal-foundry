# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from collections.abc import Mapping

from screener.config import Settings
from screener.models import MacroSnapshot

from .base import ConfigurationError, ProviderClient


class FREDClient(ProviderClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.fred_api_key:
            raise ConfigurationError("SCREENER_FRED_API_KEY is required for live mode")
        super().__init__(settings, "fred")

    def _latest_value(self, series_id: str, as_of: str) -> tuple[float, bool]:
        api_key = self.settings.fred_api_key
        if api_key is None:
            raise ConfigurationError("SCREENER_FRED_API_KEY is required for live mode")
        payload, cached = self.get_json(
            f"{self.settings.fred_base_url}/series/observations",
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "observation_end": as_of,
                "limit": 10,
            },
            cache_key=f"series:{series_id}:{as_of}",
        )
        if not isinstance(payload, Mapping):
            raise ValueError(f"FRED payload malformed for {series_id}")
        rows = payload.get("observations")
        if not isinstance(rows, list):
            raise ValueError(f"FRED observations missing for {series_id}")
        for row in rows:
            if isinstance(row, Mapping):
                value = row.get("value")
                if isinstance(value, str) and value not in {".", ""}:
                    return float(value), cached
        raise ValueError(f"FRED returned no usable value for {series_id}")

    def build_macro_snapshot(self, as_of: str) -> tuple[MacroSnapshot, list[str]]:
        warnings: list[str] = []
        policy_rate, cached_policy = self._latest_value(
            self.settings.fred_series_policy_rate, as_of
        )
        inflation, cached_inflation = self._latest_value(
            self.settings.fred_series_inflation, as_of
        )
        unemployment, cached_unemployment = self._latest_value(
            self.settings.fred_series_unemployment, as_of
        )
        credit_spread, cached_credit = self._latest_value(
            self.settings.fred_series_credit_spread, as_of
        )
        gdp_growth, cached_gdp = self._latest_value(
            self.settings.fred_series_gdp_growth, as_of
        )
        if cached_policy:
            warnings.append("FRED policy rate served from cache")
        if cached_inflation:
            warnings.append("FRED inflation served from cache")
        if cached_unemployment:
            warnings.append("FRED unemployment served from cache")
        if cached_credit:
            warnings.append("FRED credit spread served from cache")
        if cached_gdp:
            warnings.append("FRED GDP growth served from cache")
        return (
            MacroSnapshot(
                policy_rate=policy_rate,
                inflation_yoy=inflation,
                unemployment_rate=unemployment,
                credit_spread=credit_spread,
                gdp_growth=gdp_growth,
            ),
            warnings,
        )
