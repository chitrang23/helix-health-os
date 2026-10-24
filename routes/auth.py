from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import verify_password, get_password_hash, create_access_token
from models.orm import User

router = APIRouter(tags=["Authentication"])


# --- SCHEMAS ---
class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    username: Optional[str] = None
    dob: Optional[str] = None
    birthday: Optional[str] = None  # Frontend compatibility alias
    age: Optional[int] = None
    gender: Optional[str] = None
    role: Optional[str] = "patient"


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class PasswordResetPayload(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=6)


# --- CORE AUTHENTICATION ENDPOINTS ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterPayload, db: Session = Depends(get_db)):
    """
    Registers a new user directly into the database.
    Enforces normalized emails, safe password hashing, and active status.
    """
    clean_email = payload.email.strip().lower()
    clean_username = (payload.username or clean_email.split("@")[0]).strip()
    birth_date = payload.dob or payload.birthday

    # Prevent duplicate registrations
    existing_user = db.query(User).filter(
        (User.email == clean_email) | (User.username == clean_username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or username already exists."
        )

    # Hash password safely
    hashed_pwd = get_password_hash(payload.password)

    new_user = User(
        username=clean_username,
        email=clean_email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name or clean_username.title(),
        dob=birth_date,
        gender=payload.gender or "unknown",
        role=payload.role or "patient",
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(data={"sub": new_user.email, "role": new_user.role})
    return {
        "status": "success",
        "message": "User registered successfully.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "username": new_user.username,
            "full_name": new_user.full_name,
            "role": new_user.role
        }
    }


@router.post("/login")
def login_json(payload: LoginPayload, db: Session = Depends(get_db)):
    """
    Standard JSON login endpoint for web frontend compatibility.
    """
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 standard password token flow endpoint.
    Accepts either normalized email or username in the form username field.
    """
    identifier = form_data.username.strip().lower()
    user = db.query(User).filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@router.post("/reset-password")
def reset_password(payload: PasswordResetPayload, db: Session = Depends(get_db)):
    """
    Updates the hashed password for a verified registered email in the database.
    """
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email address not found in system."
        )

    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    return {"status": "success", "message": "Password successfully reset."}