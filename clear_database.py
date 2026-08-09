"""
Utility script to wipe and reset the entire FinnAI PostgreSQL/SQLite database.

Usage:
    python clear_database.py
"""

from app.db.database import clear_db
from app.utils.logger import get_logger

logger = get_logger("finnai.clear_db", "INFO")

if __name__ == "__main__":
    logger.info("Dropping all existing database tables and recreating fresh schema...")
    clear_db()
    logger.info("Database successfully cleared and reset!")
    print("Database cleared and reset to fresh empty schema.")
