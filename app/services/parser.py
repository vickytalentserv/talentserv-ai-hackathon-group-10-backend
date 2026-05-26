import json
import re
from decimal import Decimal

from app.config import settings
from app.schemas.requirement import ParsedRequirement

KNOWN_CITIES = {
    "pune": "Pune",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
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
}

PROPERTY_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("apartment", re.compile(r"\b(apartment|flat|condo|condominium)\b", re.I)),
    ("house", re.compile(r"\b(house|villa|bungalow|townhome|townhouse)\b", re.I)),
]


class ParserService:
    BEDROOM_PATTERN = re.compile(
        r"\b(\d+)\s*(?:bhk|bedroom|bedrooms|bed|beds|br)\b",
        re.I,
    )
    CRORE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", re.I)
    LAKH_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)\b", re.I)
    USD_AMOUNT_PATTERN = re.compile(
        r"(?:\$|usd\s*)?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:k|K|million|m|mn)?\b",
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

        if settings.openai_api_key:
            result = self._maybe_enhance_with_llm(normalized, result)

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

        amounts = [self._parse_amount(match.group(0)) for match in self.USD_AMOUNT_PATTERN.finditer(text)]
        crore_matches = [self._parse_amount(match.group(0)) for match in self.CRORE_PATTERN.finditer(text)]
        lakh_matches = [self._parse_amount(match.group(0)) for match in self.LAKH_PATTERN.finditer(text)]
        all_amounts = [item for item in amounts + crore_matches + lakh_matches if item is not None]

        if len(all_amounts) == 1:
            result.budget_max = all_amounts[0][0]
            result.budget_currency = all_amounts[0][1]
        elif len(all_amounts) >= 2:
            values = sorted(item[0] for item in all_amounts)
            result.budget_min = values[0]
            result.budget_max = values[-1]
            result.budget_currency = all_amounts[0][1]

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

        usd = self.USD_AMOUNT_PATTERN.search(fragment)
        if usd:
            value = Decimal(usd.group(1))
            suffix = fragment.lower()
            if "k" in suffix and "million" not in suffix and "mn" not in suffix:
                value *= Decimal("1000")
            elif re.search(r"\b(?:million|mn|m)\b", suffix):
                value *= Decimal("1000000")
            return value, "USD"

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
        try:
            import httpx

            prompt = (
                "Extract real estate search filters from the user text. "
                "Return JSON with keys: intent, bedrooms, budget_min, budget_max, "
                "budget_currency, locality, city, property_type. Use null when unknown.\n"
                f"Text: {text}\n"
                f"Existing rule parse: {result.model_dump(mode='json')}"
            )
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": "You return only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            payload = json.loads(content)
            merged = result.model_dump()
            for key, value in payload.items():
                if value is not None and merged.get(key) in (None, "", 0):
                    merged[key] = value
            merged["parser"] = "rules+llm"
            merged["confidence"] = min(1.0, result.confidence + 0.1)
            return ParsedRequirement.model_validate(merged)
        except Exception:
            return result
