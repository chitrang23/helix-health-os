from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone
import jwt

router = APIRouter(tags=["Authentication"])

SECRET_KEY = "helix_super_secret_enterprise_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Temporary in-memory user store for prototype demonstration
# In production, this maps to SQLAlchemy PostgreSQL User table
users_db = {
    "chitrang@helix.os": {
        "user_id": 1,
        "full_name": "Chitrang Laxman Sawant",
        "email": "chitrang@helix.os",
        "hashed_password": pwd_context.hash("password123"),
        "age": 21,
        "gender": "Male",
        "birthday": "2005-01-01"
    }
}

class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str
    age: int
    gender: str
    birthday: str

class PasswordReset(BaseModel):
    email: str
    new_password: str

@router.post("/register")
async def register(user: UserRegister):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    hashed_pw = pwd_context.hash(user.password)
    users_db[user.email] = {
        "user_id": len(users_db) + 1,
        "full_name": user.full_name,
        "email": user.email,
        "hashed_password": hashed_pw,
        "age": user.age,
        "gender": user.gender,
        "birthday": user.birthday
    }
    return {"success": True, "message": "User registered successfully."}

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + access_token_expires
    to_encode = {"sub": user["email"], "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "age": user["age"],
            "gender": user["gender"],
            "birthday": user["birthday"]
        }
    }

@router.post("/api/auth/reset-password")
async def reset_password(req: PasswordReset):
    user = users_db.get(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="Email address not found in system.")
    
    user["hashed_password"] = pwd_context.hash(req.new_password)
    return {"success": True, "message": "Password successfully reset."}
