from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from screener.config import Settings
from screener.models import InputSnapshot, SecuritySnapshot

from .base import ProviderError
from .fmp import FMPClient
from .fred import FREDClient
from .sec import SECAPIClient, SECClient


@dataclass
class LiveSnapshotResult:
    snapshot: InputSnapshot
    data_sources: list[str]
    warnings: list[str]


def _load_symbols_override(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    lines = [
        line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines()
    ]
    symbols = [line for line in lines if line and not line.startswith("#")]
    return symbols or None


def _fallback_symbols(settings: Settings) -> list[str]:
    return [symbol.upper() for symbol in settings.fmp_fallback_symbols if symbol.strip()]


def _apply_sec_fallback(
    security: SecuritySnapshot, settings: Settings, warnings: list[str], reason: str
) -> None:
    security.stale_days = settings.stale_days_limit
    security.data_quality_score = 0.6
    warnings.append(
        f"SEC freshness unavailable for {security.symbol}; used degraded fallback. Reason: {reason}"
    )


def _apply_filing_signal(
    security: SecuritySnapshot,
    stale_days: int,
    settings: Settings,
    *,
    fresh_quality: float,
    stale_quality: float,
) -> None:
    effective_stale_days = stale_days
    if settings.stale_days_limit < stale_days <= (
        settings.stale_days_limit + settings.filing_freshness_grace_days
    ):
        effective_stale_days = settings.stale_days_limit
    security.stale_days = effective_stale_days
    security.data_quality_score = (
        stale_quality
        if effective_stale_days > settings.stale_days_limit
        else fresh_quality
    )


def build_live_snapshot(
    settings: Settings,
    *,
    as_of: str | None = None,
    symbols_file: Path | None = None,
    fail_on_provider_error: bool = False,
) -> LiveSnapshotResult:
    run_as_of = as_of or date.today().isoformat()
    fmp = FMPClient(settings)
    sec = SECClient(settings) if settings.sec_user_agent else None
    sec_api = SECAPIClient(settings) if settings.sec_api_key else None
    fred = FREDClient(settings)

    warnings: list[str] = []
    symbol_override = _load_symbols_override(symbols_file)
    sec_source = "sec" if sec is not None else ("sec-api" if sec_api is not None else "sec:unavailable")
    data_sources = ["fmp", sec_source, "fred"]
    ticker_map: dict[str, str] = {}
    sec_warnings: list[str] = []
    sec_available = sec is not None
    symbols: list[str]
    if symbol_override is not None:
        symbols = symbol_override
        symbols_source_path = symbols_file if symbols_file is not None else Path("<inline>")
        data_sources.insert(0, f"symbols_file:{symbols_source_path.as_posix()}")
    else:
        try:
            symbols, universe_warnings = fmp.get_universe()
            warnings.extend(universe_warnings)
        except ProviderError as exc:
            symbols = _fallback_symbols(settings)
            if not symbols:
                raise
            warnings.append(
                f"FMP universe endpoint unavailable; used fallback symbol list. Reason: {exc}"
            )
            data_sources.insert(0, "symbols:fallback")

    if sec is not None:
        try:
            ticker_map, ticker_warnings = sec.get_ticker_map()
            warnings.extend(ticker_warnings)
        except Exception as exc:
            sec_available = False
            data_sources = ["sec-api" if item == "sec" and sec_api is not None else item for item in data_sources]
            data_sources = ["sec:unavailable" if item == "sec" and sec_api is None else item for item in data_sources]
            sec_warnings.append(
                f"SEC ticker map unavailable; continuing with fallback filing-freshness source. Reason: {exc}"
            )
            warnings.extend(sec_warnings)
    macro, macro_warnings = fred.build_macro_snapshot(run_as_of)
    warnings.extend(macro_warnings)

    securities: list[SecuritySnapshot] = []
    failures: list[str] = []
    for symbol in symbols:
        try:
            security, symbol_warnings = fmp.build_security_snapshot(symbol)
            warnings.extend(symbol_warnings)
            if sec_available:
                cik = ticker_map.get(symbol.upper())
                if cik is None:
                    if sec_api is not None:
                        stale_days, stale_cached = sec_api.get_stale_days_for_symbol(
                            symbol, run_as_of
                        )
                        _apply_filing_signal(
                            security,
                            stale_days,
                            settings,
                            fresh_quality=0.9,
                            stale_quality=0.65,
                        )
                        if stale_cached:
                            warnings.append(f"sec-api filings cached for {symbol}")
                    else:
                        _apply_sec_fallback(
                            security,
                            settings,
                            warnings,
                            "CIK mapping missing",
                        )
                else:
                    try:
                        if sec is None:
                            raise ProviderError("SEC client unavailable")
                        stale_days, stale_cached = sec.get_stale_days(cik, run_as_of)
                        _apply_filing_signal(
                            security,
                            stale_days,
                            settings,
                            fresh_quality=0.95,
                            stale_quality=0.65,
                        )
                        if stale_cached:
                            warnings.append(f"SEC submissions cached for {symbol}")
                    except Exception as exc:
                        if sec_api is not None:
                            stale_days, stale_cached = sec_api.get_stale_days_for_symbol(
                                symbol, run_as_of
                            )
                            _apply_filing_signal(
                                security,
                                stale_days,
                                settings,
                                fresh_quality=0.9,
                                stale_quality=0.65,
                            )
                            warnings.append(
                                f"SEC freshness lookup failed for {symbol}; used sec-api fallback. Reason: {exc}"
                            )
                            if stale_cached:
                                warnings.append(f"sec-api filings cached for {symbol}")
                        else:
                            _apply_sec_fallback(security, settings, warnings, str(exc))
            elif sec_api is not None:
                stale_days, stale_cached = sec_api.get_stale_days_for_symbol(symbol, run_as_of)
                _apply_filing_signal(
                    security,
                    stale_days,
                    settings,
                    fresh_quality=0.9,
                    stale_quality=0.65,
                )
                if stale_cached:
                    warnings.append(f"sec-api filings cached for {symbol}")
            else:
                _apply_sec_fallback(
                    security,
                    settings,
                    warnings,
                    "ticker map unavailable",
                )
            securities.append(security)
        except Exception as exc:
            message = f"Live enrichment failed for {symbol}: {exc}"
            failures.append(message)
            if fail_on_provider_error:
                raise ProviderError(message) from exc
    warnings.extend(failures)
    if len(securities) < 6:
        raise ProviderError(
            "Live snapshot could not retain enough securities to produce exactly 6 recommendations"
        )
    snapshot = InputSnapshot(
        as_of=run_as_of,
        generated_at=datetime.now(timezone.utc),
        macro=macro,
        securities=securities,
    )
    return LiveSnapshotResult(snapshot=snapshot, data_sources=data_sources, warnings=warnings)
