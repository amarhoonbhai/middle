import os
import sys
import logging
from telethon import TelegramClient

# Add parent directory to system path to enable robust module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from userbot.config import config
from userbot.database import Database
from userbot.handlers import register_all_handlers

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/userbot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("userbot.main")

async def main() -> None:
    logger.info("Initializing SQLite database...")
    db = Database("userbot.db")
    await db.seed_settings(config.OWNER_ID)
    
    logger.info("Initializing Telegram client...")
    # Initialize the client. Telethon stores the session in <SESSION_NAME>.session
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    
    # Register handlers
    register_all_handlers(client, db)
    
    logger.info("Starting Telegram Client login flow...")
    # client.start() automatically prompts for phone, code, and 2FA password in the console
    await client.start()
    
    logger.info("Userbot successfully authorized and running! Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Userbot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Unhandled userbot crash: {e}", exc_info=True)
