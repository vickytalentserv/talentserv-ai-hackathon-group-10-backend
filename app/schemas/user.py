from pydantic import BaseModel


class UserRead(BaseModel):
    id: int
    auth0_sub: str
    email: str | None
    name: str | None
    picture: str | None

    model_config = {"from_attributes": True}


class UserProfileSync(BaseModel):
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    openai_enabled: bool = False
