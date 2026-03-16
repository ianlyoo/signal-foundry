# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false

import json
from pathlib import Path
from typing import cast

import pytest

from screener.config import Settings
from screener.models import ArtifactMode, EvidenceItem, LLMMode, RationaleOutput
from screener.pipeline import run_offline
from screener.scoring import ScoredSecurity


def test_offline_pipeline_generates_six_recommendations(tmp_path: Path) -> None:
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    batch = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)
    assert len(batch.recommendations) == 6
    assert [item.rank for item in batch.recommendations] == [1, 2, 3, 4, 5, 6]
    assert {item.bucket.value for item in batch.recommendations} == {
        "safer_growth",
        "higher_risk_higher_growth",
    }
    assert (tmp_path / "recommendations.json").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "dashboard.html").exists()
    manifest = (tmp_path / "run_manifest.json").read_text(encoding="utf-8")
    assert "dashboard.html" in manifest


def test_rationale_evidence_refs_are_grounded(tmp_path: Path) -> None:
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.FULL)
    batch = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)
    for item in batch.recommendations:
        valid_refs = {entry.evidence_id for entry in item.evidence}
        assert set(item.rationale.evidence_refs).issubset(valid_refs)


def test_gemini_mode_uses_gemini_rationale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_call_gemini(
        item: ScoredSecurity, evidence: list[EvidenceItem], _settings: Settings
    ) -> RationaleOutput:
        return RationaleOutput(
            text=f"{item.security.symbol} gemini rationale",
            key_reasons=["Reason one", "Reason two"],
            primary_risks=["Risk one", "Risk two"],
            watch_items=["Watch one", "Watch two"],
            evidence_refs=[evidence[0].evidence_id, evidence[1].evidence_id],
            source_mode="gemini",
            requested_mode="gemini",
            model_name=settings.gemini_model,
        )

    monkeypatch.setattr("screener.rationale._call_gemini", fake_call_gemini)
    settings = Settings(
        pdf_enabled=False,
        artifact_mode=ArtifactMode.FULL,
        llm_mode=LLMMode.GEMINI,
        gemini_api_key="test-key",
    )
    batch = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)
    assert batch.model_version == settings.gemini_model
    assert all(item.rationale.source_mode == "gemini" for item in batch.recommendations)


def test_gemini_mode_without_key_surfaces_template_warning(tmp_path: Path) -> None:
    settings = Settings(
        pdf_enabled=False,
        artifact_mode=ArtifactMode.FULL,
        llm_mode=LLMMode.GEMINI,
    )
    settings.gemini_api_key = None
    _ = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)
    manifest = cast(
        dict[str, object],
        json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8")),
    )
    assert manifest["requested_llm_mode"] == "gemini"
    warnings = cast(list[str], manifest["warnings"])
    assert any(
        "Gemini 키가 없어 템플릿 기반 한국어 문안으로 대체했습니다." in warning
        for warning in warnings
    )
