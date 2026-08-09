"""
Environment loading and validation utilities.
"""

import os
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

from core.logging import get_logger

logger = get_logger(__name__)


def load_environment(env_file: Optional[str] = ".env") -> bool:
    """
    Explicitly loads environment variables from a .env file if available.

    Args:
        env_file: Path to the .env file (default: '.env')

    Returns:
        bool: True if loaded successfully or not required, False if error occurred.
    """
    if not HAS_DOTENV:
        logger.warning(
            "python-dotenv is not installed. Relying strictly on system environment variables."
        )
        return False

    target_path = Path(env_file)
    if target_path.exists():
        load_dotenv(dotenv_path=target_path, override=True)
        logger.info(f"Loaded environment variables from '{target_path.resolve()}'")
        return True
    else:
        logger.debug(f"Environment file '{env_file}' not found. Using current shell variables.")
        return False


def validate_environment(required_vars: List[str]) -> List[str]:
    """
    Validates that essential environment variables are set.

    Args:
        required_vars: List of variable names required for operation.

    Returns:
        List[str]: List of missing variable names (empty if all present).
    """
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
    else:
        logger.info("Environment validation succeeded. All required variables are present.")
    return missing
