from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_optional_user
from app.database import get_db
from app.models import Property, Requirement, User
from app.schemas.match import PropertyMatchItem, PropertyMatchRequest, PropertyMatchResponse
from app.schemas.property import PropertyListResponse, PropertyRead
from app.schemas.requirement import ParsedRequirement
from app.config import settings
from app.services.llm_matching import LLMMatchingService
from app.services.matching import MatchingService
from app.services.parser import ParserService

router = APIRouter(prefix="/api/v1", tags=["properties"])
parser_service = ParserService()
matching_service = MatchingService()
llm_matching_service = LLMMatchingService()

INTENT_TO_LISTING_STATUS = {
    "buy": "for_sale",
    "rent": "for_rent",
}

SORT_OPTIONS = {
    "newest": Property.id.desc(),
    "price-asc": Property.price.asc(),
    "price-desc": Property.price.desc(),
}


def _requirement_to_parsed(requirement: Requirement) -> ParsedRequirement:
    return ParsedRequirement(
        raw_text=requirement.raw_text,
        intent=requirement.intent,  # type: ignore[arg-type]
        bedrooms=requirement.bedrooms,
        budget_min=requirement.budget_min,
        budget_max=requirement.budget_max,
        budget_currency=requirement.budget_currency,
        locality=requirement.locality,
        city=requirement.city,
        property_type=requirement.property_type,
        parser=requirement.parser,
        confidence=float(requirement.confidence),
    )


@router.get("/properties", response_model=PropertyListResponse)
def list_properties(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    source: str | None = None,
    city: str | None = None,
    state: str | None = None,
    listing_status: str | None = None,
    bedrooms: int | None = Query(default=None, ge=0),
    property_type: str | None = None,
    budget_min: Decimal | None = Query(default=None, ge=0),
    budget_max: Decimal | None = Query(default=None, ge=0),
    intent: str | None = Query(default=None, pattern="^(buy|rent)$"),
    sort: str = Query(default="newest", pattern="^(newest|price-asc|price-desc)$"),
    db: Session = Depends(get_db),
) -> PropertyListResponse:
    query = select(Property)
    count_query = select(func.count()).select_from(Property)

    if search:
        pattern = f"%{search.strip()}%"
        search_filter = or_(
            Property.title.ilike(pattern),
            Property.address.ilike(pattern),
            Property.city.ilike(pattern),
            Property.description.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    filters = [
        (source, lambda q: q.where(Property.source == source)),
        (city, lambda q: q.where(Property.city.ilike(f"%{city}%"))),
        (state, lambda q: q.where(Property.state == state.upper())),
        (listing_status, lambda q: q.where(Property.listing_status == listing_status)),
        (bedrooms, lambda q: q.where(Property.bedrooms == bedrooms)),
        (property_type, lambda q: q.where(Property.property_type == property_type)),
        (budget_min, lambda q: q.where(Property.price >= budget_min)),
        (budget_max, lambda q: q.where(Property.price <= budget_max)),
    ]

    if intent:
        mapped_status = INTENT_TO_LISTING_STATUS.get(intent)
        if mapped_status:
            query = query.where(Property.listing_status == mapped_status)
            count_query = count_query.where(Property.listing_status == mapped_status)

    for value, apply_filter in filters:
        if value is not None:
            query = apply_filter(query)
            count_query = apply_filter(count_query)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * page_size
    order_by = SORT_OPTIONS.get(sort, Property.id.desc())
    items = db.scalars(query.order_by(order_by).offset(offset).limit(page_size)).all()

    return PropertyListResponse(
        items=[PropertyRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/properties/match", response_model=PropertyMatchResponse)
def match_properties(
    payload: PropertyMatchRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> PropertyMatchResponse:
    parsed: ParsedRequirement

    if payload.text:
        parsed = parser_service.parse(payload.text.strip())
    else:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required when matching by requirement_id",
            )

        requirement = db.scalar(
            select(Requirement).where(
                Requirement.id == payload.requirement_id,
                Requirement.user_id == current_user.id,
            )
        )
        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found",
            )
        parsed = _requirement_to_parsed(requirement)

    candidate_query = matching_service.build_candidate_query(parsed)
    properties = db.scalars(candidate_query).all()
    match_relaxed = False

    if not properties:
        relaxed_query = matching_service.build_relaxed_candidate_query(parsed)
        properties = db.scalars(relaxed_query).all()
        match_relaxed = bool(properties)

    matches = matching_service.match(
        properties,
        parsed,
        min_score=payload.min_score,
        limit=payload.limit,
    )

    if match_relaxed:
        for match in matches:
            match.reasons.insert(0, "Similar listing — exact rent/budget matches unavailable in database")

    match_source = "database"
    if match_relaxed:
        match_source = "database+relaxed"
    if settings.openai_match_rerank:
        matches, llm_used = llm_matching_service.rerank(
            parsed,
            matches,
            limit=settings.openai_match_rerank_limit,
        )
        if llm_used:
            match_source = "database+llm"

    return PropertyMatchResponse(
        items=[
            PropertyMatchItem(
                property=PropertyRead.model_validate(match.property),
                score=match.score,
                reasons=match.reasons,
            )
            for match in matches
        ],
        parsed=parsed,
        total=len(matches),
        source=match_source,
        relaxed=match_relaxed,
    )


@router.get("/properties/{property_id}", response_model=PropertyRead)
def get_property(property_id: int, db: Session = Depends(get_db)) -> Property:
    property_record = db.get(Property, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return property_record
