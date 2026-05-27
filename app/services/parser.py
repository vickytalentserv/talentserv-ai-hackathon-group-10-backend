import re
from decimal import Decimal

from app.schemas.requirement import ParsedRequirement
from app.services.openai_service import OpenAIService

LLM_PARSE_SYSTEM = (
    "You extract structured Indian real estate search filters from natural language. "
    "Return JSON with keys: intent (buy|rent|null), bedrooms (int|null), budget_min, "
    "budget_max, budget_currency (INR|USD), locality, city, property_type "
    "(apartment|house|flat|villa|null). Use null when unknown. "
    "Default budget_currency to INR for all Indian property searches. "
    "Only use USD when the user explicitly mentions $, USD, or dollars. "
    "Treat 40k, 50k, lakh, and crore as INR amounts. "
    "Normalize city names: Bengaluru/Bangalore, Mumbai/Bombay, Gurugram/Gurgaon. "
    "Map localities to the correct city when possible, e.g. Koramangala -> Bengaluru, "
    "Borivali/Mira Road/Santacruz -> Mumbai, Baner/Hinjewadi -> Pune."
)

KNOWN_CITIES = {
    "pune": "Pune",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "chennai": "Chennai",
    "hyderabad": "Hyderabad",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "kolkata": "Kolkata",
}

KNOWN_LOCALITIES = {
    "baner": "Baner",
    "hinjewadi": "Hinjewadi",
    "koregaon park": "Koregaon Park",
    "wakad": "Wakad",
    "kharadi": "Kharadi",
    "magarpatta": "Magarpatta",
    "aundh": "Aundh",
    "viman nagar": "Viman Nagar",
    "kothrud": "Kothrud",
    "hadapsar": "Hadapsar",
    "bandra": "Bandra West",
    "bandra west": "Bandra West",
    "andheri": "Andheri East",
    "andheri east": "Andheri East",
    "powai": "Powai",
    "worli": "Worli",
    "juhu": "Juhu",
    "goregaon": "Goregaon West",
    "chembur": "Chembur East",
    "malad": "Malad West",
    "thane": "Thane West",
    "kharghar": "Kharghar",
    "koramangala": "Koramangala",
    "indiranagar": "Indiranagar",
    "whitefield": "Whitefield",
    "hsr layout": "HSR Layout",
    "bellandur": "Bellandur",
    "electronic city": "Electronic City",
    "jayanagar": "Jayanagar",
    "marathahalli": "Marathahalli",
    "sarjapur": "Sarjapur",
    "hebbal": "Hebbal",
    "btm layout": "BTM Layout",
    "mg road": "MG Road",
    "mira road": "Mira Road",
    "santacruz": "Santacruz",
    "santacruz east": "Santacruz East",
    "santacruz west": "Santacruz West",
    "borivali": "Borivali",
    "borivali west": "Borivali West",
    "lower parel": "Lower Parel",
    "dadar": "Dadar",
}

LOCALITY_TO_CITY = {
    "baner": "Pune",
    "hinjewadi": "Pune",
    "koregaon park": "Pune",
    "wakad": "Pune",
    "kharadi": "Pune",
    "magarpatta": "Pune",
    "aundh": "Pune",
    "viman nagar": "Pune",
    "kothrud": "Pune",
    "hadapsar": "Pune",
    "bandra": "Mumbai",
    "bandra west": "Mumbai",
    "andheri": "Mumbai",
    "andheri east": "Mumbai",
    "powai": "Mumbai",
    "worli": "Mumbai",
    "juhu": "Mumbai",
    "goregaon": "Mumbai",
    "goregaon west": "Mumbai",
    "chembur": "Mumbai",
    "chembur east": "Mumbai",
    "malad": "Mumbai",
    "malad west": "Mumbai",
    "thane": "Mumbai",
    "thane west": "Mumbai",
    "kharghar": "Mumbai",
    "lower parel": "Mumbai",
    "dadar": "Mumbai",
    "borivali": "Mumbai",
    "borivali west": "Mumbai",
    "koramangala": "Bengaluru",
    "indiranagar": "Bengaluru",
    "whitefield": "Bengaluru",
    "hsr layout": "Bengaluru",
    "bellandur": "Bengaluru",
    "electronic city": "Bengaluru",
    "jayanagar": "Bengaluru",
    "marathahalli": "Bengaluru",
    "sarjapur": "Bengaluru",
    "hebbal": "Bengaluru",
    "btm layout": "Bengaluru",
    "mg road": "Bengaluru",
    "yelahanka": "Bengaluru",
    "mira road": "Mumbai",
    "santacruz": "Mumbai",
    "santacruz east": "Mumbai",
    "santacruz west": "Mumbai",
}

