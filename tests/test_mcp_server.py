import json
from pathlib import Path
from typing import cast

import pytest

from screener.mcp_server import run_data_tool, run_report_tool


def _ready_pdf_runtime(*_args: object, **_kwargs: object) -> tuple[bool, str]:
    return True, "ok"


def _fake_write_pdf(_html: str, path: Path) -> tuple[bool, str]:
    _ = path.write_bytes(b"%PDF-1.7\n")
    return True, "ok"


def _unavailable_pdf_runtime(*_args: object, **_kwargs: object) -> tuple[bool, str]:
    return False, "PDF runtime unavailable"


def test_run_report_tool_defaults_to_pdf_only(
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

    result = run_report_tool(
        mode="offline",
        input_path="tests/fixtures/base_snapshot.json",
        output_dir=str(tmp_path),
    )

    assert (tmp_path / "report.pdf").exists()
    assert not (tmp_path / "recommendations.json").exists()
    manifest = cast(
        dict[str, object],
        json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8")),
    )
    assert manifest["artifact_mode"] == "pdf_only"
    assert result["pdf_path"] == str(tmp_path / "report.pdf")


def test_run_data_tool_returns_structured_payloads(tmp_path: Path) -> None:
    result = run_data_tool(
        mode="offline",
        input_path="tests/fixtures/base_snapshot.json",
        output_dir=str(tmp_path),
    )

    assert (tmp_path / "recommendations.json").exists()
    assert not (tmp_path / "report.pdf").exists()
    manifest = cast(dict[str, object], result["manifest"])
    recommendations = cast(dict[str, object], result["recommendations"])
    evidence_packets = cast(dict[str, object], result["evidence_packets"])
    recommendation_rows = cast(list[object], recommendations["recommendations"])
    assert manifest["artifact_mode"] == "data_only"
    assert len(recommendation_rows) == 6
    assert "recommendations" in evidence_packets


def test_run_report_tool_enforces_pdf_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "screener.pipeline.check_pdf_runtime",
        _unavailable_pdf_runtime,
    )

    with pytest.raises(RuntimeError, match="PDF runtime unavailable"):
        _ = run_report_tool(
            mode="offline",
            input_path="tests/fixtures/base_snapshot.json",
            output_dir=str(tmp_path),
        )
