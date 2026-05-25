from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_or_create_user
from app.database import get_db
from app.models import User
from app.schemas import UserProfileSync, UserRead

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_or_create_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def sync_me_profile(
    payload: UserProfileSync,
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> User:
    """Sync Auth0 profile fields into the local user record."""
    updated = False
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None and getattr(current_user, field) != value:
            setattr(current_user, field, value)
            updated = True

    if updated:
        db.commit()
        db.refresh(current_user)

    return current_user
