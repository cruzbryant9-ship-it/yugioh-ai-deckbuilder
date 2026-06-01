from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_TOTAL_ADVISORY_CAP = 0.15
ADVISORY_KILL_SWITCH = False
KNOWN_ADVISORY_SOURCES = ("diagnosis", "diff_index", "filler_memory")
ENABLE_FILLER_MEMORY_INFLUENCE = False
ALLOWED_ACTIVATION_READY_FILLERS_ONLY = True
MAX_FILLER_MEMORY_BIAS = 0.03
PER_CARD_FILLER_MEMORY_BIAS_CAP = 0.025


@dataclass
class AdvisoryInfluenceBudget:
    total_cap: float = DEFAULT_TOTAL_ADVISORY_CAP
    enabled: bool = True
    used_by_source: dict[str, float] = field(default_factory=dict)

    def apply(self, source: str, requested: float) -> float:
        if not self.enabled or ADVISORY_KILL_SWITCH:
            return 0.0
        requested = clamp_float(requested)
        used_total = sum(abs(value) for value in self.used_by_source.values())
        remaining = max(0.0, abs(self.total_cap) - used_total)
        applied = max(-remaining, min(remaining, requested))
        self.used_by_source[source] = self.used_by_source.get(source, 0.0) + applied
        return round(applied, 6)

    def remaining(self) -> float:
        return round(max(0.0, abs(self.total_cap) - sum(abs(value) for value in self.used_by_source.values())), 6)

    def summary(self) -> dict[str, Any]:
        used = {source: round(float(self.used_by_source.get(source, 0.0) or 0.0), 6) for source in KNOWN_ADVISORY_SOURCES}
        for source, value in self.used_by_source.items():
            used.setdefault(source, round(float(value or 0.0), 6))
        return {
            "enabled": self.enabled and not ADVISORY_KILL_SWITCH,
            "total_cap": self.total_cap,
            "tracked_sources": list(KNOWN_ADVISORY_SOURCES),
            "used_by_source": used,
            "remaining": self.remaining(),
        }


def apply_advisory_nudges(requests: dict[str, float], total_cap: float = DEFAULT_TOTAL_ADVISORY_CAP, enabled: bool = True) -> dict[str, Any]:
    budget = AdvisoryInfluenceBudget(total_cap=total_cap, enabled=enabled)
    applied = {source: budget.apply(source, value) for source, value in requests.items()}
    return {"applied": applied, "summary": budget.summary()}


def clamp_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
