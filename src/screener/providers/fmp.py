# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnnecessaryIsInstance=false

from __future__ import annotations

from collections.abc import Mapping

from screener.config import Settings
from screener.models import SecuritySnapshot

from .base import ConfigurationError, ProviderClient, ProviderError


def _pick_float(
    data: Mapping[str, object], keys: list[str], default: float = 0.0
) -> float:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return default


def _pick_str(data: Mapping[str, object], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def _pick_inverse_ratio(
    data: Mapping[str, object], keys: list[str], default: float = 0.0
) -> float:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)) and float(value) > 0:
            return 1.0 / float(value)
    return default


class FMPClient(ProviderClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.fmp_api_key:
            raise ConfigurationError("SCREENER_FMP_API_KEY is required for live mode")
        super().__init__(settings, "fmp")

    def get_universe(self) -> tuple[list[str], list[str]]:
        warnings: list[str] = []
        api_key = self.settings.fmp_api_key
        if api_key is None:
            raise ConfigurationError("SCREENER_FMP_API_KEY is required for live mode")
        payload, cached = self.get_json(
            f"{self.settings.fmp_base_url}/company-screener",
            params={
                "marketCapMoreThan": int(self.settings.min_market_cap_risky),
                "limit": self.settings.fmp_universe_limit,
                "apikey": api_key,
            },
            cache_key=f"company-screener:{self.settings.fmp_universe_limit}",
        )
        if cached:
            warnings.append("FMP universe served from cache")
        rows: list[Mapping[str, object]] = (
            [row for row in payload if isinstance(row, Mapping)]
            if isinstance(payload, list)
            else []
        )
        symbols = [row.get("symbol") for row in rows]
        return [
            symbol for symbol in symbols if isinstance(symbol, str) and symbol
        ], warnings

    def build_security_snapshot(
        self, symbol: str
    ) -> tuple[SecuritySnapshot, list[str]]:
        warnings: list[str] = []
        api_key = self.settings.fmp_api_key
        if api_key is None:
            raise ConfigurationError("SCREENER_FMP_API_KEY is required for live mode")
        base_params: dict[str, str] = {"symbol": symbol, "apikey": api_key}
        profile_payload, cached_profile = self.get_json(
            f"{self.settings.fmp_base_url}/profile",
            params=base_params,
            cache_key=f"profile:{symbol}",
        )
        ratios_payload, cached_ratios = self.get_json(
            f"{self.settings.fmp_base_url}/ratios-ttm",
            params=base_params,
            cache_key=f"ratios-ttm:{symbol}",
        )
        growth_payload, cached_growth = self.get_json(
            f"{self.settings.fmp_base_url}/financial-growth",
            params=base_params,
            cache_key=f"financial-growth:{symbol}",
        )
        if cached_profile:
            warnings.append(f"FMP profile cached for {symbol}")
        if cached_ratios:
            warnings.append(f"FMP ratios cached for {symbol}")
        if cached_growth:
            warnings.append(f"FMP growth cached for {symbol}")

        if not isinstance(profile_payload, list) or not profile_payload:
            raise ProviderError(f"FMP profile payload missing for {symbol}")
        if not isinstance(ratios_payload, list) or not ratios_payload:
            raise ProviderError(f"FMP ratios payload missing for {symbol}")
        if not isinstance(growth_payload, list) or not growth_payload:
            raise ProviderError(f"FMP growth payload missing for {symbol}")

        profile = (
            profile_payload[0]
            if isinstance(profile_payload, list)
            and profile_payload
            and isinstance(profile_payload[0], dict)
            else {}
        )
        ratios = (
            ratios_payload[0]
            if isinstance(ratios_payload, list)
            and ratios_payload
            and isinstance(ratios_payload[0], dict)
            else {}
        )
        growth = (
            growth_payload[0]
            if isinstance(growth_payload, list)
            and growth_payload
            and isinstance(growth_payload[0], dict)
            else {}
        )
        if (
            not isinstance(profile, dict)
            or not isinstance(ratios, dict)
            or not isinstance(growth, dict)
        ):
            raise ProviderError(f"FMP returned malformed data for {symbol}")

        price = _pick_float(profile, ["price"])
        target_price = _pick_float(
            profile, ["priceTargetAverage", "priceTargetConsensus"], price
        )
        analyst_upside = (
            ((target_price - price) / price) if price > 0 and target_price > 0 else 0.0
        )
        if price <= 0:
            raise ProviderError(f"FMP returned non-positive price for {symbol}")
        fcf_yield = _pick_float(
            ratios,
            ["freeCashFlowYieldTTM", "freeCashFlowYield", "fcfYieldTTM", "fcfYield"],
        )
        if fcf_yield <= 0:
            fcf_yield = _pick_inverse_ratio(
                ratios,
                ["priceToFreeCashFlowRatioTTM", "priceToFreeCashFlowRatio"],
            )
        if fcf_yield > 1.0:
            fcf_yield /= 100.0
        pe_ratio = _pick_float(
            ratios,
            ["peRatioTTM", "priceEarningsRatioTTM", "priceToEarningsRatioTTM"],
        )
        earnings_yield = _pick_float(ratios, ["earningsYieldTTM", "earningsYield"])
        if earnings_yield <= 0:
            earnings_yield = _pick_inverse_ratio(
                ratios,
                ["priceToEarningsRatioTTM", "priceEarningsRatioTTM", "peRatioTTM"],
            )
        security = SecuritySnapshot(
            symbol=symbol,
            name=_pick_str(profile, ["companyName", "name"], symbol),
            sector=_pick_str(profile, ["sector"], "Unknown"),
            industry=_pick_str(profile, ["industry"], "Unknown"),
            market_cap=_pick_float(profile, ["mktCap", "marketCap"]),
            price=price,
            revenue_growth_yoy=_pick_float(
                growth, ["revenueGrowth", "growthRevenue", "revenueGrowthTTM"]
            ),
            fcf_growth_yoy=_pick_float(
                growth, ["freeCashFlowGrowth", "growthFreeCashFlow"]
            ),
            ebit_margin=_pick_float(
                ratios,
                ["operatingProfitMarginTTM", "ebitMarginTTM", "operatingMarginTTM"],
            ),
            gross_margin=_pick_float(
                ratios, ["grossProfitMarginTTM", "grossMarginTTM"]
            ),
            debt_to_equity=_pick_float(
                ratios, ["debtEquityRatioTTM", "debtToEquityTTM"]
            ),
            current_ratio=_pick_float(ratios, ["currentRatioTTM", "currentRatio"]),
            fcf_yield=fcf_yield,
            ev_to_ebit=_pick_float(
                ratios,
                [
                    "enterpriseValueOverEBITDATTM",
                    "evToEbitTTM",
                    "enterpriseValueOverEBIT",
                    "enterpriseValueMultipleTTM",
                ],
            ),
            pe_ratio=pe_ratio,
            earnings_yield=earnings_yield,
            roic=_pick_float(ratios, ["returnOnInvestedCapitalTTM", "roicTTM", "roic"]),
            beta=_pick_float(profile, ["beta"], 1.0),
            analyst_upside=analyst_upside,
        )
        return security, warnings
