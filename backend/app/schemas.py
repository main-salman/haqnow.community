from datetime import datetime
from pydantic import BaseModel, EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: str = "viewer"
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MfaVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class ApiKeyCreate(BaseModel):
    name: str
    scopes: str = "ingest,search,export,admin"


class ApiKeyOut(BaseModel):
    id: int
    name: str
    scopes: str
    created_by: int
    last_used_at: datetime | None = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyResponse(BaseModel):
    api_key: str
    key_info: ApiKeyOut


class DocumentCreate(BaseModel):
    title: str
    description: str | None = None
    source: str | None = None
    language: str = "en"
    published_date: datetime | None = None
    acquired_date: datetime | None = None
    event_date: datetime | None = None
    filing_date: datetime | None = None


class DocumentOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    source: str | None = None
    language: str
    status: str
    uploader_id: int
    published_date: datetime | None = None
    acquired_date: datetime | None = None
    event_date: datetime | None = None
    filing_date: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PresignedUploadRequest(BaseModel):
    filename: str
    content_type: str
    size: int


class PresignedUploadResponse(BaseModel):
    upload_id: str
    upload_url: str
    fields: dict


