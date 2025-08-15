from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .db import get_db, Base, engine
from .models import User, ApiKey
from .schemas import UserCreate, UserOut, LoginRequest, MfaVerifyRequest, TokenResponse, ApiKeyCreate, ApiKeyResponse, ApiKeyOut
from .security import hash_password, verify_password, generate_totp_secret, verify_totp, create_jwt, generate_api_key


router = APIRouter(prefix="/auth", tags=["auth"])


@router.on_event("startup")
def startup_migrate():
    Base.metadata.create_all(bind=engine)


@router.post("/admin/users", response_model=UserOut)
def admin_create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        totp_secret=generate_totp_secret(),
        mfa_enabled=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/admin/users", response_model=list[UserOut])
def admin_list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"mfa_required": user.mfa_enabled}


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.totp_secret:
        raise HTTPException(status_code=401, detail="MFA not enabled")
    if not verify_totp(payload.code, user.totp_secret):
        raise HTTPException(status_code=401, detail="Invalid code")
    token = create_jwt({"sub": str(user.id), "email": user.email, "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/admin/api-keys", response_model=ApiKeyResponse)
def admin_create_api_key(payload: ApiKeyCreate, db: Session = Depends(get_db)):
    # TODO: Add proper auth middleware to verify admin role
    raw_key, key_hash = generate_api_key()
    api_key = ApiKey(
        name=payload.name,
        key_hash=key_hash,
        scopes=payload.scopes,
        created_by=1,  # TODO: Get from authenticated user
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return ApiKeyResponse(api_key=raw_key, key_info=api_key)


@router.get("/admin/api-keys", response_model=list[ApiKeyOut])
def admin_list_api_keys(db: Session = Depends(get_db)):
    # TODO: Add proper auth middleware to verify admin role
    keys = db.query(ApiKey).filter(ApiKey.is_active == True).all()
    return keys


@router.delete("/admin/api-keys/{key_id}")
def admin_revoke_api_key(key_id: int, db: Session = Depends(get_db)):
    # TODO: Add proper auth middleware to verify admin role
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    db.commit()
    return {"message": "API key revoked"}


