from __future__ import annotations

from dataclasses import replace

from app.models import Property
from app.schemas.requirement import ParsedRequirement
from app.services.matching import PropertyMatchResult
from app.services.openai_service import OpenAIService

RERANK_SYSTEM_PROMPT = (
    "You rerank Indian real estate listings against a buyer or renter query. "
    "Prefer exact city, locality, BHK, budget, and buy/rent intent matches. "
    "Return only valid JSON with key rankings: an array of objects with "
    "property_id (int), score (0 to 1), and reason (short phrase). "
    "Include only property_id values from the candidate list. "
    "Order rankings from best to worst."
)


class LLMMatchingService:
    def __init__(self, openai_service: OpenAIService | None = None) -> None:
        self.openai = openai_service or OpenAIService()

    def rerank(
        self,
        parsed: ParsedRequirement,
        matches: list[PropertyMatchResult],
        *,
        limit: int,
    ) -> tuple[list[PropertyMatchResult], bool]:
        if not self.openai.is_enabled() or len(matches) < 2:
            return matches, False

        candidates = matches[:limit]
        payload = self.openai.chat_json(
            system=RERANK_SYSTEM_PROMPT,
            user=self._build_prompt(parsed, candidates),
        )
        if not isinstance(payload, dict):
            return matches, False

        rankings = payload.get("rankings")
        if not isinstance(rankings, list):
            return matches, False

        reranked = self._apply_rankings(candidates, rankings)
        if not reranked:
            return matches, False

        tail = matches[limit:]
        return reranked + tail, True

    def _build_prompt(
        self,
        parsed: ParsedRequirement,
        candidates: list[PropertyMatchResult],
    ) -> str:
        requirement = parsed.model_dump(mode="json")
        listings = [
            {
                "property_id": match.property.id,
                "title": match.property.title[:160],
                "city": match.property.city,
                "address": match.property.address[:120],
                "price_inr": str(match.property.price),
                "bedrooms": match.property.bedrooms,
                "property_type": match.property.property_type,
                "listing_status": match.property.listing_status,
                "rule_score": match.score,
                "rule_reasons": match.reasons[:3],
            }
            for match in candidates
        ]
        return (
            f"User query: {parsed.raw_text}\n"
            f"Parsed requirement: {requirement}\n"
            f"Candidate listings: {listings}"
        )

    def _apply_rankings(
        self,
        candidates: list[PropertyMatchResult],
        rankings: list[object],
    ) -> list[PropertyMatchResult]:
        by_id = {match.property.id: match for match in candidates}
        reranked: list[PropertyMatchResult] = []
        seen: set[int] = set()

        for item in rankings:
            if not isinstance(item, dict):
                continue

            property_id = item.get("property_id")
            llm_score = item.get("score")
            reason = item.get("reason")
            if not isinstance(property_id, int) or property_id not in by_id:
                continue
            if property_id in seen:
                continue
            if not isinstance(llm_score, (int, float)):
                continue

            seen.add(property_id)
            original = by_id[property_id]
            blended_score = round(min(1.0, (original.score * 0.55) + (float(llm_score) * 0.45)), 4)
            reasons = [str(reason)] if reason else []
            reasons.extend(original.reasons[:1])
            reranked.append(
                replace(
                    original,
                    score=blended_score,
                    reasons=reasons[:3],
                )
            )

        for match in candidates:
            if match.property.id not in seen:
                reranked.append(match)

        reranked.sort(key=lambda item: (-item.score, item.property.id))
        return reranked
