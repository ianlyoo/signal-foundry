# Screener

Batch stock screener MVP with deterministic ranking, evidence packets, AI-ready rationale generation, and Markdown/HTML/PDF outputs. Reframed as a **RAG-like retrieval → reranking → grounding** pipeline over tabular fundamentals.

## Why I built this

Screening hundreds of tickers by hand is slow and inconsistent — every decision needs the same evidence and an auditable reason.
This pipeline automates the boring middle: retrieve a snapshot, rerank by rules, attach evidence, and generate only grounded text.
Deterministic scoring stays the source of truth so LLM output can explain, never invent.

## Highlights

- **Deterministic scoring (reranking):** `scoring.py` normalizes valuation/growth/quality/risk across the snapshot and applies a macro overlay before `select_top_six()` picks 3+3 (safer_growth / higher_risk_higher_growth).
- **Evidence packet:** `evidence.py:build_evidence()` emits 5 typed `EvidenceItem`s per pick (valuation, growth, quality, risk, macro) with `as_of` and `source`.
- **Grounded generation:** `rationale.py:generate_rationale()` calls OpenAI/Gemini only with the evidence blob, falls back to a deterministic template, and records `source_mode`/`model_name`.
- **Offline fixture:** `tests/fixtures/base_snapshot.json` lets the full pipeline run without network — `pytest -q` and `python -m screener.cli run --mode offline` both work offline.

## Architecture — RAG-like pipeline

> `provider → retrieval → reranking/scoring → evidence → grounded generation → validation → reporting`

```mermaid
flowchart LR
    A[provider] --> B[retrieval] --> C[reranking/scoring] --> D[evidence] --> E[grounded generation] --> F[validation] --> G[reporting]
```

| RAG 5-stage | Screener mapping | File |
|---|---|---|
| Ingest / Provider | FMP + SEC + FRED → `InputSnapshot` (or offline fixture) | `providers/live_snapshot.py`, `io.py` |
| Retrieval | **RAG-like tabular retrieval** — load snapshot rows for the as-of date (no vector DB) | `pipeline.py:run_offline/run_live`, `io.py:load_snapshot` |
| Reranking | Normalize + weight + macro overlay → composite score → sector-capped Top-6 | `scoring.py:score_snapshot`, `select_top_six` |
| Evidence | Build 5 evidence items per pick as the only context for generation | `evidence.py:build_evidence` |
| Grounded generation | Evidence-only prompt → JSON rationale (`text`, `key_reasons`, `primary_risks`, `watch_items`, `evidence_refs`) | `rationale.py:generate_rationale` |
| Validation | **Citation validation** via `validate_grounding()` — every `evidence_refs` must exist in `evidence` | `rationale.py:validate_grounding` |
| Reporting | Markdown / HTML / PDF + `evidence_packets.json` + `run_manifest.json` | `pipeline.py:write_artifacts`, `reporting.py` |

### RAG-like tabular retrieval (honest scope)

This project is **RAG-like, not vector RAG**. There is no embedding index, no vector database, and no ANN search. Retrieval is a deterministic load of a typed `InputSnapshot` table (snapshot JSON or live-built snapshot) — the same role a retriever plays in RAG, but over structured rows instead of vectors. That keeps the demo fully offline and reproducible via `tests/fixtures/base_snapshot.json`.

### Citation validation — `validate_grounding()`

`rationale.py:validate_grounding()` is the pipeline's citation check: given a `Recommendation`, it asserts `set(rationale.evidence_refs) ⊆ {e.evidence_id for e in evidence}` and raises `ValueError` on any unsupported ref. LLM callers (`_call_openai`, `_call_gemini`) run the same subset check before returning, so even a model that hallucinates an ID is rejected and the caller falls back to the template rationale with a warning in `run_manifest.json`.

### Tests

3 test modules, 12 cases — all offline, no network:

- `tests/test_pipeline.py` — 6-pick invariant, evidence grounding, Gemini mock + missing-key fallback warning
- `tests/test_cli.py` — PDF auto vs required runtime branch, live missing-secret error
- `tests/test_live_pipeline.py` — live snapshot mock, cache warnings, timeout and insufficient-candidate failures

Run: `pytest -q` (or `python -m pytest -q`).

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m screener.cli run --mode offline --input tests/fixtures/base_snapshot.json --output-dir out/demo
pytest
```

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
python -m screener.cli run --mode live --output-dir out/live
```

Example Gemini rationale run:

```bash
set SCREENER_GEMINI_API_KEY=your_gemini_key
python -m screener.cli run --mode offline --input tests/fixtures/base_snapshot.json --output-dir out/gemini --llm-mode gemini
```

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
