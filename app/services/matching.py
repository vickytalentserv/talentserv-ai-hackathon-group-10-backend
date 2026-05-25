from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Select, or_, select

from app.models import Property
from app.schemas.requirement import ParsedRequirement

USD_TO_INR = Decimal("83")  # used when budget is entered in USD against INR listings

INTENT_TO_LISTING_STATUS = {
    "buy": "for_sale",
    "rent": "for_rent",
}

PROPERTY_TYPE_ALIASES: dict[str, set[str]] = {
    "apartment": {"apartment", "condo", "flat"},
    "house": {"house", "townhome", "villa", "bungalow"},
    "villa": {"villa", "house", "bungalow"},
    "flat": {"flat", "apartment"},
    "condo": {"condo", "apartment", "flat"},
    "townhome": {"townhome", "house", "villa"},
}

CITY_ALIASES = {
    "bangalore": "bengaluru",
    "bombay": "mumbai",
}

CANDIDATE_LIMIT = 300


@dataclass
class PropertyMatchResult:
    property: Property
    score: float
    reasons: list[str]


class MatchingService:
    def build_candidate_query(self, parsed: ParsedRequirement) -> Select[tuple[Property]]:
        query = select(Property)
        has_filters = False

        if parsed.intent:
            expected = INTENT_TO_LISTING_STATUS.get(parsed.intent)
            if expected:
                query = query.where(Property.listing_status == expected)
                has_filters = True

        if parsed.bedrooms is not None:
            min_bedrooms = max(0, parsed.bedrooms - 1)
            query = query.where(Property.bedrooms.between(min_bedrooms, parsed.bedrooms + 1))
            has_filters = True

        if parsed.city:
            city = parsed.city.strip()
            alias = CITY_ALIASES.get(city.lower(), city)
            pattern = f"%{city}%"
            alias_pattern = f"%{alias}%"
            query = query.where(
                or_(
                    Property.city.ilike(pattern),
                    Property.city.ilike(alias_pattern),
                    Property.address.ilike(pattern),
                    Property.title.ilike(pattern),
                )
            )
            has_filters = True

        if parsed.locality:
            locality_pattern = f"%{parsed.locality.strip()}%"
            query = query.where(
                or_(
                    Property.address.ilike(locality_pattern),
                    Property.title.ilike(locality_pattern),
                )
            )
            has_filters = True

        if parsed.property_type:
            aliases = PROPERTY_TYPE_ALIASES.get(
                parsed.property_type.lower(),
                {parsed.property_type.lower()},
            )
            query = query.where(Property.property_type.in_(sorted(aliases)))
            has_filters = True

        budget_min = parsed.budget_min
        budget_max = parsed.budget_max
        if parsed.budget_currency == "USD":
            if budget_min is not None:
                budget_min = budget_min * USD_TO_INR
            if budget_max is not None:
                budget_max = budget_max * USD_TO_INR

        if budget_max is not None:
            query = query.where(Property.price <= budget_max * Decimal("1.15"))
            has_filters = True

        if budget_min is not None:
            query = query.where(Property.price >= budget_min * Decimal("0.85"))
            has_filters = True

        if not has_filters:
            return select(Property).order_by(Property.id.desc()).limit(CANDIDATE_LIMIT)

        return query.order_by(Property.id.desc()).limit(CANDIDATE_LIMIT)

    def match(
        self,
        properties: list[Property],
        parsed: ParsedRequirement,
        *,
        min_score: float = 0.15,
        limit: int = 50,
    ) -> list[PropertyMatchResult]:
        scored: list[PropertyMatchResult] = []

        for property_record in properties:
            score, reasons = self._score_property(property_record, parsed)
            if score >= min_score:
                scored.append(
                    PropertyMatchResult(
                        property=property_record,
                        score=round(score, 4),
                        reasons=reasons,
                    )
                )

        scored.sort(key=lambda item: (-item.score, item.property.id))
        return scored[:limit]

    def _score_property(
        self,
        property_record: Property,
        parsed: ParsedRequirement,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        weights_used = 0.0

        intent_score, intent_reason = self._score_intent(property_record, parsed.intent)
        if parsed.intent is not None:
            weights_used += 0.2
            score += intent_score * 0.2
            if intent_reason:
                reasons.append(intent_reason)

        bedroom_score, bedroom_reason = self._score_bedrooms(property_record, parsed.bedrooms)
        if parsed.bedrooms is not None:
            weights_used += 0.2
            score += bedroom_score * 0.2
            if bedroom_reason:
                reasons.append(bedroom_reason)

        city_score, city_reason = self._score_city(property_record, parsed.city)
        if parsed.city is not None:
            weights_used += 0.2
            score += city_score * 0.2
            if city_reason:
                reasons.append(city_reason)

        locality_score, locality_reason = self._score_locality(property_record, parsed.locality)
        if parsed.locality is not None:
            weights_used += 0.15
            score += locality_score * 0.15
            if locality_reason:
                reasons.append(locality_reason)

        type_score, type_reason = self._score_property_type(property_record, parsed.property_type)
        if parsed.property_type is not None:
            weights_used += 0.1
            score += type_score * 0.1
            if type_reason:
                reasons.append(type_reason)

        budget_score, budget_reason = self._score_budget(property_record, parsed)
        if parsed.budget_min is not None or parsed.budget_max is not None:
            weights_used += 0.15
            score += budget_score * 0.15
            if budget_reason:
                reasons.append(budget_reason)

        keyword_score, keyword_reasons = self._score_keywords(property_record, parsed.raw_text)
        weights_used += 0.1
        score += keyword_score * 0.1
        reasons.extend(keyword_reasons)

        if weights_used == 0:
            score = 0.35
            reasons.append("General listing match")

        normalized = min(1.0, score / weights_used) if weights_used else score
        return normalized, reasons

    def _score_intent(
        self,
        property_record: Property,
        intent: str | None,
    ) -> tuple[float, str | None]:
        if intent is None:
            return 0.0, None

        expected = INTENT_TO_LISTING_STATUS.get(intent)
        if expected and property_record.listing_status == expected:
            label = "for sale" if intent == "buy" else "for rent"
            return 1.0, f"Intent match: {label}"

        if expected and property_record.listing_status != expected:
            return 0.0, None

        return 0.5, None

    def _score_bedrooms(
        self,
        property_record: Property,
        bedrooms: int | None,
    ) -> tuple[float, str | None]:
        if bedrooms is None:
            return 0.0, None

        diff = abs(property_record.bedrooms - bedrooms)
        if diff == 0:
            return 1.0, f"Bedrooms match: {bedrooms} BHK"
        if diff == 1:
            return 0.55, f"Close bedroom count: {property_record.bedrooms} BHK"
        return 0.0, None

    def _score_city(
        self,
        property_record: Property,
        city: str | None,
    ) -> tuple[float, str | None]:
        if city is None:
            return 0.0, None

        query = CITY_ALIASES.get(city.lower(), city.lower())
        record_city = CITY_ALIASES.get(property_record.city.lower(), property_record.city.lower())
        haystack = f"{property_record.city} {property_record.address} {property_record.title}".lower()
        if query == record_city or query in haystack:
            return 1.0, f"City match: {property_record.city}"
        return 0.0, None

    def _score_locality(
        self,
        property_record: Property,
        locality: str | None,
    ) -> tuple[float, str | None]:
        if locality is None:
            return 0.0, None

        query = locality.lower()
        haystack = f"{property_record.address} {property_record.title} {property_record.city}".lower()
        if query in haystack:
            return 1.0, f"Locality match: {locality}"
        return 0.0, None

    def _score_property_type(
        self,
        property_record: Property,
        property_type: str | None,
    ) -> tuple[float, str | None]:
        if property_type is None:
            return 0.0, None

        actual = property_record.property_type.lower()
        expected = property_type.lower()
        aliases = PROPERTY_TYPE_ALIASES.get(expected, {expected})

        if actual in aliases:
            return 1.0, f"Property type match: {property_record.property_type}"

        return 0.0, None

    def _score_budget(
        self,
        property_record: Property,
        parsed: ParsedRequirement,
    ) -> tuple[float, str | None]:
        price_inr = Decimal(property_record.price)

        budget_min = parsed.budget_min
        budget_max = parsed.budget_max

        if parsed.budget_currency == "USD":
            if budget_min is not None:
                budget_min = budget_min * USD_TO_INR
            if budget_max is not None:
                budget_max = budget_max * USD_TO_INR

        if budget_min is not None and price_inr < budget_min * Decimal("0.85"):
            return 0.0, None

        if budget_max is not None:
            if price_inr <= budget_max:
                return 1.0, "Within budget"
            if price_inr <= budget_max * Decimal("1.15"):
                return 0.6, "Slightly above budget"
            return 0.0, None

        if budget_min is not None:
            return 1.0, "Above minimum budget"

        return 0.0, None

    def _score_keywords(
        self,
        property_record: Property,
        raw_text: str,
    ) -> tuple[float, list[str]]:
        stopwords = {
            "a",
            "an",
            "the",
            "in",
            "on",
            "at",
            "for",
            "to",
            "of",
            "and",
            "or",
            "with",
            "near",
            "under",
            "below",
            "want",
            "looking",
            "show",
            "buy",
            "rent",
            "bhk",
            "bedroom",
            "bedrooms",
            "flat",
            "property",
            "apartment",
            "house",
        }
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", raw_text.lower())
            if len(token) > 2 and token not in stopwords
        ]
        if not tokens:
            return 0.0, []

        haystack = " ".join(
            filter(
                None,
                [
                    property_record.title,
                    property_record.description,
                    property_record.address,
                    property_record.city,
                ],
            )
        ).lower()

        hits = [token for token in tokens if token in haystack]
        if not hits:
            return 0.0, []

        ratio = min(1.0, len(hits) / max(1, min(len(tokens), 4)))
        reasons = [f"Keyword match: {hit}" for hit in hits[:2]]
        return ratio, reasons
