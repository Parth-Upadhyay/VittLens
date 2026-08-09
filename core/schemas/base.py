"""
Base Pydantic schema model with strict validation and standard serialization config.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class CoreBaseModel(BaseModel):
    """
    Standard base model for all FinnAI platform schemas.

    Ensures:
    - Trimmed strings by default
    - Proper UTC datetime handling
    - Immutability / freeze options via subclassing
    - Compatible with OpenAPI / JSON schema generation
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda dt: dt.astimezone(timezone.utc).isoformat()
            if dt.tzinfo
            else dt.replace(tzinfo=timezone.utc).isoformat()
        },
    )

    def to_dict(self) -> Dict[str, Any]:
        """Utility export to dict using field names."""
        return self.model_dump(by_alias=False, exclude_none=False)
