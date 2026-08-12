import os
import pytest
from typing import Generator
from userbot.database import Database

import uuid

@pytest.fixture
def db() -> Generator[Database, None, None]:
    """Fixture to provide a clean temporary database instance and clean up after."""
    db_file = f"test_{uuid.uuid4().hex}.db"
    db_instance = Database(db_file)
    yield db_instance
    
    # Cleanup file after test
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

@pytest.mark.asyncio
async def test_database_initialization_and_seeding(db: Database) -> None:
    # Seed default owner settings
    owner_id = 987654321
    await db.seed_settings(owner_id)
    
    settings = await db.get_settings()
    assert settings["owner_id"] == owner_id
    assert settings["fee_percentage"] == "3.0"
    assert settings["group_naming_template"] == "MM • Deal #{deal_id}"
    assert settings["btc_address"] is None

@pytest.mark.asyncio
async def test_settings_read_write(db: Database) -> None:
    owner_id = 111222333
    await db.seed_settings(owner_id)
    
    # Update settings
    await db.update_settings(
        btc_address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        fee_percentage="2.5",
        tos_text="Custom terms of service text."
    )
    
    settings = await db.get_settings()
    assert settings["btc_address"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert settings["fee_percentage"] == "2.5"
    assert settings["tos_text"] == "Custom terms of service text."

@pytest.mark.asyncio
async def test_deal_creation_and_incremental_id(db: Database) -> None:
    # Create two deals and verify sequential deal ID generation (1 and 2)
    deal1_id = await db.create_deal(1001, ["@buyer", "@seller"])
    deal2_id = await db.create_deal(1002, ["@buyer2", "@seller2"])
    
    assert deal1_id == 1
    assert deal2_id == 2
    
    deal1 = await db.get_deal(1001)
    assert deal1 is not None
    assert deal1["deal_id"] == 1
    assert deal1["status"] == "active"
    assert deal1["funds_received"] == 0
    
    deal2 = await db.get_deal_by_id(2)
    assert deal2 is not None
    assert deal2["chat_id"] == 1002

@pytest.mark.asyncio
async def test_deal_status_transitions(db: Database) -> None:
    deal_id = await db.create_deal(5001, ["@party1", "@party2"])
    
    # 1. Update deal details
    await db.update_deal(deal_id, amount="500.00", fee="15.00")
    deal = await db.get_deal(5001)
    assert deal["amount"] == "500.00"
    assert deal["fee"] == "15.00"
    
    # 2. Mark funds received
    await db.update_deal(deal_id, funds_received=1)
    deal = await db.get_deal(5001)
    assert deal["funds_received"] == 1
    
    # 3. Close deal
    await db.close_deal(deal_id)
    deal = await db.get_deal_by_id(deal_id)
    assert deal["status"] == "closed"
    assert deal["closed_at"] is not None
