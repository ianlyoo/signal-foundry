# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

import json

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .models import Bucket, EvidenceItem, Recommendation, RationaleOutput
from .scoring import ScoredSecurity


PROMPT_VERSION = "v2-ko"


class LLMRationale(BaseModel):
    text: str
    key_reasons: list[str] = Field(min_length=2, max_length=4)
    primary_risks: list[str] = Field(min_length=2, max_length=4)
    watch_items: list[str] = Field(min_length=2, max_length=4)
    evidence_refs: list[str]

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        if len(unique) < 2:
            raise ValueError("evidence_refs must contain at least 2 unique ids")
        return unique


def _fallback_text(item: ScoredSecurity) -> str:
    security = item.security
    bucket_label = (
        "안정 성장" if item.bucket == Bucket.SAFE else "고위험 고성장"
    )
    return (
        f"{security.symbol}은(는) {bucket_label} 버킷에서 선별된 종목입니다. "
        f"매출 성장률 {security.revenue_growth_yoy:.1%}와 잉여현금흐름 수익률 {security.fcf_yield:.1%}의 조합이 유지되고, "
        f"EBIT 마진 {security.ebit_margin:.1%}, 유동비율 {security.current_ratio:.2f} 수준도 방어력을 보탭니다. "
        f"현재 금리, 물가, 신용 환경을 반영한 매크로 조건에서도 과도한 레버리지 없이 성장을 유지할 가능성이 상대적으로 높다고 판단됩니다."
    )


def _fallback_key_reasons(item: ScoredSecurity) -> list[str]:
    security = item.security
    return [
        f"매출 성장률이 {security.revenue_growth_yoy:.1%}로 플러스 구간을 유지해 성장 점수를 지지합니다.",
        f"잉여현금흐름 수익률 {security.fcf_yield:.1%}가 현재 현금창출력 대비 밸류에이션 부담을 어느 정도 상쇄합니다.",
        f"EBIT 마진 {security.ebit_margin:.1%}, ROIC {security.roic:.1%} 수준으로 운영 효율이 양호합니다.",
    ]


def _fallback_primary_risks(item: ScoredSecurity) -> list[str]:
    security = item.security
    return [
        f"베타가 {security.beta:.2f} 수준이라 시장 조정 시 지수보다 변동성이 크게 나타날 수 있습니다.",
        f"EV/EBIT {security.ev_to_ebit:.1f} 배수 구간에서는 성장 둔화가 발생할 경우 밸류에이션 압력이 커질 수 있습니다.",
        f"금리와 수요 환경이 우호적이지 않으면 멀티플 확장 여력이 제한될 수 있습니다.",
    ]


def _fallback_watch_items(item: ScoredSecurity) -> list[str]:
    security = item.security
    return [
        f"다음 실적 사이클에서도 매출 성장률이 {security.revenue_growth_yoy:.1%} 수준 이상 유지되는지 확인해야 합니다.",
        f"잉여현금흐름 전환율과 FCF 성장률이 {security.fcf_growth_yoy:.1%} 부근을 유지하는지 점검해야 합니다.",
        f"부채비율 {security.debt_to_equity:.2f}, 유동비율 {security.current_ratio:.2f}를 중심으로 재무 건전성을 추적해야 합니다.",
    ]


def _build_messages(
    item: ScoredSecurity, evidence: list[EvidenceItem]
) -> list[ChatCompletionMessageParam]:
    evidence_blob = json.dumps(
        [entry.model_dump(mode="json") for entry in evidence],
        ensure_ascii=True,
        indent=2,
    )
    bucket_label = (
        "안정 성장" if item.bucket == Bucket.SAFE else "고위험 고성장"
    )
    return [
        {
            "role": "system",
            "content": (
                "당신은 간결한 한국어 투자 리서치 요약을 작성합니다. 제공된 evidence만 사용하세요. "
                "사실, 목표주가, 투자 조언을 지어내지 마세요. 모든 문장은 evidence로 뒷받침되어야 합니다."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{item.security.symbol}이(가) {bucket_label} 버킷에 포함된 이유를 한국어 3~4문장으로 작성하세요. "
                "JSON만 반환하세요. Evidence:\n"
                f"{evidence_blob}"
            ),
        },
    ]


def _build_prompt_text(item: ScoredSecurity, evidence: list[EvidenceItem]) -> str:
    evidence_blob = json.dumps(
        [entry.model_dump(mode="json") for entry in evidence],
        ensure_ascii=True,
        indent=2,
    )
    bucket_label = (
        "안정 성장" if item.bucket == Bucket.SAFE else "고위험 고성장"
    )
    return (
        "당신은 간결한 한국어 투자 리서치 요약을 작성합니다. 제공된 evidence만 사용하세요. "
        "사실, 목표주가, 투자 조언을 지어내지 마세요. 모든 문장은 evidence로 뒷받침되어야 합니다. "
        f"{item.security.symbol}이(가) {bucket_label} 버킷에 포함된 이유를 한국어 3~4문장으로 작성하세요. "
        "스키마에 맞는 JSON만 반환하세요. Evidence:\n"
        f"{evidence_blob}"
    )


