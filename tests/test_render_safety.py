from collections.abc import Callable
from pathlib import Path

import pytest

from screener.config import Settings
from screener.models import ArtifactMode, RecommendationBatch
from screener.pipeline import run_offline
from screener.reporting import render_dashboard, render_html


@pytest.mark.parametrize(
    ("renderer", "template_name"),
    [(render_html, "report.html.j2"), (render_dashboard, "dashboard.html.j2")],
)
def test_html_templates_escape_snapshot_text(
    renderer: Callable[[RecommendationBatch, Path], str],
    template_name: str,
    tmp_path: Path,
) -> None:
    batch = run_offline(
        Path("tests/fixtures/base_snapshot.json"),
        tmp_path / "data",
        Settings(artifact_mode=ArtifactMode.DATA_ONLY),
    )
    batch.recommendations[0].name = '<script>alert("fixture")</script> & Company'
    _ = (tmp_path / template_name).write_text(
        "<p>{{ batch.recommendations[0].name }}</p>", encoding="utf-8"
    )

    html = renderer(batch, tmp_path)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; Company" in html
