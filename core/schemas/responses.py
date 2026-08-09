"""
Standard API and service response envelopes.
"""

from datetime import datetime, timezone
from typing import Generic, List, Optional, TypeVar
from pydantic import Field

from core.schemas.base import CoreBaseModel

T = TypeVar("T")


class ResponseMeta(CoreBaseModel):
    """Metadata envelope for service responses."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response UTC timestamp",
    )
    request_id: Optional[str] = Field(
        default=None, description="Unique trace/request ID for log correlation"
    )
    execution_time_ms: Optional[float] = Field(
        default=None, description="Processing duration in milliseconds"
    )


class APIResponse(CoreBaseModel, Generic[T]):
    """Standard generic envelope for successful service responses."""

    success: bool = Field(default=True, description="Execution success status")
    message: str = Field(default="Operation completed successfully", description="Status message")
    data: Optional[T] = Field(default=None, description="Payload data")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Metadata")


class PaginatedResponse(CoreBaseModel, Generic[T]):
    """Standard wrapper for paginated collections."""

    items: List[T] = Field(default_factory=list, description="Collection of items for current page")
    page: int = Field(default=1, ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    total_items: int = Field(default=0, ge=0, description="Total count of items across all pages")

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total_items + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1