def _call_openai(
    item: ScoredSecurity, evidence: list[EvidenceItem], settings: Settings
) -> RationaleOutput:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=_build_messages(item, evidence),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "stock_rationale",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "key_reasons": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                        "primary_risks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                        "watch_items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                        "evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                    },
                    "required": [
                        "text",
                        "key_reasons",
                        "primary_risks",
                        "watch_items",
                        "evidence_refs",
                    ],
                    "additionalProperties": False,
                },
            },
        },
    )
    raw = response.choices[0].message.content
    if not isinstance(raw, str):
        raise ValueError("LLM did not return JSON text content")
    parsed = LLMRationale.model_validate_json(raw)
    valid_refs = {entry.evidence_id for entry in evidence}
    if not set(parsed.evidence_refs).issubset(valid_refs):
        raise ValueError("LLM returned unsupported evidence refs")
    return RationaleOutput(
        text=parsed.text,
        key_reasons=parsed.key_reasons,
        primary_risks=parsed.primary_risks,
        watch_items=parsed.watch_items,
        evidence_refs=parsed.evidence_refs,
        source_mode="openai",
        requested_mode=settings.llm_mode.value,
        model_name=settings.openai_model,
    )


def _call_gemini(
    item: ScoredSecurity, evidence: list[EvidenceItem], settings: Settings
) -> RationaleOutput:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=_build_prompt_text(item, evidence),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=LLMRationale.model_json_schema(),
            temperature=0.1,
        ),
    )
    if response.parsed is not None:
        parsed = LLMRationale.model_validate(response.parsed)
    else:
        raw = response.text
        if not isinstance(raw, str):
            raise ValueError("Gemini did not return JSON text content")
        parsed = LLMRationale.model_validate_json(raw)
    valid_refs = {entry.evidence_id for entry in evidence}
    if not set(parsed.evidence_refs).issubset(valid_refs):
        raise ValueError("Gemini returned unsupported evidence refs")
    return RationaleOutput(
        text=parsed.text,
        key_reasons=parsed.key_reasons,
        primary_risks=parsed.primary_risks,
        watch_items=parsed.watch_items,
        evidence_refs=parsed.evidence_refs,
        source_mode="gemini",
        requested_mode=settings.llm_mode.value,
        model_name=settings.gemini_model,
    )


def _fallback_rationale(
    item: ScoredSecurity,
    requested_mode: str,
    warning: str | None = None,
) -> RationaleOutput:
    refs = [
        f"{item.security.symbol}-val",
        f"{item.security.symbol}-growth",
        f"{item.security.symbol}-quality",
    ]
    return RationaleOutput(
        text=_fallback_text(item),
        key_reasons=_fallback_key_reasons(item),
        primary_risks=_fallback_primary_risks(item),
        watch_items=_fallback_watch_items(item),
        evidence_refs=refs,
        source_mode="template",
        requested_mode=requested_mode,
        model_name="template-only",
        warning=warning,
    )


def generate_rationale(
    item: ScoredSecurity, evidence: list[EvidenceItem], settings: Settings
) -> RationaleOutput:
    if settings.llm_mode.value == "gemini":
        if not settings.gemini_api_key:
            return _fallback_rationale(
                item,
                requested_mode=settings.llm_mode.value,
                warning="Gemini 키가 없어 템플릿 기반 한국어 문안으로 대체했습니다.",
            )
        try:
            return _call_gemini(item, evidence, settings)
        except Exception:
            return _fallback_rationale(
                item,
                requested_mode=settings.llm_mode.value,
                warning="Gemini 생성에 실패해 템플릿 기반 한국어 문안으로 대체했습니다.",
            )
    if settings.llm_mode.value == "openai":
        if not settings.openai_api_key:
            return _fallback_rationale(
                item,
                requested_mode=settings.llm_mode.value,
                warning="OpenAI 키가 없어 템플릿 기반 한국어 문안으로 대체했습니다.",
            )
        try:
            return _call_openai(item, evidence, settings)
        except Exception:
            return _fallback_rationale(
                item,
                requested_mode=settings.llm_mode.value,
                warning="OpenAI 생성에 실패해 템플릿 기반 한국어 문안으로 대체했습니다.",
            )
    return _fallback_rationale(item, requested_mode=settings.llm_mode.value)


def validate_grounding(recommendation: Recommendation) -> None:
    valid_refs = {entry.evidence_id for entry in recommendation.evidence}
    missing = [
        ref for ref in recommendation.rationale.evidence_refs if ref not in valid_refs
    ]
    if missing:
        raise ValueError(f"Unsupported evidence references: {missing}")
