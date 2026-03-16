# pyright: reportMissingTypeStubs=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownLambdaType=false

from pathlib import Path

from typer.testing import CliRunner

from screener.cli import app
from screener.config import Settings
runner = CliRunner()


def test_pdf_auto_missing_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "screener.pipeline.check_pdf_runtime",
        lambda *args, **kwargs: (False, "PDF runtime unavailable"),
    )
    result = runner.invoke(
        app,
        [
            "run",
            "--mode",
            "offline",
            "--input",
            "tests/fixtures/base_snapshot.json",
            "--output-dir",
            str(tmp_path),
            "--pdf-mode",
            "auto",
            "--artifact-mode",
            "full",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "dashboard.html").exists()
    assert not (tmp_path / "report.pdf").exists()
    manifest = (tmp_path / "run_manifest.json").read_text(encoding="utf-8")
    assert "dashboard.html" in manifest
    assert '"pdf_status": "skipped_runtime_unavailable"' in manifest


def test_pdf_required_missing_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "screener.pipeline.check_pdf_runtime",
        lambda *args, **kwargs: (False, "PDF runtime unavailable"),
    )
    result = runner.invoke(
        app,
        [
            "run",
            "--mode",
            "offline",
            "--input",
            "tests/fixtures/base_snapshot.json",
            "--output-dir",
            str(tmp_path),
            "--pdf-mode",
            "required",
            "--artifact-mode",
            "full",
        ],
    )
    assert result.exit_code != 0
    error_output = result.stdout + getattr(result, "stderr", "")
    assert (
        "PDF runtime unavailable" in error_output
        or "PDF runtime unavailable" in str(result.exception)
    )


def test_live_missing_secret_returns_clean_error(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SCREENER_FMP_API_KEY", raising=False)

    def settings_without_fmp() -> Settings:
        settings = Settings()
        settings.fmp_api_key = None
        return settings

    monkeypatch.setattr("screener.cli.get_settings", settings_without_fmp)
    result = runner.invoke(
        app,
        [
            "run",
            "--mode",
            "live",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    error_output = result.stdout + getattr(result, "stderr", "")
    assert "SCREENER_FMP_API_KEY is required for live mode" in error_output
