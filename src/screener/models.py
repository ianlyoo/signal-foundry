from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Bucket(str, Enum):
    SAFE = "safer_growth"
    RISKY = "higher_risk_higher_growth"


class LLMMode(str, Enum):
    DISABLED = "disabled"
    OPENAI = "openai"
    GEMINI = "gemini"


class PDFMode(str, Enum):
    AUTO = "auto"
    REQUIRED = "required"


class ArtifactMode(str, Enum):
    PDF_ONLY = "pdf_only"
    FULL = "full"
    DATA_ONLY = "data_only"


class MacroSnapshot(BaseModel):
    policy_rate: float
    inflation_yoy: float
    unemployment_rate: float
    credit_spread: float
    gdp_growth: float


class SecuritySnapshot(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: str
    market_cap: float
    price: float
    revenue_growth_yoy: float
    fcf_growth_yoy: float
    ebit_margin: float
    gross_margin: float
    debt_to_equity: float
    current_ratio: float
    fcf_yield: float
    ev_to_ebit: float
    pe_ratio: float
    earnings_yield: float
    roic: float
    beta: float
    analyst_upside: float
    stale_days: int = 0
    data_quality_score: float = 1.0


class InputSnapshot(BaseModel):
    as_of: str
    generated_at: datetime | None = None
    macro: MacroSnapshot
    securities: list[SecuritySnapshot]


class EvidenceItem(BaseModel):
    evidence_id: str
    label: str
    value: str
    source: str
    as_of: str


class RationaleOutput(BaseModel):
    text: str
    key_reasons: list[str] = Field(default_factory=list)
    primary_risks: list[str] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)
    evidence_refs: list[str]
    source_mode: str
    requested_mode: str = LLMMode.DISABLED.value
    model_name: str = "template-only"
    warning: str | None = None

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        if len(unique) < 2:
            raise ValueError("evidence_refs must contain at least 2 unique ids")
        return unique


class Recommendation(BaseModel):
    symbol: str
    name: str
    rank: int
    bucket: Bucket
    sector: str
    industry: str
    composite_score: float
    valuation_score: float
    growth_score: float
    quality_score: float
    risk_score: float
    macro_overlay: float
    selection_tier: str
    as_of: str
    evidence: list[EvidenceItem]
    rationale: RationaleOutput


class RunManifest(BaseModel):
    run_id: str
    as_of: str
    mode: str
    artifact_mode: str = ArtifactMode.FULL.value
    ranking_version: str
    prompt_version: str
    model_version: str
    disclaimer_id: str
    requested_llm_mode: str = LLMMode.DISABLED.value
    requested_llm_model: str = ""
    rationale_sources: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pdf_status: str = "not_requested"
    artifacts: dict[str, str] = Field(default_factory=dict)
    report_paths: list[str]


class RecommendationBatch(BaseModel):
    run_id: str
    generated_at: datetime
    as_of: str
    ranking_version: str
    prompt_version: str
    model_version: str
    disclaimer_id: str
    requested_llm_mode: str = LLMMode.DISABLED.value
    requested_llm_model: str = ""
    rationale_sources: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation]

    @model_validator(mode="after")
    def validate_recommendations(self) -> "RecommendationBatch":
        if len(self.recommendations) != 6:
            raise ValueError("recommendations must contain exactly 6 entries")
        symbols = [item.symbol for item in self.recommendations]
        if len(set(symbols)) != len(symbols):
            raise ValueError("recommendations must contain unique symbols")
        return self
