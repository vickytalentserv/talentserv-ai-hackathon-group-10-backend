from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_or_create_user
from app.database import get_db
from app.models import Inquiry, Property, User
from app.schemas.inquiry import InquiryCreate, InquiryRead

router = APIRouter(prefix="/api/v1/inquiries", tags=["inquiries"])


@router.post("", response_model=InquiryRead, status_code=status.HTTP_201_CREATED)
def create_inquiry(
    payload: InquiryCreate,
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Inquiry:
    property_id = payload.property_id
    if property_id is not None and db.get(Property, property_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    inquiry = Inquiry(
        user_id=current_user.id,
        listing_key=payload.listing_key,
        property_id=property_id,
        name=payload.name.strip(),
        email=str(payload.email).strip(),
        phone=payload.phone.strip() if payload.phone else None,
        message=payload.message.strip(),
        status="submitted",
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)
    return inquiry
