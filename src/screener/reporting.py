# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

import os
import platform
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import RecommendationBatch


def _candidate_windows_dll_dirs(config_value: str) -> list[Path]:
    paths: list[Path] = []
    for item in config_value.split(";"):
        value = item.strip()
        if value:
            paths.append(Path(value))
    paths.extend([Path("C:/msys64/ucrt64/bin"), Path("C:/msys64/mingw64/bin")])
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def check_pdf_runtime(pdf_windows_dll_directories: str = "") -> tuple[bool, str]:
    if platform.system() == "Windows":
        for dll_dir in _candidate_windows_dll_dirs(pdf_windows_dll_directories):
            if dll_dir.exists():
                os.environ["WEASYPRINT_DLL_DIRECTORIES"] = str(dll_dir)
                os.environ["PATH"] = f"{dll_dir};{os.environ.get('PATH', '')}"
                try:
                    add_dll_directory = getattr(os, "add_dll_directory", None)
                    if callable(add_dll_directory):
                        _ = add_dll_directory(str(dll_dir))
                except (AttributeError, FileNotFoundError, OSError):
                    pass
    try:
        from weasyprint import HTML

        _ = HTML

        return True, "ready"
    except Exception as exc:
        return False, f"PDF runtime unavailable: {exc}"


DISCLAIMER = (
    "이 자료는 정보 제공을 위한 리서치 결과이며, 개인 맞춤형 투자 자문이 아닙니다."
)
DISCLAIMER_ID = "generic-research-v1"


def render_markdown(batch: RecommendationBatch) -> str:
    lines = [
        f"# 주식 추천 리포트 ({batch.as_of})",
        "",
        DISCLAIMER,
        "",
        "## 개요",
        "",
        f"- 실행 ID: `{batch.run_id}`",
        f"- 랭킹 버전: `{batch.ranking_version}`",
        f"- 프롬프트 버전: `{batch.prompt_version}`",
        f"- 요청한 LLM 모드: `{batch.requested_llm_mode}`",
        f"- 요청한 LLM 모델: `{batch.requested_llm_model or '없음'}`",
        f"- 실제 문안 출처: `{', '.join(batch.rationale_sources) or 'template'}`",
        "",
    ]
    for recommendation in batch.recommendations:
        lines.extend(
            [
                f"## {recommendation.rank}. {recommendation.symbol} - {recommendation.name}",
                "",
                f"- 버킷: `{recommendation.bucket.value}`",
                f"- 섹터: `{recommendation.sector}`",
                f"- 종합 점수: `{recommendation.composite_score:.4f}`",
                f"- 문안 출처: `{recommendation.rationale.source_mode}` via `{recommendation.rationale.model_name}`",
                "",
                recommendation.rationale.text,
                "",
                 "### 핵심 근거",
                "",
            ]
        )
        for reason in recommendation.rationale.key_reasons:
            lines.append(f"- {reason}")
        lines.extend(
            [
                "",
                 "### 주요 리스크",
                "",
            ]
        )
        for risk in recommendation.rationale.primary_risks:
            lines.append(f"- {risk}")
        lines.extend(
            [
                "",
                 "### 체크 포인트",
                "",
            ]
        )
        for watch_item in recommendation.rationale.watch_items:
            lines.append(f"- {watch_item}")
        if recommendation.rationale.warning:
            lines.extend(
                [
                    "",
                     "### 생성 메모",
                    "",
                    f"- {recommendation.rationale.warning}",
                ]
            )
        lines.extend(
            [
                "",
                 "### 근거 데이터",
                "",
            ]
        )
        for item in recommendation.evidence:
            lines.append(f"- `{item.evidence_id}` {item.label}: {item.value}")
        lines.append("")
    return "\n".join(lines)


def render_html(batch: RecommendationBatch, templates_dir: Path) -> str:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    return template.render(
        title=f"주식 추천 리포트 ({batch.as_of})",
        batch=batch,
        disclaimer=DISCLAIMER,
        font_base_uri=templates_dir.resolve().as_uri(),
    )


def render_dashboard(batch: RecommendationBatch, templates_dir: Path) -> str:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("dashboard.html.j2")
    return template.render(title=f"Screener Dashboard ({batch.as_of})", batch=batch)


def write_pdf(html_text: str, output_path: Path) -> tuple[bool, str]:
    ready, message = check_pdf_runtime()
    if not ready:
        return False, message
    try:
        from weasyprint import HTML

        _ = HTML(string=html_text, base_url=str(output_path.parent)).write_pdf(
            str(output_path)
        )
        return True, "generated"
    except Exception as exc:
        return False, f"PDF generation failed: {exc}"
