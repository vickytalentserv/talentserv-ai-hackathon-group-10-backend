from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None


def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


def _get_rsa_key(token: str) -> dict:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header",
        ) from exc

    jwks = _get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == unverified_header.get("kid"):
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find appropriate key",
    )


@dataclass
class Auth0User:
    sub: str
    email: str | None
    name: str | None
    picture: str | None


def _claim_from_payload(payload: dict, claim: str) -> str | None:
    """Read standard or namespaced custom claims from Auth0 access tokens."""
    audience = settings.auth0_api_audience.rstrip("/")
    candidates = (
        claim,
        f"{audience}/{claim}",
        f"{audience}/claims/{claim}",
    )
    for key in candidates:
        value = payload.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def verify_token(token: str) -> Auth0User:
    rsa_key = _get_rsa_key(token)
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=settings.auth0_algorithms_list,
            audience=settings.auth0_api_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    return Auth0User(
        sub=sub,
        email=_claim_from_payload(payload, "email"),
        name=_claim_from_payload(payload, "name") or _claim_from_payload(payload, "nickname"),
        picture=_claim_from_payload(payload, "picture"),
    )


def get_current_auth0_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Auth0User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
        )

    return verify_token(credentials.credentials)


def get_or_create_user(
    auth0_user: Auth0User = Depends(get_current_auth0_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.auth0_sub == auth0_user.sub).one_or_none()

    if user is None:
        user = User(
            auth0_sub=auth0_user.sub,
            email=auth0_user.email,
            name=auth0_user.name,
            picture=auth0_user.picture,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    updated = False
    for field, value in {
        "email": auth0_user.email,
        "name": auth0_user.name,
        "picture": auth0_user.picture,
    }.items():
        if value is not None and getattr(user, field) != value:
            setattr(user, field, value)
            updated = True

    if updated:
        db.commit()
        db.refresh(user)

    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    auth0_user = verify_token(credentials.credentials)
    user = db.query(User).filter(User.auth0_sub == auth0_user.sub).one_or_none()

    if user is None:
        user = User(
            auth0_sub=auth0_user.sub,
            email=auth0_user.email,
            name=auth0_user.name,
            picture=auth0_user.picture,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
