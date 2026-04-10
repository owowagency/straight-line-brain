"""
Rule-based query classification for known patterns.

STRUCTURED signals:
- Numbers: "hoeveel", "aantal", "gemiddeld", "totaal", "som"
- Comparisons: "vergelijk", "vs", "verschil", "meer dan"
- Time series: "trend", "groei", "daling", "afgelopen kwartaal"
- Aggregations: "per segment", "per maand", "top 10"

SEMANTIC signals:
- Qualitative: "wat is ons standpunt", "hoe spreken we"
- Knowledge: "tone of voice", "propositie", "werkwijze"
- Open questions: "wat weten we over", "beschrijf", "leg uit"

BOTH signals:
- Combined: "hoe presteren we" (numbers + context)
- Broad: "evalueer", "analyseer", "beoordeel"
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class QueryPlan:
    intent: str  # "structured", "semantic", "both"
    confidence: float  # 0.0 - 1.0
    reason: str
    merge_strategy: str  # "structured_first", "semantic_first", "interleaved"
    # Narrow endpoint routing (optional — for direct lookups)
    narrow_type: str | None = None  # "icp", "tone_of_voice", "company", "services"
    narrow_params: dict | None = None


# ---------------------------------------------------------------------------
# Keyword / pattern sets
# ---------------------------------------------------------------------------

_STRUCTURED_KEYWORDS = {
    "hoeveel", "aantal", "gemiddeld", "gemiddelde", "totaal", "som",
    "vergelijk", "versus", "vs", "verschil", "meer dan", "minder dan",
    "trend", "groei", "daling", "stijging", "afgelopen kwartaal",
    "per segment", "per maand", "per week", "top 10", "top 5",
    "omzet", "revenue", "conversie", "pipeline", "deal", "deals",
    "percentage", "ratio", "kpi",
}

_SEMANTIC_KEYWORDS = {
    "wat is", "hoe spreken", "beschrijf", "leg uit", "vertel",
    "tone of voice", "schrijfstijl", "propositie", "werkwijze",
    "standpunt", "visie", "missie", "kernwaarden",
    "wat weten we", "kennis over", "informatie over",
}

_BOTH_KEYWORDS = {
    "hoe presteren", "evalueer", "analyseer", "beoordeel",
    "samenvatting", "overzicht", "rapportage", "rapport",
    "prestaties", "performance",
}

# Narrow endpoint patterns
_ICP_KEYWORDS = {"icp", "doelgroep", "klantprofiel", "ideal customer"}
_TOV_KEYWORDS = {"tone of voice", "schrijfstijl", "communicatiestijl", "toon"}
_COMPANY_KEYWORDS = {"bedrijfsprofiel", "over ons", "wie zijn we"}
_SERVICE_KEYWORDS = {"dienst", "diensten", "service", "services", "product", "aanbod"}
# Vul hier je eigen segmentnamen in voor narrow routing
_SEGMENT_NAMES: set[str] = set()

# Numeric patterns (signal structured intent)
_NUMERIC_PATTERN = re.compile(
    r"\b(hoeveel|aantal|[\d]+[%€]?|q[1-4]|kwartaal|maand|jaar)\b", re.IGNORECASE
)


class RuleBasedClassifier:
    """Keyword/pattern-based query classification for clear-cut cases."""

    def classify(self, query: str) -> QueryPlan:
        q = query.lower().strip()

        # 1. Check for narrow endpoint matches (highest priority)
        narrow = self._check_narrow(q)
        if narrow:
            return narrow

        # 2. Score each intent
        structured_score = self._score_structured(q)
        semantic_score = self._score_semantic(q)
        both_score = self._score_both(q)

        # 3. Determine winner
        scores = {
            "structured": structured_score,
            "semantic": semantic_score,
            "both": both_score,
        }
        winner = max(scores, key=scores.get)
        confidence = scores[winner]

        # If nothing matched well, default to semantic with low confidence
        if confidence < 0.3:
            return QueryPlan(
                intent="semantic",
                confidence=0.2,
                reason="No strong keyword signals — defaulting to semantic search",
                merge_strategy="semantic_first",
            )

        merge_strategy = {
            "structured": "structured_first",
            "semantic": "semantic_first",
            "both": "structured_first",
        }[winner]

        return QueryPlan(
            intent=winner,
            confidence=confidence,
            reason=f"Keyword analysis: {winner} (score={confidence:.2f})",
            merge_strategy=merge_strategy,
        )

    def _check_narrow(self, q: str) -> QueryPlan | None:
        """Check if query maps directly to a narrow endpoint."""
        # ICP lookup
        if any(kw in q for kw in _ICP_KEYWORDS) or (
            any(seg in q for seg in _SEGMENT_NAMES)
            and not any(kw in q for kw in _STRUCTURED_KEYWORDS)
        ):
            segment = None
            for seg in _SEGMENT_NAMES:
                if seg in q:
                    segment = seg
                    break
            return QueryPlan(
                intent="semantic",
                confidence=0.95,
                reason="Query maps to ICP narrow endpoint",
                merge_strategy="semantic_first",
                narrow_type="icp",
                narrow_params={"segment": segment},
            )

        # Tone of voice
        if any(kw in q for kw in _TOV_KEYWORDS):
            return QueryPlan(
                intent="semantic",
                confidence=0.95,
                reason="Query maps to tone-of-voice narrow endpoint",
                merge_strategy="semantic_first",
                narrow_type="tone_of_voice",
            )

        # Company info
        if any(kw in q for kw in _COMPANY_KEYWORDS):
            return QueryPlan(
                intent="semantic",
                confidence=0.95,
                reason="Query maps to company narrow endpoint",
                merge_strategy="semantic_first",
                narrow_type="company",
            )

        # Services
        if any(kw in q for kw in _SERVICE_KEYWORDS):
            segment = None
            for seg in _SEGMENT_NAMES:
                if seg in q:
                    segment = seg
                    break
            return QueryPlan(
                intent="semantic",
                confidence=0.90,
                reason="Query maps to services narrow endpoint",
                merge_strategy="semantic_first",
                narrow_type="services",
                narrow_params={"segment": segment} if segment else None,
            )

        return None

    def _score_structured(self, q: str) -> float:
        hits = sum(1 for kw in _STRUCTURED_KEYWORDS if kw in q)
        numeric_hits = len(_NUMERIC_PATTERN.findall(q))
        return min(1.0, (hits * 0.25) + (numeric_hits * 0.2))

    def _score_semantic(self, q: str) -> float:
        hits = sum(1 for kw in _SEMANTIC_KEYWORDS if kw in q)
        return min(1.0, hits * 0.3)

    def _score_both(self, q: str) -> float:
        hits = sum(1 for kw in _BOTH_KEYWORDS if kw in q)
        # Also trigger "both" when structured AND semantic signals present
        has_structured = self._score_structured(q) > 0.2
        has_semantic = self._score_semantic(q) > 0.2
        combo_bonus = 0.3 if (has_structured and has_semantic) else 0.0
        return min(1.0, (hits * 0.3) + combo_bonus)
