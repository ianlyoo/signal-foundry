# Signal Foundry

Signal Foundry는 주식 스크리닝 결과를 PDF 중심 리서치 패킷으로 만들어 주는 엔진입니다. 필요할 때만 대시보드/HTML/JSON 데이터 산출물을 함께 남기고, AI 에이전트용 MCP 인터페이스도 별도로 제공합니다.

## 한눈에 보기

- 사람 사용 기본값: `pdf_only`
- 검토용 대시보드: `full`
- 에이전트/파이프라인 연동: `data_only` 또는 `screener-mcp`

## 설치

### 1) 가상환경 생성

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

Windows CMD:

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .[dev]
```

## 환경 변수

`.env.example`을 복사해 `.env`를 만들고 필요한 값을 채우면 됩니다.

필수/선택 항목은 다음과 같습니다.

- `SCREENER_FMP_API_KEY`: live 모드 종목/재무 데이터
- `SCREENER_FRED_API_KEY`: 거시 데이터
- `SCREENER_SEC_USER_AGENT`: SEC 직접 조회 시 식별 헤더
- `SCREENER_SEC_API_KEY`: SEC 대체 filing freshness 소스
- `SCREENER_GEMINI_API_KEY`: Gemini 문안 생성
- `SCREENER_OPENAI_API_KEY`: OpenAI 문안 생성

## 빠른 시작

오프라인 fixture로 PDF만 생성:

```bash
python -m screener.cli run \
  --mode offline \
  --input tests/fixtures/base_snapshot.json \
  --output-dir out/demo \
  --artifact-mode pdf_only
```

생성 결과:

- `out/demo/report.pdf`
- `out/demo/run_manifest.json`

## 실행 모드

- `offline`: 준비된 snapshot JSON으로 실행
- `live`: FMP / SEC(sec-api fallback) / FRED를 사용해 실데이터로 실행

예시:

```bash
python -m screener.cli run --mode live --output-dir out/live --artifact-mode pdf_only
```

FMP `company-screener` endpoint를 쓰기 어려운 플랜이면 내장 종목 바스켓으로 fallback합니다. 직접 유니버스를 지정하려면:

```bash
python -m screener.cli run --mode live --symbols-file symbols.txt --output-dir out/live --artifact-mode pdf_only
```

## Artifact Mode

### `pdf_only`

최종 리포트만 필요할 때 쓰는 기본 모드입니다.

- 남는 파일: `report.pdf`, `run_manifest.json`

### `full`

대시보드, HTML, 마크다운, 데이터 산출물까지 전부 보고 싶을 때 씁니다.

- 남는 파일: PDF + HTML/Markdown/dashboard + JSON 데이터

```bash
python -m screener.cli run \
  --mode offline \
  --input tests/fixtures/base_snapshot.json \
  --output-dir out/full \
  --artifact-mode full
```

이 모드에서는 `out/full/dashboard.html`을 브라우저에서 열어 확인할 수 있습니다.

### `data_only`

에이전트, 후처리 파이프라인, 분석 스크립트용 구조화 데이터만 남깁니다.

- 남는 파일: `input_snapshot.json`, `recommendations.json`, `evidence_packets.json`, `run_manifest.json`

## AI 문안 생성

- `--llm-mode disabled`: 템플릿 기반 문안
- `--llm-mode gemini`: Gemini 사용
- `--llm-mode openai`: OpenAI 사용

예시:

```bash
python -m screener.cli run \
  --mode offline \
  --input tests/fixtures/base_snapshot.json \
  --output-dir out/gemini \
  --llm-mode gemini \
  --artifact-mode pdf_only
```

## MCP 사용

이 프로젝트는 얇은 MCP 서버 엔트리포인트를 포함합니다.

```bash
screener-mcp
```

제공 도구:

- `run_report`: PDF 우선 도구. 기본적으로 PDF 리포트 경로와 manifest 경로를 반환
- `run_data`: 구조화 데이터 도구. manifest, 추천 결과, evidence packet을 반환

권장 사용 방식:

- 사람/운영자: CLI + `pdf_only`
- 다른 에이전트: MCP `run_report`
- 데이터 파이프라인/분석: MCP `run_data`

## 테스트 및 점검

```bash
python -m basedpyright
pytest
```

## Windows PDF 런타임

Windows에서는 WeasyPrint 외에도 GTK/Pango/FontConfig 런타임이 필요합니다.

PowerShell 예시:

```powershell
winget install -e --id MSYS2.MSYS2 --accept-package-agreements --accept-source-agreements
C:\msys64\usr\bin\bash.exe -lc "pacman -S --noconfirm mingw-w64-ucrt-x86_64-pango mingw-w64-ucrt-x86_64-cairo mingw-w64-ucrt-x86_64-fontconfig"
```

런타임 DLL 경로를 직접 지정하려면:

PowerShell:

```powershell
$env:SCREENER_PDF_WINDOWS_DLL_DIRECTORIES = "C:\msys64\ucrt64\bin"
```

CMD:

```bat
set SCREENER_PDF_WINDOWS_DLL_DIRECTORIES=C:\msys64\ucrt64\bin
```
