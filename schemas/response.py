from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timezone

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    message: str = "Operation completed successfully"
    error: Optional[Any] = None
    timestamp: str = datetime.now(timezone.utc).isoformat()

    @classmethod
    def ok(cls, data: T = None, message: str = "Success"):
        return cls(success=True, data=data, message=message, error=None)

    @classmethod
    def fail(cls, message: str, error: Any = None):
        return cls(success=False, data=None, message=message, error=error)
