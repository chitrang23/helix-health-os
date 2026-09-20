from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(tags=["Auth"])

class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class LoginInput(BaseModel):
    email: str
    password: str

users_db = {}

@router.post("/auth/register")
@router.post("/v1/auth/register")
async def register(data: RegisterInput):
    if data.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = len(users_db) + 1
    token = f"fake-jwt-token-{user_id}"
    user_info = {
        "user_id": user_id,
        "email": data.email,
        "full_name": data.full_name,
        "token": token
    }
    users_db[data.email] = user_info
    
    return {
        "status": "success",
        "user_id": user_id,
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/auth/login")
@router.post("/v1/auth/login")
async def login(data: LoginInput):
    user = users_db.get(data.email)
    if not user or data.password != "SecurePassword123!":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "access_token": user["token"],
        "token_type": "bearer",
        "user_id": user["user_id"]
    }
