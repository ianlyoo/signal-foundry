import json
from pathlib import Path
from typing import cast

import pytest

from screener.config import Settings
from screener.models import ArtifactMode
from screener.pipeline import run_offline


def _ready_pdf_runtime(*_args: object, **_kwargs: object) -> tuple[bool, str]:
    return True, "ok"


def _fake_write_pdf(_html: str, path: Path) -> tuple[bool, str]:
    _ = path.write_bytes(b"%PDF-1.7\n")
    return True, "ok"


def test_pdf_only_mode_keeps_pdf_and_manifest_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "screener.pipeline.check_pdf_runtime",
        _ready_pdf_runtime,
    )
    monkeypatch.setattr(
        "screener.pipeline.write_pdf",
        _fake_write_pdf,
    )

    settings = Settings(artifact_mode=ArtifactMode.PDF_ONLY)
    _ = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)

    assert (tmp_path / "report.pdf").exists()
    assert (tmp_path / "run_manifest.json").exists()
    assert not (tmp_path / "report.html").exists()
    assert not (tmp_path / "dashboard.html").exists()
    assert not (tmp_path / "recommendations.json").exists()

    manifest = cast(
        dict[str, object],
        json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8")),
    )
    artifacts = cast(dict[str, str], manifest["artifacts"])
    assert manifest["artifact_mode"] == "pdf_only"
    assert artifacts["report_pdf"].endswith("report.pdf")


def test_data_only_mode_keeps_structured_outputs_only(tmp_path: Path) -> None:
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.DATA_ONLY)
    _ = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)

    assert (tmp_path / "input_snapshot.json").exists()
    assert (tmp_path / "recommendations.json").exists()
    assert (tmp_path / "evidence_packets.json").exists()
    assert (tmp_path / "run_manifest.json").exists()
    assert not (tmp_path / "report.pdf").exists()
    assert not (tmp_path / "report.html").exists()
    assert not (tmp_path / "dashboard.html").exists()

    manifest = cast(
        dict[str, object],
        json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8")),
    )
    artifacts = cast(dict[str, str], manifest["artifacts"])
    assert manifest["artifact_mode"] == "data_only"
    assert "recommendations" in artifacts


def test_pdf_only_mode_raises_when_pdf_disabled(tmp_path: Path) -> None:
    settings = Settings(pdf_enabled=False, artifact_mode=ArtifactMode.PDF_ONLY)

    with pytest.raises(RuntimeError, match="PDF-only artifact mode requires PDF generation"):
        _ = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)
