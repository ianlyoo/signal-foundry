from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .config import get_settings
from .models import ArtifactMode, LLMMode, PDFMode
from .pipeline import run_live, run_offline
from .providers.base import ConfigurationError, ProviderError

app = typer.Typer(no_args_is_help=True)


@app.callback()
def callback() -> None:
    """Batch equity screener CLI."""


@app.command()
def run(
    input: Annotated[
        Path | None,
        typer.Option(
            exists=True, file_okay=True, dir_okay=False, help="Input snapshot JSON"
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(help="Execution mode: offline or live."),
    ] = "offline",
    output_dir: Annotated[
        str,
        typer.Option(help="Output artifact directory"),
    ] = "out/latest",
    llm_mode: Annotated[
        LLMMode,
        typer.Option(help="disabled, openai, or gemini"),
    ] = LLMMode.DISABLED,
    as_of: Annotated[
        str | None,
        typer.Option(help="Optional as-of date override for live mode (YYYY-MM-DD)."),
    ] = None,
    symbols_file: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Optional symbol override file for live mode.",
        ),
    ] = None,
    fail_on_provider_error: Annotated[
        bool,
        typer.Option(
            help="Fail immediately on provider enrichment errors in live mode."
        ),
    ] = False,
    pdf_mode: Annotated[
        PDFMode | None,
        typer.Option(help="Override PDF mode: auto or required."),
    ] = None,
    artifact_mode: Annotated[
        ArtifactMode | None,
        typer.Option(help="Artifact mode: pdf_only, full, or data_only."),
    ] = None,
) -> None:
    settings = get_settings()
    settings.llm_mode = llm_mode
    if pdf_mode is not None:
        settings.pdf_mode = pdf_mode
    if artifact_mode is not None:
        settings.artifact_mode = artifact_mode
    if settings.artifact_mode == ArtifactMode.PDF_ONLY and pdf_mode is None:
        settings.pdf_mode = PDFMode.REQUIRED
    if settings.artifact_mode == ArtifactMode.PDF_ONLY:
        settings.pdf_enabled = True
    output_path = Path(output_dir)
    try:
        if mode == "offline":
            if input is None:
                raise typer.BadParameter("--input is required for offline mode")
            batch = run_offline(input, output_path, settings)
        elif mode == "live":
            batch = run_live(
                output_path,
                settings,
                as_of=as_of,
                symbols_file=symbols_file,
                fail_on_provider_error=fail_on_provider_error,
            )
        else:
            raise typer.BadParameter("mode must be one of: offline, live")
    except (ConfigurationError, ProviderError, RuntimeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Run complete: {batch.run_id}")
    typer.echo(
        f"Generated {len(batch.recommendations)} recommendations for {batch.as_of}"
    )
    typer.echo(f"Artifacts written to {output_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
