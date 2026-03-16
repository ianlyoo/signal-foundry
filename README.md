# Signal Foundry

Signal Foundry is a stock screening and report-generation engine that turns market data into a polished PDF-first research packet, with full dashboard/data outputs available when needed.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m screener.cli run --mode offline --input tests/fixtures/base_snapshot.json --output-dir out/demo --artifact-mode pdf_only
pytest
```

## Recommended use

- Normal human use: generate the final PDF only.
- Dashboard/HTML inspection: run with `--artifact-mode full`.
- Agent/data workflows: run with `--artifact-mode data_only` or use the MCP wrapper.

## Modes

- `offline`: consumes a prebuilt snapshot fixture or JSON file
- `live`: builds a snapshot from FMP, SEC, and FRED before scoring

## AI rationale modes

- `--llm-mode disabled`: deterministic template text only
- `--llm-mode openai`: uses `SCREENER_OPENAI_API_KEY`
- `--llm-mode gemini`: uses `SCREENER_GEMINI_API_KEY`

## Live mode environment

Set these before running live mode:

```bash
set SCREENER_FMP_API_KEY=your_fmp_key
set SCREENER_FRED_API_KEY=your_fred_key
set SCREENER_SEC_USER_AGENT=YourApp your-email@example.com
```

Example live run:

```bash
python -m screener.cli run --mode live --output-dir out/live --artifact-mode pdf_only
```

If the FMP `company-screener` endpoint is unavailable on your plan, live mode now falls
back to a curated built-in symbol basket. You can also override the universe explicitly:

```bash
python -m screener.cli run --mode live --symbols-file symbols.txt --output-dir out/live
```

## Artifact modes

- `--artifact-mode pdf_only`: writes `report.pdf` and `run_manifest.json`
- `--artifact-mode full`: writes PDF plus HTML/Markdown/dashboard/data artifacts
- `--artifact-mode data_only`: writes structured JSON artifacts and no PDF

If you want the dashboard artifact, run in full mode and open `dashboard.html` from the output directory.

```bash
python -m screener.cli run --mode offline --input tests/fixtures/base_snapshot.json --output-dir out/full --artifact-mode full
```

Example Gemini rationale run:

```bash
set SCREENER_GEMINI_API_KEY=your_gemini_key
python -m screener.cli run --mode offline --input tests/fixtures/base_snapshot.json --output-dir out/gemini --llm-mode gemini --artifact-mode pdf_only
```

## MCP wrapper

This repo includes a thin MCP server entrypoint:

```bash
screener-mcp
```

It exposes two tools:

- `run_report`: PDF-first tool, returns `pdf_path` and `manifest_path`
- `run_data`: data-oriented tool, returns manifest plus structured recommendations/evidence payloads

## Windows PDF support

The project uses WeasyPrint for PDF output. On Windows, WeasyPrint also needs GTK/Pango/FontConfig runtime libraries.

Recommended setup:

```bash
winget install -e --id MSYS2.MSYS2 --accept-package-agreements --accept-source-agreements
C:\msys64\usr\bin\bash.exe -lc "pacman -S --noconfirm mingw-w64-ucrt-x86_64-pango mingw-w64-ucrt-x86_64-cairo mingw-w64-ucrt-x86_64-fontconfig"
```

Optional override if your DLLs live elsewhere:

```bash
set SCREENER_PDF_WINDOWS_DLL_DIRECTORIES=C:\msys64\ucrt64\bin
```
