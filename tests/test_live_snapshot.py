# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from pathlib import Path

import pytest

from screener.config import Settings
from screener.io import load_snapshot
from screener.models import MacroSnapshot, SecuritySnapshot
from screener.providers.base import ProviderError
from screener.providers.live_snapshot import build_live_snapshot


def _fixture_securities() -> dict[str, SecuritySnapshot]:
    snapshot = load_snapshot(Path("tests/fixtures/base_snapshot.json"))
    return {security.symbol: security for security in snapshot.securities}


def _fixture_macro() -> MacroSnapshot:
    snapshot = load_snapshot(Path("tests/fixtures/base_snapshot.json"))
    return snapshot.macro


def test_live_snapshot_falls_back_when_fmp_universe_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    securities = _fixture_securities()
    macro = _fixture_macro()

    def fake_get_universe(_self: object) -> tuple[list[str], list[str]]:
        raise ProviderError("402 Payment Required")

    def fake_get_ticker_map(_self: object) -> tuple[dict[str, str], list[str]]:
        return ({symbol: f"{index:010d}" for index, symbol in enumerate(securities, start=1)}, [])

    def fake_build_macro_snapshot(
        _self: object, _as_of: str
    ) -> tuple[MacroSnapshot, list[str]]:
        return (macro, [])

    def fake_build_security_snapshot(
        _self: object, symbol: str
    ) -> tuple[SecuritySnapshot, list[str]]:
        return (securities[symbol], [])

    def fake_get_stale_days(_self: object, _cik: str, _as_of: str) -> tuple[int, bool]:
        return (3, False)

    monkeypatch.setattr("screener.providers.live_snapshot.FMPClient.get_universe", fake_get_universe)
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_ticker_map", fake_get_ticker_map
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FREDClient.build_macro_snapshot",
        fake_build_macro_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.build_security_snapshot",
        fake_build_security_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_stale_days", fake_get_stale_days
    )

    settings = Settings(
        pdf_enabled=False,
        fmp_fallback_symbols=tuple(securities.keys()),
        sec_api_key=None,
    )
    result = build_live_snapshot(settings, as_of="2026-03-13")

    assert len(result.snapshot.securities) == len(settings.fmp_fallback_symbols)
    assert result.data_sources[0] == "symbols:fallback"
    assert any("used fallback symbol list" in warning for warning in result.warnings)


def test_live_snapshot_uses_symbols_file_before_fmp_universe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    securities = _fixture_securities()
    macro = _fixture_macro()
    symbols_path = tmp_path / "symbols.txt"
    _ = symbols_path.write_text("MSFT\nGOOGL\nMETA\nV\nTXN\nCELH\n", encoding="utf-8")

    def fail_get_universe(_self: object) -> tuple[list[str], list[str]]:
        raise AssertionError("FMP universe should not be called when symbols_file is provided")

    def fake_get_ticker_map(_self: object) -> tuple[dict[str, str], list[str]]:
        return ({symbol: f"{index:010d}" for index, symbol in enumerate(securities, start=1)}, [])

    def fake_build_macro_snapshot(
        _self: object, _as_of: str
    ) -> tuple[MacroSnapshot, list[str]]:
        return (macro, [])

    def fake_build_security_snapshot(
        _self: object, symbol: str
    ) -> tuple[SecuritySnapshot, list[str]]:
        return (securities[symbol], [])

    def fake_get_stale_days(_self: object, _cik: str, _as_of: str) -> tuple[int, bool]:
        return (3, False)

    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.get_universe", fail_get_universe
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_ticker_map", fake_get_ticker_map
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FREDClient.build_macro_snapshot",
        fake_build_macro_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.build_security_snapshot",
        fake_build_security_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_stale_days", fake_get_stale_days
    )

    settings = Settings(pdf_enabled=False, sec_api_key=None)
    result = build_live_snapshot(settings, as_of="2026-03-13", symbols_file=symbols_path)

    assert len(result.snapshot.securities) == 6
    assert result.data_sources[0] == f"symbols_file:{symbols_path.as_posix()}"
    assert all("fallback symbol list" not in warning for warning in result.warnings)