PROPERTY_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("apartment", re.compile(r"\b(apartment|flat|condo|condominium)\b", re.I)),
    ("house", re.compile(r"\b(house|villa|bungalow|townhome|townhouse)\b", re.I)),
]


class ParserService:
    def __init__(self, openai_service: OpenAIService | None = None) -> None:
        self.openai = openai_service or OpenAIService()

    BEDROOM_PATTERN = re.compile(
        r"\b(\d+)\s*(?:bhk|bedroom|bedrooms|bed|beds|br)\b",
        re.I,
    )
    CRORE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", re.I)
    LAKH_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)\b", re.I)
    INR_AMOUNT_PATTERN = re.compile(
        r"(?:₹|rs\.?\s*|inr\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:k|K|lakh|lac|crore|cr)?\b",
        re.I,
    )
    USD_AMOUNT_PATTERN = re.compile(
        r"(?:\$|usd\s*)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:k|K|million|m|mn)?\b",
        re.I,
    )
    UNDER_PATTERN = re.compile(
        r"(?:under|below|upto|up to|max|maximum|less than)\s+(.+?)(?:\s+in|\s+near|\s+at|\s+for|$)",
        re.I,
    )
    BETWEEN_PATTERN = re.compile(
        r"(?:between|from)\s+(.+?)\s+(?:and|to)\s+(.+?)(?:\s+in|\s+near|\s+at|\s+for|$)",
        re.I,
    )
    RENT_PATTERN = re.compile(r"\b(rent|rental|lease|for rent|to rent|renting)\b", re.I)
    BUY_PATTERN = re.compile(r"\b(buy|purchase|for sale|to buy|buying)\b", re.I)
    IN_LOCALITY_PATTERN = re.compile(
        r"\b(?:in|near|around|at)\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:\s+under|\s+between|\s+for|\s+with|$)",
        re.I,
    )
    GENERIC_LOCATION_SUFFIX = re.compile(
        r"\s+(?:area|region|city|limits|vicinity)\s*$",
        re.I,
    )

    def parse(self, text: str) -> ParsedRequirement:
        normalized = " ".join(text.strip().split())
        result = ParsedRequirement(raw_text=normalized, parser="rules", confidence=0.5)

        self._apply_intent(normalized, result)
        self._apply_bedrooms(normalized, result)
        self._apply_budget(normalized, result)
        self._apply_locations(normalized, result)
        self._apply_property_type(normalized, result)
        result.confidence = self._score_confidence(result)

        if self.openai.is_enabled():
            result = self._maybe_enhance_with_llm(normalized, result)

        return self._finalize_parsed_requirement(result)

    def _finalize_parsed_requirement(self, result: ParsedRequirement) -> ParsedRequirement:
        if result.locality:
            result.locality = self._clean_locality(result.locality, result.city)

        raw = result.raw_text.lower()
        explicit_usd = "$" in raw or "usd" in raw or "dollar" in raw
        if not explicit_usd:
            result.budget_currency = "INR"

        result.confidence = self._score_confidence(result)
        return result

    def _apply_intent(self, text: str, result: ParsedRequirement) -> None:
        rent_match = self.RENT_PATTERN.search(text)
        buy_match = self.BUY_PATTERN.search(text)
        if rent_match and not buy_match:
            result.intent = "rent"
        elif buy_match and not rent_match:
            result.intent = "buy"
        elif rent_match and buy_match:
            result.intent = "rent" if rent_match.start() < buy_match.start() else "buy"

    def _apply_bedrooms(self, text: str, result: ParsedRequirement) -> None:
        match = self.BEDROOM_PATTERN.search(text)
        if match:
            result.bedrooms = int(match.group(1))

    def _apply_budget(self, text: str, result: ParsedRequirement) -> None:
        between = self.BETWEEN_PATTERN.search(text)
        if between:
            min_amount = self._parse_amount(between.group(1))
            max_amount = self._parse_amount(between.group(2))
            if min_amount is not None:
                result.budget_min = min_amount[0]
                result.budget_currency = min_amount[1]
            if max_amount is not None:
                result.budget_max = max_amount[0]
                result.budget_currency = max_amount[1]
            return

        under = self.UNDER_PATTERN.search(text)
        if under:
            parsed = self._parse_amount(under.group(1))
            if parsed is not None:
                result.budget_max = parsed[0]
                result.budget_currency = parsed[1]
            return

        amounts = [
            self._parse_amount(match.group(0))
            for match in self.INR_AMOUNT_PATTERN.finditer(text)
            if not self._is_bedroom_amount_match(text, match)
        ]
        usd_amounts = [
            self._parse_amount(match.group(0))
            for match in self.USD_AMOUNT_PATTERN.finditer(text)
            if not self._is_bedroom_amount_match(text, match)
        ]
        crore_matches = [self._parse_amount(match.group(0)) for match in self.CRORE_PATTERN.finditer(text)]
        lakh_matches = [self._parse_amount(match.group(0)) for match in self.LAKH_PATTERN.finditer(text)]
        all_amounts = [
            item for item in amounts + usd_amounts + crore_matches + lakh_matches if item is not None
        ]

        if len(all_amounts) == 1:
            result.budget_max = all_amounts[0][0]
            result.budget_currency = all_amounts[0][1]
        elif len(all_amounts) >= 2:
            values = sorted(item[0] for item in all_amounts)
            result.budget_min = values[0]
            result.budget_max = values[-1]
            result.budget_currency = all_amounts[0][1]

    def _is_bedroom_amount_match(self, text: str, match: re.Match[str]) -> bool:
        window = text[max(0, match.start() - 8) : match.end() + 12].lower()
        return bool(re.search(r"\b(bhk|bedroom|bedrooms|bed|beds|br)\b", window))

    def _parse_amount(self, fragment: str) -> tuple[Decimal, str] | None:
        fragment = fragment.strip().replace(",", "")
        crore = self.CRORE_PATTERN.search(fragment)
        if crore:
            value = Decimal(crore.group(1)) * Decimal("10000000")
            return value, "INR"

        lakh = self.LAKH_PATTERN.search(fragment)
        if lakh:
            value = Decimal(lakh.group(1)) * Decimal("100000")
            return value, "INR"

        if "$" not in fragment and "usd" not in fragment.lower():
            inr_k = re.search(r"(\d+(?:\.\d+)?)\s*k\b", fragment, re.I)
            if inr_k:
                value = Decimal(inr_k.group(1)) * Decimal("1000")
                return value, "INR"

            rupee = re.search(r"(?:₹|rs\.?\s*|inr\s*)(\d+(?:,\d{3})*(?:\.\d+)?)", fragment, re.I)
            if rupee:
                value = Decimal(rupee.group(1).replace(",", ""))
                return value, "INR"

        usd = self.USD_AMOUNT_PATTERN.search(fragment)
        if usd and ("$" in fragment or "usd" in fragment.lower()):
            value = Decimal(usd.group(1).replace(",", ""))
            suffix = fragment.lower()
            if "k" in suffix and "million" not in suffix and "mn" not in suffix:
                value *= Decimal("1000")
            elif re.search(r"\b(?:million|mn|m)\b", suffix):
                value *= Decimal("1000000")
            return value, "USD"

        if "$" not in fragment and "usd" not in fragment.lower():
            digits = re.sub(r"[^\d.]", "", fragment)
            if digits and re.fullmatch(r"[\d,]+(?:\.\d+)?", fragment.strip()):
                value = Decimal(digits)
                if value > 0:
                    return value, "INR"

        return None

    def _apply_locations(self, text: str, result: ParsedRequirement) -> None:
        lowered = text.lower()
        for key, city in KNOWN_CITIES.items():
            if re.search(rf"\b{re.escape(key)}\b", lowered):
                result.city = city

        for key, locality in KNOWN_LOCALITIES.items():
            if re.search(rf"\b{re.escape(key)}\b", lowered):
                result.locality = locality
                if result.city is None:
                    result.city = LOCALITY_TO_CITY.get(key)

        if result.locality is None:
            match = self.IN_LOCALITY_PATTERN.search(text)
            if match:
                candidate = self._normalize_location_phrase(match.group(1).strip(" .,"))
                candidate_key = candidate.lower()
                if candidate_key in KNOWN_CITIES:
                    result.city = KNOWN_CITIES[candidate_key]
                elif candidate_key in KNOWN_LOCALITIES:
                    result.locality = KNOWN_LOCALITIES[candidate_key]
                    if result.city is None:
                        result.city = LOCALITY_TO_CITY.get(candidate_key)
                elif candidate_key not in KNOWN_CITIES and len(candidate.split()) <= 4:
                    if result.city and candidate_key == result.city.lower():
                        pass
                    else:
                        result.locality = candidate.title()
                        if result.city is None:
                            result.city = LOCALITY_TO_CITY.get(candidate_key)

    def _normalize_location_phrase(self, phrase: str) -> str:
        return self.GENERIC_LOCATION_SUFFIX.sub("", phrase.strip()).strip()

    def _clean_locality(self, locality: str | None, city: str | None) -> str | None:
        if not locality:
            return None

        cleaned = locality.strip()
        cleaned_lower = cleaned.lower()
        if cleaned_lower in KNOWN_LOCALITIES:
            return KNOWN_LOCALITIES[cleaned_lower]

        if city:
            city_lower = city.lower()
            if cleaned_lower.endswith(city_lower):
                cleaned = cleaned[: -len(city)].strip(" ,")
                cleaned_lower = cleaned.lower()

        for city_key in KNOWN_CITIES:
            if cleaned_lower.endswith(city_key):
                cleaned = cleaned[: -len(city_key)].strip(" ,")
                break

        if not cleaned or cleaned.lower() in KNOWN_CITIES:
            return None

        key = cleaned.lower()
        if key in KNOWN_LOCALITIES:
            return KNOWN_LOCALITIES[key]
        return cleaned.title()

    def _apply_property_type(self, text: str, result: ParsedRequirement) -> None:
        for property_type, pattern in PROPERTY_TYPE_PATTERNS:
            if pattern.search(text):
                result.property_type = property_type
                break

    def _score_confidence(self, result: ParsedRequirement) -> float:
        fields = [
            result.intent,
            result.bedrooms,
            result.budget_min or result.budget_max,
            result.city or result.locality,
        ]
        filled = sum(1 for field in fields if field is not None)
        return round(0.25 + (filled * 0.15), 2)

    def _maybe_enhance_with_llm(self, text: str, result: ParsedRequirement) -> ParsedRequirement:
        payload = self.openai.chat_json(
            system=LLM_PARSE_SYSTEM,
            user=(
                f"User query: {text}\n"
                f"Existing rule parse: {result.model_dump(mode='json')}\n"
                "Improve missing or weak fields. Keep valid rule values unless clearly wrong."
            ),
        )
        if not isinstance(payload, dict):
            return result

        merged = result.model_dump()
        merge_keys = (
            "intent",
            "bedrooms",
            "budget_min",
            "budget_max",
            "budget_currency",
            "locality",
            "city",
            "property_type",
        )
        for key in merge_keys:
            value = payload.get(key)
            if value is None:
                continue
            current = merged.get(key)
            if current in (None, "", 0) or result.confidence < 0.65:
                merged[key] = value

        merged["parser"] = "rules+llm"
        merged["confidence"] = min(
            1.0,
            max(result.confidence, self._score_confidence(ParsedRequirement.model_validate(merged))) + 0.1,
        )
        return self._finalize_parsed_requirement(ParsedRequirement.model_validate(merged))
