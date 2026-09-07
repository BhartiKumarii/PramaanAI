from pydantic import BaseModel


class RegistrySeedEntryIn(BaseModel):
    document_number: str
    full_name: str
    reason: str
    severity: str = "MEDIUM"


class RegistrySeedRequest(BaseModel):
    entries: list[RegistrySeedEntryIn] | None = None


class RegistrySeedResponse(BaseModel):
    seeded: int


class RegistryLookupRequest(BaseModel):
    document_number: str | None = None
    name: str | None = None
