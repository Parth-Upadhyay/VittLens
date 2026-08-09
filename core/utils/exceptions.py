"""
Domain exception hierarchy for FinnAI platform services.
"""

from typing import Any, Dict, Optional


class FinnAIException(Exception):
    """
    Base domain exception for all FinnAI platform errors.

    Attributes:
        message: Human-readable error description
        code: System error code identifier
        details: Supplementary context attributes
        status_code: Suggested HTTP/service status code mapping
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(FinnAIException):
    """Raised when environment variables or application configuration is invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            details=details,
            status_code=500,
        )


class ValidationError(FinnAIException):
    """Raised when input parameters or entity validation checks fail."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        ctx = details or {}
        if field:
            ctx["field"] = field
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=ctx,
            status_code=400,
        )


class ExternalServiceError(FinnAIException):
    """Raised when an external API or service dependency fails."""

    def __init__(
        self,
        message: str,
        service_name: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        ctx = details or {}
        ctx["service_name"] = service_name
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            details=ctx,
            status_code=502,
        )


class RateLimitError(FinnAIException):
    """Raised when service or API rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        retry_after: Optional[int] = None,
    ):
        details = {"retry_after_seconds": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details=details,
            status_code=429,
        )


class ResourceNotFoundError(FinnAIException):
    """Raised when a requested domain resource or record is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} with ID '{resource_id}' was not found.",
            code="RESOURCE_NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id},
            status_code=404,
        )


class DataParsingError(FinnAIException):
    """Raised when financial document or data extraction parsing fails."""

    def __init__(self, message: str, source: Optional[str] = None):
        super().__init__(
            message=message,
            code="DATA_PARSING_ERROR",
            details={"source": source} if source else {},
            status_code=422,
        )
