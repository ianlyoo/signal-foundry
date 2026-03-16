from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import ArtifactMode, LLMMode, PDFMode


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="SCREENER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    output_root: Path = Path("out")
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_mode: LLMMode = Field(default=LLMMode.DISABLED)
    artifact_mode: ArtifactMode = ArtifactMode.FULL
    pdf_enabled: bool = True
    pdf_mode: PDFMode = PDFMode.AUTO
    pdf_windows_preflight: bool = True
    pdf_windows_dll_directories: str = ""
    max_sector_per_bucket: int = 2
    stale_days_limit: int = 45
    filing_freshness_grace_days: int = 7
    min_market_cap_safe: float = 5_000_000_000
    min_market_cap_risky: float = 1_500_000_000
    cache_root: Path = Path("data/cache")
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 2
    fmp_api_key: str | None = None
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_universe_limit: int = 60
    fmp_fallback_symbols: tuple[str, ...] = (
        "MSFT",
        "GOOG",
        "META",
        "V",
        "SOFI",
        "AAPL",
        "NVDA",
        "AMZN",
        "ADBE",
        "AMD",
        "NFLX",
        "CSCO",
    )
    sec_base_url: str = "https://data.sec.gov"
    sec_company_tickers_url: str = "https://www.sec.gov/files/company_tickers.json"
    sec_user_agent: str | None = None
    sec_api_key: str | None = None
    sec_api_base_url: str = "https://api.sec-api.io"
    fred_api_key: str | None = None
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    fred_series_policy_rate: str = "FEDFUNDS"
    fred_series_inflation: str = "CPIAUCSL"
    fred_series_unemployment: str = "UNRATE"
    fred_series_credit_spread: str = "BAMLC0A0CM"
    fred_series_gdp_growth: str = "A191RL1Q225SBEA"


def get_settings() -> Settings:
    return Settings()
