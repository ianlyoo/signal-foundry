from pathlib import Path

from screener.config import Settings
from screener.models import ArtifactMode, LLMMode
from screener.pipeline import run_offline


def test_report_html_uses_korean_copy_and_print_break_styles(tmp_path: Path) -> None:
    settings = Settings(
        pdf_enabled=False,
        artifact_mode=ArtifactMode.FULL,
        llm_mode=LLMMode.DISABLED,
    )
    _ = run_offline(Path("tests/fixtures/base_snapshot.json"), tmp_path, settings)

    report_html = (tmp_path / "report.html").read_text(encoding="utf-8")

    assert '<html lang="ko">' in report_html
    assert "주식 추천 리포트" in report_html
    assert "스크린 해석" in report_html
    assert "Noto Sans CJK KR Embedded" in report_html
    assert "src/screener/templates/fonts/NotoSansCJKkr-Regular.otf" in report_html
    assert "break-before: page;" in report_html
    assert "report-block" in report_html
