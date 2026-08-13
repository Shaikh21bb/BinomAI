from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

class CursorPaginationParams(BaseModel):
    page_size: int = 20
    cursor: Optional[str] = None

class CursorPaginationMeta(BaseModel):
    page_size: int
    has_next: bool
    next_cursor: Optional[str]
    total: Optional[int] = None

class CursorPaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    pagination: CursorPaginationMeta
