# signal-foundry

[English](README.md)

[![CI](https://github.com/ianlyoo/signal-foundry/actions/workflows/ci.yml/badge.svg)](https://github.com/ianlyoo/signal-foundry/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release: v0.1.0](https://img.shields.io/badge/Release-v0.1.0-blue.svg)](https://github.com/ianlyoo/signal-foundry/releases/tag/v0.1.0)
[![Pages](https://img.shields.io/badge/Pages-live-brightgreen.svg)](https://ianlyoo.github.io/signal-foundry/)

PDF-first stock screener and research packet generator — automate screening with MCP-ready data tools in measured market workloads.

> PDF 우선 주식 스크리너와 리서치 패킷 생성기입니다. 테이블 기반 retrieval과 결정론적 스크리닝, 근거 패킷과 MCP 데이터 도구를 제공합니다.

## 빠른 시작 — pdf와 screening

```bash
gh release download v0.1.0 --pattern "*.tgz" --repo ianlyoo/signal-foundry
npm install ./signal-foundry-*.tgz
```

```bash
git clone https://github.com/ianlyoo/signal-foundry.git
cd signal-foundry
bun install --frozen-lockfile
bun run build
```

```bash
python -m venv .venv
# Windows alternative: .venv\Scripts\activate
pip install -e .[dev]
python -m screener.cli run --mode offline --input tests/fixtures/base_snapshot.json --output-dir out/demo
```

## 활용 사례 — stock-screener와 research-packet

- 6-pick 스크리닝 (3 safer_growth + 3 higher_risk)
- 픽당 5개 EvidenceItem과 인용 검증
- Markdown/HTML/PDF 리포트와 MCP 도구

## 아키텍처 — retrieval 파이프라인

`retrieval → screening → evidence → generation → validation → reporting`

## 벤치마크 — 측정된 워크로드에서의 screening

Offline fixture 기반: 6 picks, 픽당 5 evidence, 12 테스트 케이스 offline.

Limitations adjacent to benchmark: tabular retrieval — no vector search, live는 키 필요, heuristic scoring not advice, synthetic seed 42, one run per condition, policy may change, no billing.

## 라이선스

MIT — [LICENSE](LICENSE)를 참고하세요.
