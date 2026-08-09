"""
Standard error response and detail schemas.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from core.schemas.base import CoreBaseModel
from core.schemas.responses import ResponseMeta


class ErrorDetail(CoreBaseModel):
    """Detailed error object representation."""

    code: str = Field(description="Machine-readable domain error code (e.g. VALIDATION_ERROR)")
    message: str = Field(description="Human-readable error description")
    field: Optional[str] = Field(default=None, description="Target field name if validation error")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional contextual error attributes"
    )


class ErrorResponse(CoreBaseModel):
    """Standardized error envelope for failed operations."""

    success: bool = Field(default=False, description="Always False for error responses")
    error: ErrorDetail = Field(description="Primary error detail object")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Metadata")
