# pyright: reportMissingTypeStubs=false

from pathlib import Path

import pytest

from screener.config import Settings
from screener.io import load_snapshot
from screener.models import ArtifactMode, InputSnapshot
from screener.pipeline import run_live
from screener.providers.base import ConfigurationError, ProviderError
from screener.providers.live_snapshot import LiveSnapshotResult


def _base_snapshot() -> InputSnapshot:
    return load_snapshot(Path("tests/fixtures/base_snapshot.json"))


def test_live_pipeline_uses_built_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot = _base_snapshot()

    def fake_build_live_snapshot(*_args: object, **_kwargs: object) -> LiveSnapshotResult:
        return LiveSnapshotResult(
            snapshot=snapshot,
            data_sources=["fmp", "sec", "fred"],
            warnings=["cached macro"],
        )

    monkeypatch.setattr(
        "screener.pipeline.build_live_snapshot", fake_build_live_snapshot
    )
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    batch = run_live(tmp_path, settings)
    manifest = (tmp_path / "run_manifest.json").read_text(encoding="utf-8")
    assert len(batch.recommendations) == 6
    assert (tmp_path / "dashboard.html").exists()
    assert '"mode": "live"' in manifest
    assert "dashboard.html" in manifest
    assert '"data_sources": [' in manifest
    assert '"cached macro"' in manifest


def test_missing_secret_live_mode_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_build_live_snapshot(*_args: object, **_kwargs: object) -> LiveSnapshotResult:
        raise ConfigurationError("SCREENER_FMP_API_KEY is required for live mode")

    monkeypatch.setattr(
        "screener.pipeline.build_live_snapshot", fake_build_live_snapshot
    )
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    with pytest.raises(ConfigurationError):
        _ = run_live(tmp_path, settings)


def test_provider_timeout_with_cache_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot = _base_snapshot()

    def fake_build_live_snapshot(*_args: object, **_kwargs: object) -> LiveSnapshotResult:
        return LiveSnapshotResult(
            snapshot=snapshot,
            data_sources=["fmp", "sec", "fred"],
            warnings=["FMP universe served from cache"],
        )

    monkeypatch.setattr(
        "screener.pipeline.build_live_snapshot", fake_build_live_snapshot
    )
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    _ = run_live(tmp_path, settings)
    manifest = (tmp_path / "run_manifest.json").read_text(encoding="utf-8")
    assert "FMP universe served from cache" in manifest


def test_provider_timeout_without_cache_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_build_live_snapshot(*_args: object, **_kwargs: object) -> LiveSnapshotResult:
        raise ProviderError("FMP request failed without cache")

    monkeypatch.setattr(
        "screener.pipeline.build_live_snapshot", fake_build_live_snapshot
    )
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    with pytest.raises(ProviderError):
        _ = run_live(tmp_path, settings)


def test_insufficient_candidates_after_provider_drop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    snapshot = _base_snapshot()
    snapshot.securities = snapshot.securities[:5]

    def fake_build_live_snapshot(*_args: object, **_kwargs: object) -> LiveSnapshotResult:
        return LiveSnapshotResult(
            snapshot=snapshot, data_sources=["fmp", "sec", "fred"], warnings=[]
        )

    monkeypatch.setattr(
        "screener.pipeline.build_live_snapshot", fake_build_live_snapshot
    )
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    with pytest.raises(Exception):
        _ = run_live(tmp_path, settings)
