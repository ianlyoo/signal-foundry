from __future__ import annotations

from .models import EvidenceItem, InputSnapshot
from .scoring import ScoredSecurity


def build_evidence(snapshot: InputSnapshot, item: ScoredSecurity) -> list[EvidenceItem]:
    security = item.security
    as_of = snapshot.as_of
    return [
        EvidenceItem(
            evidence_id=f"{security.symbol}-val",
            label="Valuation remains reasonable for its cash generation",
            value=f"FCF yield {security.fcf_yield:.2%}, EV/EBIT {security.ev_to_ebit:.1f}",
            source="deterministic_snapshot",
            as_of=as_of,
        ),
        EvidenceItem(
            evidence_id=f"{security.symbol}-growth",
            label="Growth remains positive",
            value=f"Revenue growth {security.revenue_growth_yoy:.2%}, FCF growth {security.fcf_growth_yoy:.2%}",
            source="deterministic_snapshot",
            as_of=as_of,
        ),
        EvidenceItem(
            evidence_id=f"{security.symbol}-quality",
            label="Operating quality and returns remain solid",
            value=f"EBIT margin {security.ebit_margin:.2%}, ROIC {security.roic:.2%}",
            source="deterministic_snapshot",
            as_of=as_of,
        ),
        EvidenceItem(
            evidence_id=f"{security.symbol}-risk",
            label="Balance sheet and market risk are visible",
            value=f"Debt/Equity {security.debt_to_equity:.2f}, Current ratio {security.current_ratio:.2f}, Beta {security.beta:.2f}",
            source="deterministic_snapshot",
            as_of=as_of,
        ),
        EvidenceItem(
            evidence_id=f"macro-{security.symbol}",
            label="Macro overlay affected the score",
            value=(
                f"Policy rate {snapshot.macro.policy_rate:.2f}%, Inflation {snapshot.macro.inflation_yoy:.2f}%, "
                f"Unemployment {snapshot.macro.unemployment_rate:.2f}%, GDP growth {snapshot.macro.gdp_growth:.2f}%"
            ),
            source="macro_snapshot",
            as_of=as_of,
        ),
    ]
