from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .config import Settings
from .models import Bucket, InputSnapshot, SecuritySnapshot


class InsufficientCandidatesError(RuntimeError):
    pass


@dataclass
class ScoredSecurity:
    security: SecuritySnapshot
    bucket: Bucket
    valuation_score: float
    growth_score: float
    quality_score: float
    risk_score: float
    macro_overlay: float
    composite_score: float
    selection_tier: str = "strict"


def _normalize(
    value: float, lower: float, upper: float, inverse: bool = False
) -> float:
    if upper == lower:
        return 0.5
    ratio = (value - lower) / (upper - lower)
    ratio = max(0.0, min(1.0, ratio))
    return 1.0 - ratio if inverse else ratio


def _range(values: list[float]) -> tuple[float, float]:
    return (min(values), max(values))


def _eligible(security: SecuritySnapshot, bucket: Bucket, settings: Settings) -> bool:
    min_market_cap = (
        settings.min_market_cap_safe
        if bucket == Bucket.SAFE
        else settings.min_market_cap_risky
    )
    return (
        security.price > 0
        and security.market_cap >= min_market_cap
        and security.stale_days <= settings.stale_days_limit
        and security.data_quality_score >= 0.6
        and security.revenue_growth_yoy > 0
        and security.fcf_yield > 0
    )


def _macro_overlay(
    snapshot: InputSnapshot, security: SecuritySnapshot, bucket: Bucket
) -> float:
    macro = snapshot.macro
    overlay = 0.0
    if macro.policy_rate >= 4.0 or macro.inflation_yoy >= 3.0:
        overlay -= 0.08 * max(security.ev_to_ebit / 30.0, 0.0)
    if macro.credit_spread >= 1.5 or macro.unemployment_rate >= 4.5:
        overlay -= 0.12 * max(security.debt_to_equity / 2.0, 0.0)
        overlay += 0.08 * min(security.current_ratio / 2.5, 1.0)
    if macro.gdp_growth >= 2.0:
        overlay += 0.05 * min(security.revenue_growth_yoy / 0.30, 1.0)
    if bucket == Bucket.RISKY:
        overlay -= 0.05 * max((security.beta - 1.4) / 1.0, 0.0)
    return overlay


def score_snapshot(snapshot: InputSnapshot, settings: Settings) -> list[ScoredSecurity]:
    all_values = {
        "fcf_yield": _range([item.fcf_yield for item in snapshot.securities]),
        "ev_to_ebit": _range([item.ev_to_ebit for item in snapshot.securities]),
        "earnings_yield": _range([item.earnings_yield for item in snapshot.securities]),
        "revenue_growth_yoy": _range(
            [item.revenue_growth_yoy for item in snapshot.securities]
        ),
        "fcf_growth_yoy": _range([item.fcf_growth_yoy for item in snapshot.securities]),
        "ebit_margin": _range([item.ebit_margin for item in snapshot.securities]),
        "gross_margin": _range([item.gross_margin for item in snapshot.securities]),
        "roic": _range([item.roic for item in snapshot.securities]),
        "debt_to_equity": _range([item.debt_to_equity for item in snapshot.securities]),
        "current_ratio": _range([item.current_ratio for item in snapshot.securities]),
        "beta": _range([item.beta for item in snapshot.securities]),
        "analyst_upside": _range([item.analyst_upside for item in snapshot.securities]),
    }
    scored: list[ScoredSecurity] = []
    for security in snapshot.securities:
        for bucket in (Bucket.SAFE, Bucket.RISKY):
            if not _eligible(security, bucket, settings):
                continue
            valuation = (
                0.45 * _normalize(security.fcf_yield, *all_values["fcf_yield"])
                + 0.30
                * _normalize(
                    security.ev_to_ebit, *all_values["ev_to_ebit"], inverse=True
                )
                + 0.25
                * _normalize(security.earnings_yield, *all_values["earnings_yield"])
            )
            growth = (
                0.55
                * _normalize(
                    security.revenue_growth_yoy, *all_values["revenue_growth_yoy"]
                )
                + 0.30
                * _normalize(security.fcf_growth_yoy, *all_values["fcf_growth_yoy"])
                + 0.15
                * _normalize(security.analyst_upside, *all_values["analyst_upside"])
            )
            quality = (
                0.35 * _normalize(security.ebit_margin, *all_values["ebit_margin"])
                + 0.25 * _normalize(security.gross_margin, *all_values["gross_margin"])
                + 0.25 * _normalize(security.roic, *all_values["roic"])
                + 0.15 * security.data_quality_score
            )
            risk = (
                0.40
                * _normalize(
                    security.debt_to_equity, *all_values["debt_to_equity"], inverse=True
                )
                + 0.35
                * _normalize(security.current_ratio, *all_values["current_ratio"])
                + 0.25 * _normalize(security.beta, *all_values["beta"], inverse=True)
            )
            overlay = _macro_overlay(snapshot, security, bucket)
            if bucket == Bucket.SAFE:
                composite = (
                    0.28 * valuation
                    + 0.26 * growth
                    + 0.28 * quality
                    + 0.18 * risk
                    + overlay
                )
            else:
                composite = (
                    0.18 * valuation
                    + 0.40 * growth
                    + 0.17 * quality
                    + 0.10 * risk
                    + overlay
                )
            scored.append(
                ScoredSecurity(
                    security=security,
                    bucket=bucket,
                    valuation_score=round(valuation, 4),
                    growth_score=round(growth, 4),
                    quality_score=round(quality, 4),
                    risk_score=round(risk, 4),
                    macro_overlay=round(overlay, 4),
                    composite_score=round(composite, 4),
                )
            )
    return scored


def select_top_six(
    scored: list[ScoredSecurity], settings: Settings
) -> list[ScoredSecurity]:
    selected: list[ScoredSecurity] = []
    selected_symbols: set[str] = set()
    sector_counts: dict[Bucket, Counter[str]] = {
        Bucket.SAFE: Counter(),
        Bucket.RISKY: Counter(),
    }
    for bucket in (Bucket.SAFE, Bucket.RISKY):
        bucket_items = sorted(
            [item for item in scored if item.bucket == bucket],
            key=lambda item: item.composite_score,
            reverse=True,
        )
        for item in bucket_items:
            if item.security.symbol in selected_symbols:
                continue
            if (
                sector_counts[bucket][item.security.sector]
                >= settings.max_sector_per_bucket
            ):
                continue
            selected.append(item)
            selected_symbols.add(item.security.symbol)
            sector_counts[bucket][item.security.sector] += 1
            if len([pick for pick in selected if pick.bucket == bucket]) == 3:
                break
    if len(selected) != 6:
        raise InsufficientCandidatesError(
            "Unable to select exactly 6 candidates under current rules"
        )
    selected.sort(key=lambda item: (item.bucket.value, -item.composite_score))
    return selected
