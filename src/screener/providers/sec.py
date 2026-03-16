# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

from datetime import date, datetime

from screener.config import Settings

from .base import ConfigurationError, ProviderClient


class SECClient(ProviderClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.sec_user_agent:
            raise ConfigurationError(
                "SCREENER_SEC_USER_AGENT is required for live mode"
            )
        super().__init__(settings, "sec")

    @property
    def _headers(self) -> dict[str, str]:
        user_agent = self.settings.sec_user_agent
        if user_agent is None:
            raise ConfigurationError(
                "SCREENER_SEC_USER_AGENT is required for live mode"
            )
        return {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    def get_ticker_map(self) -> tuple[dict[str, str], list[str]]:
        warnings: list[str] = []
        payload, cached = self.get_json(
            self.settings.sec_company_tickers_url,
            headers=self._headers,
            cache_key="company_tickers",
        )
        if cached:
            warnings.append("SEC ticker map served from cache")
        if not isinstance(payload, dict):
            raise ValueError("SEC ticker map payload is malformed")
        mapping: dict[str, str] = {}
        for row in payload.values():
            if isinstance(row, dict):
                ticker = row.get("ticker")
                cik = row.get("cik_str")
                if isinstance(ticker, str) and isinstance(cik, int):
                    mapping[ticker.upper()] = f"{cik:010d}"
        return mapping, warnings

    def get_stale_days(self, cik: str, as_of: str) -> tuple[int, bool]:
        payload, cached = self.get_json(
            f"{self.settings.sec_base_url}/submissions/CIK{cik}.json",
            headers=self._headers,
            cache_key=f"submissions:{cik}",
        )
        if not isinstance(payload, dict):
            return 999, cached
        filings = payload.get("filings")
        recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
        forms = recent.get("form", []) if isinstance(recent, dict) else []
        dates = recent.get("filingDate", []) if isinstance(recent, dict) else []
        filing_date: str | None = None
        if isinstance(forms, list) and isinstance(dates, list):
            for form, dt in zip(forms, dates):
                if form in {"10-K", "10-Q", "20-F", "40-F"} and isinstance(dt, str):
                    filing_date = dt
                    break
        if filing_date is None:
            return 999, cached
        as_of_date = date.fromisoformat(as_of)
        filing_dt = date.fromisoformat(filing_date)
        return max((as_of_date - filing_dt).days, 0), cached


class SECAPIClient(ProviderClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.sec_api_key:
            raise ConfigurationError("SCREENER_SEC_API_KEY is required for sec-api mode")
        super().__init__(settings, "sec_api")

    def get_stale_days_for_symbol(self, symbol: str, as_of: str) -> tuple[int, bool]:
        api_key = self.settings.sec_api_key
        if api_key is None:
            raise ConfigurationError("SCREENER_SEC_API_KEY is required for sec-api mode")
        payload = {
            "query": f'ticker:{symbol.upper()} AND formType:("10-K" OR "10-Q" OR "20-F" OR "40-F")',
            "from": "0",
            "size": "1",
            "sort": [{"filedAt": {"order": "desc"}}],
        }
        response, cached = self.post_json(
            self.settings.sec_api_base_url,
            params={"token": api_key},
            json_body=payload,
            cache_key=f"latest-filings:{symbol.upper()}",
        )
        if not isinstance(response, dict):
            raise ValueError("sec-api filings payload is malformed")
        filings = response.get("filings")
        if not isinstance(filings, list) or not filings:
            raise ValueError(f"sec-api returned no qualifying filings for {symbol}")
        latest = filings[0]
        if not isinstance(latest, dict):
            raise ValueError("sec-api filing payload is malformed")
        filed_at = latest.get("filedAt")
        if not isinstance(filed_at, str):
            raise ValueError("sec-api filing date missing")
        filing_dt = datetime.fromisoformat(filed_at).date()
        as_of_date = date.fromisoformat(as_of)
        return max((as_of_date - filing_dt).days, 0), cached
