import os
import pytest
from typing import Generator
from unittest.mock import AsyncMock
from userbot.database import Database
from userbot.services.permissions import is_owner
from userbot.config import config

@pytest.fixture
def temp_db() -> Generator[Database, None, None]:
    db_file = "test_perm_userbot.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    db_instance = Database(db_file)
    yield db_instance
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except PermissionError:
            pass

@pytest.mark.asyncio
async def test_is_owner_db_override(temp_db: Database) -> None:
    # Seed db with owner_id = 99999
    await temp_db.seed_settings(99999)
    
    # Matching owner ID
    assert await is_owner(99999, temp_db) is True
    
    # Non-matching owner ID
    assert await is_owner(88888, temp_db) is False

@pytest.mark.asyncio
async def test_is_owner_env_fallback() -> None:
    # Create a mock database that returns empty settings and no admins
    mock_db = AsyncMock()
    mock_db.get_settings.return_value = {}  # No database owner_id configured
    mock_db.is_admin.return_value = False   # No secondary admins

    # Should fall back to config.OWNER_ID from the env
    env_owner = config.OWNER_ID

    assert await is_owner(env_owner, mock_db) is True
    assert await is_owner(env_owner + 1, mock_db) is False
