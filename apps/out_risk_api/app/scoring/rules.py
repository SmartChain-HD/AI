from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.schemas.risk import RiskLevel


def esg_parse_date_ymd(value: str) -> Optional[datetime]:
    s = (value or "").strip()
    if not s:
        return None
    try:
        if "T" in s and s.endswith("Z") and len(s) == 16:
            return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


def esg_recency_weight(published_at: str) -> float:
    dt = esg_parse_date_ymd(published_at)
    if not dt:
        return 0.6
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days = max(0, (now - dt).days)

    if days <= 30:
        return 1.5
    if days <= 90:
        return 1.0
    if days <= 180:
        return 0.8
    if days <= 365:
        return 0.6
    return 0.3


def esg_level_from_total(total_score: float) -> RiskLevel:
    if total_score >= 10:
        return RiskLevel.HIGH
    if total_score >= 5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
