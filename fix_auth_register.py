import os

print("🔧 Updating auth route to return access_token on registration...")

os.makedirs("routes", exist_ok=True)

auth_code = '''from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from core.security import hash_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

class UserRegister(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(user_data: UserRegister):
    # Generate token immediately upon registration
    token = create_access_token({"sub": user_data.email, "role": "user"})
    return {
        "message": "User registered successfully",
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/login")
async def login(credentials: UserLogin):
    token = create_access_token({"sub": credentials.email, "role": "user"})
    return {
        "access_token": token,
        "token_type": "bearer"
    }
'''

with open("routes/auth.py", "w", encoding="utf-8") as f:
    f.write(auth_code)

print("  ✅ routes/auth.py updated with access_token response.")
