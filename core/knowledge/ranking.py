# core/knowledge/ranking.py
"""Deterministic ranking for knowledge retrieval.

Inputs:
    query text
    domain filter (optional)
    primitive candidates

Output:
    ranked candidates with scores and reasons

Ranking is intentionally deterministic and explainable. No embeddings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.knowledge.schema import Primitive, KnowledgeStatus


# Minimum length for tokenisation
_MIN_TOKEN_LEN = 2


def tokenize(text: str) -> list[str]:
    """Tokenise a string: lowercase, split on non-alphanumeric."""
    if not text:
        return []
    return [t.lower() for t in re.findall(r"[A-Za-z0-9_]+", text) if len(t) >= _MIN_TOKEN_LEN]


@dataclass
class Score:
    primitive_id: str
    score: float
    reasons: list[str] = field(default_factory=list)


class Ranker:
    """Deterministic multi-signal ranker.

    Signals (weighted):
        - exact term match in concept/description    (3.0)
        - partial token match in concept/description  (1.5)
        - domain match                                (2.0)
        - prerequisites match                         (1.0)
        - verification_method overlap                 (0.5)
        - confidence                                  (2.0 * confidence)
        - success_rate                                (1.5 * rate)
        - recency boost (very light)                  (0.1)
        - active status bonus                         (1.0)
    """

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or {
            "exact": 3.0,
            "partial": 1.5,
            "domain": 2.0,
            "prereq": 1.0,
            "verify": 0.5,
            "confidence": 2.0,
            "success": 1.5,
            "recency": 0.1,
            "active": 1.0,
        }

    def rank(self, query: str, candidates: list[Primitive],
             domain: Optional[str] = None,
             top_k: int = 10) -> list[Score]:
        if not candidates:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        results: list[Score] = []
        for prim in candidates:
            score, reasons = self._score_one(prim, query_tokens, query, domain)
            results.append(Score(primitive_id=prim.id, score=score, reasons=reasons))

        results.sort(key=lambda s: (-s.score, s.primitive_id))
        return results[:top_k]

    def _score_one(self, prim: Primitive, query_tokens: list[str],
                    raw_query: str, domain: Optional[str]) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        # Tokenise primitive content
        concept_tokens = tokenize(prim.concept)
        desc_tokens = tokenize(prim.description)
        when_tokens = tokenize(prim.when_to_use)
        prereq_tokens = tokenize(" ".join(prim.prerequisites))
        verify_tokens = tokenize(prim.verification_method)

        qset = set(query_tokens)
        concept_set = set(concept_tokens)
        desc_set = set(desc_tokens)
        when_set = set(when_tokens)
        prereq_set = set(prereq_tokens)
        verify_set = set(verify_tokens)

        # Exact match (full query as substring)
        q_lower = raw_query.lower()
        if prim.concept and q_lower in prim.concept.lower():
            score += self.weights["exact"]
            reasons.append("concept: exact match")
        elif prim.description and q_lower in prim.description.lower():
            score += self.weights["exact"] * 0.7
            reasons.append("description: exact substring")

        # Partial token match
        overlap = qset & concept_set
        if overlap:
            score += self.weights["partial"] * len(overlap)
            reasons.append(f"concept tokens: {sorted(overlap)[:3]}")
        overlap_d = qset & desc_set
        if overlap_d:
            score += self.weights["partial"] * 0.7 * len(overlap_d)
            reasons.append(f"description tokens: {sorted(overlap_d)[:3]}")
        overlap_w = qset & when_set
        if overlap_w:
            score += self.weights["partial"] * 0.5 * len(overlap_w)
            reasons.append(f"when_to_use tokens: {sorted(overlap_w)[:3]}")

        # Domain match
        if domain and prim.domain == domain:
            score += self.weights["domain"]
            reasons.append(f"domain match: {domain}")
        elif domain and prim.domain:
            # Partial domain match
            if domain in prim.domain or prim.domain in domain:
                score += self.weights["domain"] * 0.5
                reasons.append("domain partial match")

        # Prerequisites overlap
        prereq_overlap = qset & prereq_set
        if prereq_overlap:
            score += self.weights["prereq"] * len(prereq_overlap)
            reasons.append(f"prereq tokens: {sorted(prereq_overlap)[:3]}")

        # Verification method overlap
        verify_overlap = qset & verify_set
        if verify_overlap:
            score += self.weights["verify"] * len(verify_overlap)
            reasons.append("verification tokens match")

        # Confidence
        if prim.confidence > 0:
            score += self.weights["confidence"] * prim.confidence
            reasons.append(f"confidence={prim.confidence:.2f}")

        # Success rate
        if prim.usage_count > 0:
            rate = prim.success_rate()
            score += self.weights["success"] * rate
            reasons.append(f"success_rate={rate:.2f} ({prim.success_count}/{prim.usage_count})")

        # Active bonus
        if prim.is_usable():
            score += self.weights["active"]
            reasons.append("status=ACTIVE")
        elif prim.status == KnowledgeStatus.VERIFIED.value:
            score += 0.3
            reasons.append("status=VERIFIED")

        return (round(score, 4), reasons)
