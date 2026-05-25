from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_or_create_user
from app.database import get_db
from app.models import Requirement, User
from app.schemas.requirement import (
    ParsedRequirement,
    RequirementParseRequest,
    RequirementParseResponse,
    RequirementRead,
    RequirementSaveRequest,
)
from app.services.parser import ParserService

router = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])
parser_service = ParserService()


@router.post("/parse", response_model=RequirementParseResponse)
def parse_requirement(payload: RequirementParseRequest) -> RequirementParseResponse:
    parsed = parser_service.parse(payload.text)
    return RequirementParseResponse(parsed=parsed)


@router.post("", response_model=RequirementRead)
def save_requirement(
    payload: RequirementSaveRequest,
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Requirement:
    parsed = payload.parsed
    record = Requirement(
        user_id=current_user.id,
        raw_text=payload.text,
        intent=parsed.intent,
        bedrooms=parsed.bedrooms,
        budget_min=parsed.budget_min,
        budget_max=parsed.budget_max,
        budget_currency=parsed.budget_currency,
        locality=parsed.locality,
        city=parsed.city,
        property_type=parsed.property_type,
        parser=parsed.parser,
        confidence=parsed.confidence,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/latest", response_model=RequirementRead | None)
def get_latest_requirement(
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Requirement | None:
    return db.scalar(
        select(Requirement)
        .where(Requirement.user_id == current_user.id)
        .order_by(Requirement.id.desc())
        .limit(1)
    )
