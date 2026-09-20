import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = "helix_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    """Hashes a raw password string."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a raw password against its hash."""
    return hash_password(plain_password) == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a mock JWT access token for testing/dev."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire.timestamp()})
    return f"mock_token_{to_encode.get('sub', 'user')}"

class UserMock:
    def __init__(self, user_id: int = 1, username: str = "admin", role: str = "admin", is_active: bool = True):
        self.id = user_id
        self.username = username
        self.role = role
        self.is_active = is_active

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> UserMock:
    """Decodes token and returns current authenticated user context."""
    if token == "invalid":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authentication credentials"
        )
    return UserMock(user_id=1, username="admin", role="admin", is_active=True)

async def get_current_user_id(current_user: UserMock = Depends(get_current_user)) -> int:
    """Returns the ID of the current authenticated user."""
    return current_user.id

async def require_admin(current_user: UserMock = Depends(get_current_user)) -> UserMock:
    """Dependency enforcing admin role permissions."""
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required."
        )
    return current_user
