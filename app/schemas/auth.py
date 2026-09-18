from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    role: str
    # Server-authoritative — set by IT/Admin (see /admin/users), never
    # client-selected. None for an account with no checkpoint assigned
    # yet (e.g. a fresh IT_ADMIN account, which isn't checkpoint-scoped).
    checkpoint_id: str | None = None
    checkpoint_code: str | None = None
    checkpoint_name: str | None = None
