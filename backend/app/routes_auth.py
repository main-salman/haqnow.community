from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import ApiKey, User
from .schemas import (
    ApiKeyCreate,
    ApiKeyOut,
    ApiKeyResponse,
    LoginRequest,
    MfaVerifyRequest,
    TokenResponse,
    UserApproval,
    UserCreate,
    UserOut,
    UserRegister,
)
from .security import (
    create_jwt,
    generate_api_key,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.on_event("startup")
def startup_migrate():
    Base.metadata.create_all(bind=engine)


@router.post("/register", response_model=UserOut)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """Register a new user (requires admin approval)"""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role="viewer",  # Default role for registered users
        password_hash=hash_password(payload.password),
        totp_secret=None,
        mfa_enabled=False,
        is_active=True,
        registration_status="pending"  # Requires admin approval
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
        totp_secret=None,  # MFA not set up initially
        mfa_enabled=False,  # MFA disabled by default
        is_active=True,
        registration_status="approved"  # Admin-created users are auto-approved
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/admin/users", response_model=list[UserOut])
def admin_list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


@router.get("/admin/users/pending", response_model=list[UserOut])
def admin_list_pending_users(db: Session = Depends(get_db)):
    """Get all users pending approval"""
    users = db.query(User).filter(User.registration_status == "pending").all()
    return users


@router.post("/admin/users/approve")
def admin_approve_user(payload: UserApproval, db: Session = Depends(get_db)):
    """Approve or reject a user registration"""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.action == "approve":
        user.registration_status = "approved"
        user.is_active = True
    elif payload.action == "reject":
        user.registration_status = "rejected"
        user.is_active = False
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'")
    
    db.commit()
    db.refresh(user)
    return {"message": f"User {payload.action}d successfully", "user": user}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if user registration is approved
    if hasattr(user, 'registration_status') and user.registration_status == "pending":
        raise HTTPException(status_code=403, detail="Account pending approval")
    if hasattr(user, 'registration_status') and user.registration_status == "rejected":
        raise HTTPException(status_code=403, detail="Account access denied")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # If MFA is not enabled, return token directly
    if not user.mfa_enabled:
        token = create_jwt(
            {"sub": str(user.id), "email": user.email, "role": user.role}
        )
        return {"access_token": token, "mfa_required": False}

    # If MFA is enabled, require MFA verification
    return {"mfa_required": True}


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.totp_secret:
        raise HTTPException(status_code=401, detail="MFA not enabled")
    if not verify_totp(payload.code, user.totp_secret):
        raise HTTPException(status_code=401, detail="Invalid code")
    token = create_jwt({"sub": str(user.id), "email": user.email, "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/mfa/setup")
def mfa_setup(db: Session = Depends(get_db)):
    """
    Generate TOTP secret for MFA setup.
    TODO: Add authentication middleware to get current user
    """
    # For now, assume user ID 1 - this should be replaced with proper auth
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate new TOTP secret
    totp_secret = generate_totp_secret()
    user.totp_secret = totp_secret
    db.commit()

    # Return secret and QR code data
    import base64
    import io

    import qrcode

    # Generate QR code for TOTP setup
    totp_uri = f"otpauth://totp/Haqnow:{user.email}?secret={totp_secret}&issuer=Haqnow"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code_data = base64.b64encode(buffer.getvalue()).decode()

    return {
        "secret": totp_secret,
        "qr_code": f"data:image/png;base64,{qr_code_data}",
        "manual_entry_key": totp_secret,
    }


@router.post("/mfa/enable")
def mfa_enable(payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    """
    Enable MFA after verifying the setup code.
    TODO: Add authentication middleware to get current user
    """
    # For now, assume user ID 1 - this should be replaced with proper auth
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="MFA setup not initiated")

    # Verify the code
    if not verify_totp(payload.code, user.totp_secret):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Enable MFA
    user.mfa_enabled = True
    db.commit()

    return {"message": "MFA enabled successfully"}


@router.post("/mfa/disable")
def mfa_disable(payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    """
    Disable MFA after verifying current code.
    TODO: Add authentication middleware to get current user
    """
    # For now, assume user ID 1 - this should be replaced with proper auth
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is not enabled")

    # Verify the code
    if not verify_totp(payload.code, user.totp_secret):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Disable MFA
    user.mfa_enabled = False
    user.totp_secret = None
    db.commit()

    return {"message": "MFA disabled successfully"}


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
