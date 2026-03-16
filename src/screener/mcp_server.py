from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Callable, Protocol, cast
from uuid import uuid4

from .config import Settings
from .models import ArtifactMode, LLMMode, PDFMode
from .pipeline import run_live, run_offline

class _ToolDecorator(Protocol):
    def __call__(self, func: object) -> object: ...


class _FastMCPServer(Protocol):
    def tool(self) -> _ToolDecorator: ...

    def run(self, *, transport: str) -> None: ...


def _default_output_dir(settings: Settings, prefix: str) -> Path:
    return settings.output_root / "mcp" / f"{prefix}-{uuid4().hex[:8]}"


def _resolve_settings(
    *,
    artifact_mode: ArtifactMode,
    llm_mode: LLMMode,
    pdf_mode: PDFMode,
) -> Settings:
    settings = Settings()
    settings.artifact_mode = artifact_mode
    settings.llm_mode = llm_mode
    settings.pdf_mode = pdf_mode
    if artifact_mode == ArtifactMode.PDF_ONLY:
        settings.pdf_enabled = True
    elif artifact_mode == ArtifactMode.DATA_ONLY:
        settings.pdf_enabled = False
    return settings


def run_report_tool(
    *,
    mode: str = "offline",
    input_path: str | None = None,
    output_dir: str | None = None,
    llm_mode: str = "disabled",
    as_of: str | None = None,
    symbols_file: str | None = None,
    fail_on_provider_error: bool = False,
) -> dict[str, object]:
    settings = _resolve_settings(
        artifact_mode=ArtifactMode.PDF_ONLY,
        llm_mode=LLMMode(llm_mode),
        pdf_mode=PDFMode.REQUIRED,
    )
    output_path = Path(output_dir) if output_dir else _default_output_dir(settings, "report")
    if mode == "offline":
        if input_path is None:
            raise ValueError("input_path is required for offline mode")
        batch = run_offline(Path(input_path), output_path, settings)
    elif mode == "live":
        batch = run_live(
            output_path,
            settings,
            as_of=as_of,
            symbols_file=Path(symbols_file) if symbols_file else None,
            fail_on_provider_error=fail_on_provider_error,
        )
    else:
        raise ValueError("mode must be one of: offline, live")
    manifest = cast(
        dict[str, object],
        json.loads((output_path / "run_manifest.json").read_text(encoding="utf-8")),
    )
    warnings = cast(list[str], manifest.get("warnings", []))
    return {
        "run_id": batch.run_id,
        "mode": mode,
        "as_of": batch.as_of,
        "output_dir": str(output_path),
        "pdf_path": str(output_path / "report.pdf"),
        "manifest_path": str(output_path / "run_manifest.json"),
        "warnings": warnings,
    }


def run_data_tool(
    *,
    mode: str = "offline",
    input_path: str | None = None,
    output_dir: str | None = None,
    llm_mode: str = "disabled",
    as_of: str | None = None,
    symbols_file: str | None = None,
    fail_on_provider_error: bool = False,
) -> dict[str, object]:
    settings = _resolve_settings(
        artifact_mode=ArtifactMode.DATA_ONLY,
        llm_mode=LLMMode(llm_mode),
        pdf_mode=PDFMode.AUTO,
    )
    output_path = Path(output_dir) if output_dir else _default_output_dir(settings, "data")
    if mode == "offline":
        if input_path is None:
            raise ValueError("input_path is required for offline mode")
        batch = run_offline(Path(input_path), output_path, settings)
    elif mode == "live":
        batch = run_live(
            output_path,
            settings,
            as_of=as_of,
            symbols_file=Path(symbols_file) if symbols_file else None,
            fail_on_provider_error=fail_on_provider_error,
        )
    else:
        raise ValueError("mode must be one of: offline, live")
    manifest = cast(
        dict[str, object],
        json.loads((output_path / "run_manifest.json").read_text(encoding="utf-8")),
    )
    recommendations = cast(
        dict[str, object],
        json.loads((output_path / "recommendations.json").read_text(encoding="utf-8")),
    )
    evidence = cast(
        dict[str, object],
        json.loads((output_path / "evidence_packets.json").read_text(encoding="utf-8")),
    )
    snapshot = cast(
        dict[str, object],
        json.loads((output_path / "input_snapshot.json").read_text(encoding="utf-8")),
    )
    return {
        "run_id": batch.run_id,
        "mode": mode,
        "as_of": batch.as_of,
        "output_dir": str(output_path),
        "manifest": manifest,
        "snapshot": snapshot,
        "recommendations": recommendations,
        "evidence_packets": evidence,
    }


def build_mcp_server() -> _FastMCPServer:
    fastmcp_module = importlib.import_module("mcp.server.fastmcp")
    fast_mcp_cls = cast(Callable[[str], _FastMCPServer], getattr(fastmcp_module, "FastMCP"))
    mcp = fast_mcp_cls("screener")
    tool = mcp.tool()

    def run_report(
        mode: str = "offline",
        input_path: str | None = None,
        output_dir: str | None = None,
        llm_mode: str = "disabled",
        as_of: str | None = None,
        symbols_file: str | None = None,
        fail_on_provider_error: bool = False,
    ) -> dict[str, object]:
        return run_report_tool(
            mode=mode,
            input_path=input_path,
            output_dir=output_dir,
            llm_mode=llm_mode,
            as_of=as_of,
            symbols_file=symbols_file,
            fail_on_provider_error=fail_on_provider_error,
        )

    def run_data(
        mode: str = "offline",
        input_path: str | None = None,
        output_dir: str | None = None,
        llm_mode: str = "disabled",
        as_of: str | None = None,
        symbols_file: str | None = None,
        fail_on_provider_error: bool = False,
    ) -> dict[str, object]:
        return run_data_tool(
            mode=mode,
            input_path=input_path,
            output_dir=output_dir,
            llm_mode=llm_mode,
            as_of=as_of,
            symbols_file=symbols_file,
            fail_on_provider_error=fail_on_provider_error,
        )

    _ = tool(run_report)
    _ = tool(run_data)

    return mcp


def main() -> None:
    build_mcp_server().run(transport="stdio")


__all__ = [
    "main",
    "run_data_tool",
    "run_report_tool",
]