def test_live_snapshot_continues_when_sec_ticker_map_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    securities = _fixture_securities()
    macro = _fixture_macro()

    def fake_get_universe(_self: object) -> tuple[list[str], list[str]]:
        return (list(securities.keys()), [])

    def fail_get_ticker_map(_self: object) -> tuple[dict[str, str], list[str]]:
        raise ProviderError("403 Forbidden")

    def fake_build_macro_snapshot(
        _self: object, _as_of: str
    ) -> tuple[MacroSnapshot, list[str]]:
        return (macro, [])

    def fake_build_security_snapshot(
        _self: object, symbol: str
    ) -> tuple[SecuritySnapshot, list[str]]:
        return (securities[symbol].model_copy(deep=True), [])

    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.get_universe", fake_get_universe
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_ticker_map", fail_get_ticker_map
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FREDClient.build_macro_snapshot",
        fake_build_macro_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.build_security_snapshot",
        fake_build_security_snapshot,
    )

    settings = Settings(pdf_enabled=False, sec_api_key=None)
    result = build_live_snapshot(settings, as_of="2026-03-13")

    assert len(result.snapshot.securities) == len(securities)
    assert "sec:unavailable" in result.data_sources
    assert any("SEC ticker map unavailable" in warning for warning in result.warnings)
    assert all(item.stale_days == settings.stale_days_limit for item in result.snapshot.securities)
    assert all(item.data_quality_score == 0.6 for item in result.snapshot.securities)


def test_live_snapshot_continues_when_sec_submission_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    securities = _fixture_securities()
    macro = _fixture_macro()

    def fake_get_universe(_self: object) -> tuple[list[str], list[str]]:
        return (list(securities.keys()), [])

    def fake_get_ticker_map(_self: object) -> tuple[dict[str, str], list[str]]:
        return ({symbol: f"{index:010d}" for index, symbol in enumerate(securities, start=1)}, [])

    def fake_build_macro_snapshot(
        _self: object, _as_of: str
    ) -> tuple[MacroSnapshot, list[str]]:
        return (macro, [])

    def fake_build_security_snapshot(
        _self: object, symbol: str
    ) -> tuple[SecuritySnapshot, list[str]]:
        return (securities[symbol].model_copy(deep=True), [])

    def fail_get_stale_days(_self: object, _cik: str, _as_of: str) -> tuple[int, bool]:
        raise ProviderError("403 Forbidden")

    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.get_universe", fake_get_universe
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_ticker_map", fake_get_ticker_map
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FREDClient.build_macro_snapshot",
        fake_build_macro_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.build_security_snapshot",
        fake_build_security_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_stale_days", fail_get_stale_days
    )

    settings = Settings(pdf_enabled=False, sec_api_key=None)
    result = build_live_snapshot(settings, as_of="2026-03-13")

    assert len(result.snapshot.securities) == len(securities)
    assert any("SEC freshness unavailable" in warning for warning in result.warnings)
    assert all(item.stale_days == settings.stale_days_limit for item in result.snapshot.securities)
    assert all(item.data_quality_score == 0.6 for item in result.snapshot.securities)


def test_live_snapshot_uses_sec_api_when_sec_ticker_map_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    securities = _fixture_securities()
    macro = _fixture_macro()

    def fake_get_universe(_self: object) -> tuple[list[str], list[str]]:
        return (list(securities.keys()), [])

    def fail_get_ticker_map(_self: object) -> tuple[dict[str, str], list[str]]:
        raise ProviderError("403 Forbidden")

    def fake_build_macro_snapshot(
        _self: object, _as_of: str
    ) -> tuple[MacroSnapshot, list[str]]:
        return (macro, [])

    def fake_build_security_snapshot(
        _self: object, symbol: str
    ) -> tuple[SecuritySnapshot, list[str]]:
        return (securities[symbol].model_copy(deep=True), [])

    def fake_sec_api_stale_days(
        _self: object, _symbol: str, _as_of: str
    ) -> tuple[int, bool]:
        return (12, False)

    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.get_universe", fake_get_universe
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECClient.get_ticker_map", fail_get_ticker_map
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FREDClient.build_macro_snapshot",
        fake_build_macro_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.FMPClient.build_security_snapshot",
        fake_build_security_snapshot,
    )
    monkeypatch.setattr(
        "screener.providers.live_snapshot.SECAPIClient.get_stale_days_for_symbol",
        fake_sec_api_stale_days,
    )

    settings = Settings(pdf_enabled=False, sec_api_key="test-sec-api")
    result = build_live_snapshot(settings, as_of="2026-03-13")

    assert len(result.snapshot.securities) == len(securities)
    assert "sec-api" in result.data_sources
    assert all(item.stale_days == 12 for item in result.snapshot.securities)
    assert all(item.data_quality_score == 0.9 for item in result.snapshot.securities)
