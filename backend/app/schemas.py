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


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    registration_status: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserApproval(BaseModel):
    user_id: int
    action: str  # "approve" or "reject"


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


class DocumentShareCreate(BaseModel):
    shared_with_email: str | None = None  # None for "everyone"
    permission_level: str  # "view" or "edit"
    is_everyone: bool = False
    expires_at: datetime | None = None
    group_id: int | None = None


class DocumentShareOut(BaseModel):
    id: int
    document_id: int
    shared_by_user_id: int
    shared_with_email: str | None = None
    permission_level: str
    is_everyone: bool
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    group_id: int | None = None

    class Config:
        from_attributes = True


class DocumentShareUpdate(BaseModel):
    permission_level: str | None = None
    expires_at: datetime | None = None


class GroupCreate(BaseModel):
    name: str


class GroupMemberAdd(BaseModel):
    email: str


class GroupOut(BaseModel):
    id: int
    name: str
    owner_user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
