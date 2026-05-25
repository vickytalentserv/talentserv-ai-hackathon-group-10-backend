from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_or_create_user
from app.database import get_db
from app.models import Favorite, Inquiry, Property, User
from app.schemas.favorite import FavoriteCreate, FavoriteListResponse, FavoriteRead
from app.schemas.property import PropertyRead

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


def _to_favorite_read(favorite: Favorite) -> FavoriteRead:
    property_data = None
    if favorite.property is not None:
        property_data = PropertyRead.model_validate(favorite.property)

    return FavoriteRead(
        id=favorite.id,
        listing_key=favorite.listing_key,
        property_id=favorite.property_id,
        property=property_data,
        created_at=favorite.created_at,
    )


@router.get("", response_model=FavoriteListResponse)
def list_favorites(
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> FavoriteListResponse:
    favorites = db.scalars(
        select(Favorite)
        .options(joinedload(Favorite.property))
        .where(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
    ).all()

    items = [_to_favorite_read(favorite) for favorite in favorites]
    return FavoriteListResponse(items=items, total=len(items))


@router.post("", response_model=FavoriteRead, status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreate,
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> FavoriteRead:
    existing = db.scalar(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.listing_key == payload.listing_key,
        )
    )
    if existing is not None:
        if existing.property_id and existing.property is None:
            existing.property = db.get(Property, existing.property_id)
        return _to_favorite_read(existing)

    property_id = payload.property_id
    if property_id is not None and db.get(Property, property_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    favorite = Favorite(
        user_id=current_user.id,
        listing_key=payload.listing_key,
        property_id=property_id,
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)

    if favorite.property_id:
        favorite.property = db.get(Property, favorite.property_id)

    return _to_favorite_read(favorite)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    listing_key: str = Query(min_length=3, max_length=80),
    current_user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> None:
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.listing_key == listing_key,
        )
    )
    if favorite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    db.delete(favorite)
    db.commit()
