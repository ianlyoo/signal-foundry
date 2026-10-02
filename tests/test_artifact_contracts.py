import json
from pathlib import Path
from typing import cast

import pytest

from screener.config import Settings
from screener.io import load_snapshot
from screener.models import ArtifactMode, PDFMode
from screener.pipeline import run_offline, write_artifacts


def _ready_pdf(*_args: object) -> tuple[bool, str]:
    return True, "ok"


def _failed_pdf(*_args: object) -> tuple[bool, str]:
    return False, "fixture PDF failure"


def test_full_and_data_only_share_the_same_structured_outputs(tmp_path: Path) -> None:
    source = Path("tests/fixtures/base_snapshot.json")
    data_dir, full_dir = tmp_path / "data", tmp_path / "full"
    batch = run_offline(source, data_dir, Settings(artifact_mode=ArtifactMode.DATA_ONLY))
    warnings = ["fixture warning"]

    write_artifacts(
        batch, load_snapshot(source), full_dir,
        Settings(artifact_mode=ArtifactMode.FULL, pdf_enabled=False),
        mode="offline", data_sources=["fixture"], warnings=warnings,
    )

    for filename in ("input_snapshot.json", "recommendations.json", "evidence_packets.json"):
        assert (full_dir / filename).read_bytes() == (data_dir / filename).read_bytes()
    manifest = cast(dict[str, object], json.loads((full_dir / "run_manifest.json").read_text()))
    assert manifest["report_paths"] == [
        str(full_dir / name) for name in (
            "report.md", "report.html", "dashboard.html", "input_snapshot.json",
            "recommendations.json", "evidence_packets.json",
        )
    ]
    assert warnings == manifest["warnings"] == ["fixture warning"]
    assert "metrics" not in batch.recommendations[0].model_dump()
    assert "report_pdf" not in cast(dict[str, str], manifest["artifacts"])


@pytest.mark.parametrize("artifact_mode", [ArtifactMode.FULL, ArtifactMode.PDF_ONLY])
@pytest.mark.parametrize("pdf_mode", [PDFMode.AUTO, PDFMode.REQUIRED])
def test_pdf_failure_leaves_an_accurate_manifest_before_raising(
    artifact_mode: ArtifactMode,
    pdf_mode: PDFMode,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("screener.pipeline.check_pdf_runtime", _ready_pdf)
    monkeypatch.setattr("screener.pipeline.write_pdf", _failed_pdf)
    settings = Settings(artifact_mode=artifact_mode, pdf_mode=pdf_mode)
    source = Path("tests/fixtures/base_snapshot.json")

    if pdf_mode == PDFMode.REQUIRED:
        with pytest.raises(RuntimeError, match="fixture PDF failure"):
            _ = run_offline(source, tmp_path, settings)
    else:
        _ = run_offline(source, tmp_path, settings)

    manifest = cast(dict[str, object], json.loads((tmp_path / "run_manifest.json").read_text()))
    assert manifest["pdf_status"] == "failed_generation"
    assert manifest["warnings"] == ["fixture PDF failure"]
    assert "report_pdf" not in cast(dict[str, str], manifest["artifacts"])
    assert not (tmp_path / "report.pdf").exists()
