from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .evidence import build_evidence
from .io import load_snapshot, write_batch, write_json, write_manifest, write_snapshot
from .models import (
    ArtifactMode,
    InputSnapshot,
    LLMMode,
    PDFMode,
    Recommendation,
    RecommendationBatch,
    RunManifest,
)
from .providers import build_live_snapshot
from .rationale import PROMPT_VERSION, generate_rationale, validate_grounding
from .reporting import (
    DISCLAIMER_ID,
    check_pdf_runtime,
    render_dashboard,
    render_html,
    render_markdown,
    write_pdf,
)
from .scoring import score_snapshot, select_top_six

RANKING_VERSION = "v1"


def run_offline(
    input_path: Path, output_dir: Path, settings: Settings
) -> RecommendationBatch:
    snapshot = load_snapshot(input_path)
    return _run_from_snapshot(
        snapshot,
        output_dir,
        settings,
        mode="offline",
        data_sources=[f"snapshot:{input_path.as_posix()}"],
        warnings=[],
    )


def run_live(
    output_dir: Path,
    settings: Settings,
    *,
    as_of: str | None = None,
    symbols_file: Path | None = None,
    fail_on_provider_error: bool = False,
) -> RecommendationBatch:
    live_result = build_live_snapshot(
        settings,
        as_of=as_of,
        symbols_file=symbols_file,
        fail_on_provider_error=fail_on_provider_error,
    )
    return _run_from_snapshot(
        live_result.snapshot,
        output_dir,
        settings,
        mode="live",
        data_sources=live_result.data_sources,
        warnings=live_result.warnings,
    )


def _run_from_snapshot(
    snapshot: InputSnapshot,
    output_dir: Path,
    settings: Settings,
    *,
    mode: str,
    data_sources: list[str],
    warnings: list[str],
) -> RecommendationBatch:
    scored = score_snapshot(snapshot, settings)
    selected = select_top_six(scored, settings)
    recommendations: list[Recommendation] = []
    runtime_warnings = list(warnings)
    rank = 1
    for bucket in ("safer_growth", "higher_risk_higher_growth"):
        for item in [pick for pick in selected if pick.bucket.value == bucket]:
            evidence = build_evidence(snapshot, item)
            rationale = generate_rationale(item, evidence, settings)
            recommendation = Recommendation(
                symbol=item.security.symbol,
                name=item.security.name,
                rank=rank,
                bucket=item.bucket,
                sector=item.security.sector,
                industry=item.security.industry,
                composite_score=item.composite_score,
                valuation_score=item.valuation_score,
                growth_score=item.growth_score,
                quality_score=item.quality_score,
                risk_score=item.risk_score,
                macro_overlay=item.macro_overlay,
                selection_tier=item.selection_tier,
                as_of=snapshot.as_of,
                evidence=evidence,
                rationale=rationale,
            )
            validate_grounding(recommendation)
            recommendations.append(recommendation)
            if recommendation.rationale.warning:
                runtime_warnings.append(
                    f"{recommendation.symbol}: {recommendation.rationale.warning}"
                )
            rank += 1
    source_modes = {item.rationale.source_mode for item in recommendations}
    if source_modes == {"gemini"}:
        model_version = settings.gemini_model
    elif source_modes == {"openai"}:
        model_version = settings.openai_model
    elif source_modes == {"template"}:
        model_version = "template-only"
    else:
        model_version = "mixed-fallback"
    requested_llm_mode = settings.llm_mode.value
    requested_llm_model = _requested_llm_model(settings)
    batch = RecommendationBatch(
        run_id=f"run-{uuid4().hex[:12]}",
        generated_at=datetime.now(UTC),
        as_of=snapshot.as_of,
        ranking_version=RANKING_VERSION,
        prompt_version=PROMPT_VERSION,
        model_version=model_version,
        disclaimer_id=DISCLAIMER_ID,
        requested_llm_mode=requested_llm_mode,
        requested_llm_model=requested_llm_model,
        rationale_sources=sorted(source_modes),
        recommendations=recommendations,
    )
    write_artifacts(
        batch,
        snapshot,
        output_dir,
        settings,
        mode=mode,
        data_sources=data_sources,
        warnings=runtime_warnings,
    )
    return batch


def _requested_llm_model(settings: Settings) -> str:
    if settings.llm_mode == LLMMode.GEMINI:
        return settings.gemini_model
    if settings.llm_mode == LLMMode.OPENAI:
        return settings.openai_model
    return ""


