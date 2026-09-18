from typing import Literal

from pydantic import BaseModel, Field

RoleValue = Literal["OFFICER"]


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    checkpoint_code: str | None = None
    is_active: bool
    created_at: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8)
    role: RoleValue
    checkpoint_id: str | None = None


class UserUpdateRequest(BaseModel):
    role: RoleValue | None = None
    checkpoint_id: str | None = None
    is_active: bool | None = None
    new_password: str | None = Field(None, min_length=8)


class OfficerResponse(BaseModel):
    id: str
    username: str
    role: str
    checkpoint_code: str | None = None
    is_active: bool
    case_count: int


class DeviceResponse(BaseModel):
    id: str
    device_identifier: str
    officer_username: str | None = None
    app_version: str | None = None
    is_disabled: bool
    revoked_at: str | None = None
    revoked_reason: str | None = None
    last_active_at: str | None = None
    registered_at: str


class DeviceRegisterRequest(BaseModel):
    device_identifier: str = Field(..., min_length=1)
    app_version: str | None = None


class DeviceUpdateRequest(BaseModel):
    is_disabled: bool


class DeviceRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=256)


class CheckpointResponse(BaseModel):
    id: str
    code: str
    name: str
    location: str | None = None
    is_active: bool