def write_artifacts(
    batch: RecommendationBatch,
    snapshot: InputSnapshot,
    output_dir: Path,
    settings: Settings,
    *,
    mode: str,
    data_sources: list[str],
    warnings: list[str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    templates_dir = Path(__file__).parent / "templates"
    artifact_mode = settings.artifact_mode

    artifacts: dict[str, str] = {}
    html_text = ""
    if artifact_mode in {ArtifactMode.FULL, ArtifactMode.PDF_ONLY}:
        html_text = render_html(batch, templates_dir, snapshot=snapshot)
    if artifact_mode == ArtifactMode.FULL:
        artifacts.update(_write_report_artifacts(batch, html_text, templates_dir, output_dir))
    if artifact_mode in {ArtifactMode.FULL, ArtifactMode.DATA_ONLY}:
        artifacts.update(_write_data_artifacts(batch, snapshot, output_dir))

    pdf = _generate_pdf(html_text, output_dir / "report.pdf", settings)
    if pdf.status == "generated":
        artifacts["report_pdf"] = str(output_dir / "report.pdf")
    manifest_warnings = list(warnings)
    if pdf.warning is not None:
        manifest_warnings.append(pdf.warning)
    manifest = RunManifest(
        run_id=batch.run_id,
        as_of=batch.as_of,
        mode=mode,
        artifact_mode=artifact_mode.value,
        ranking_version=batch.ranking_version,
        prompt_version=batch.prompt_version,
        model_version=batch.model_version,
        disclaimer_id=batch.disclaimer_id,
        requested_llm_mode=batch.requested_llm_mode,
        requested_llm_model=batch.requested_llm_model,
        rationale_sources=batch.rationale_sources,
        data_sources=data_sources,
        warnings=manifest_warnings,
        pdf_status=pdf.status,
        artifacts=artifacts,
        report_paths=list(artifacts.values()),
    )
    write_manifest(output_dir / "run_manifest.json", manifest)
    if pdf.error is not None:
        raise RuntimeError(pdf.error)


def _write_report_artifacts(
    batch: RecommendationBatch,
    html_text: str,
    templates_dir: Path,
    output_dir: Path,
) -> dict[str, str]:
    reports = (
        ("report_markdown", "report.md", render_markdown(batch)),
        ("report_html", "report.html", html_text),
        ("dashboard_html", "dashboard.html", render_dashboard(batch, templates_dir)),
    )
    artifacts: dict[str, str] = {}
    for name, filename, content in reports:
        path = output_dir / filename
        _ = path.write_text(content, encoding="utf-8")
        artifacts[name] = str(path)
    return artifacts


def _write_data_artifacts(
    batch: RecommendationBatch, snapshot: InputSnapshot, output_dir: Path
) -> dict[str, str]:
    snapshot_path = output_dir / "input_snapshot.json"
    batch_path = output_dir / "recommendations.json"
    evidence_path = output_dir / "evidence_packets.json"
    write_snapshot(snapshot_path, snapshot)
    write_batch(batch_path, batch)
    write_json(
        evidence_path,
        {
            "run_id": batch.run_id,
            "recommendations": [
                {
                    "symbol": item.symbol,
                    "evidence": [entry.model_dump(mode="json") for entry in item.evidence],
                }
                for item in batch.recommendations
            ],
        },
    )
    return {
        "input_snapshot": str(snapshot_path),
        "recommendations": str(batch_path),
        "evidence_packets": str(evidence_path),
    }


@dataclass(frozen=True)
class _PDFResult:
    status: str
    warning: str | None = None
    error: str | None = None


def _generate_pdf(html_text: str, pdf_path: Path, settings: Settings) -> _PDFResult:
    """Report the outcome so the manifest can be written before a required failure."""
    if settings.artifact_mode == ArtifactMode.PDF_ONLY and not settings.pdf_enabled:
        return _PDFResult(
            "disabled", error="PDF-only artifact mode requires PDF generation to be enabled"
        )
    if not settings.pdf_enabled or settings.artifact_mode == ArtifactMode.DATA_ONLY:
        return _PDFResult("disabled")
    ready, message = check_pdf_runtime(settings.pdf_windows_dll_directories)
    if not ready:
        status = "skipped_runtime_unavailable"
    else:
        generated, message = write_pdf(html_text, pdf_path)
        if generated:
            return _PDFResult("generated")
        status = "failed_generation"
    return _PDFResult(
        status, warning=message,
        error=message if settings.pdf_mode == PDFMode.REQUIRED else None,
    )
