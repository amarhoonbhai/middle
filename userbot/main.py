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

# Configure logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/userbot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("userbot.main")

def get_telegram_client(session_name: str) -> TelegramClient:
    """Initializes TelegramClient with SOCKS5 Proxy if configured in the environment."""
    if config.PROXY_IP and config.PROXY_PORT:
        import socks
        proxy = (socks.SOCKS5, config.PROXY_IP, config.PROXY_PORT, True, config.PROXY_USER, config.PROXY_PASS)
        logger.info(f"Initializing TelegramClient with SOCKS5 Proxy ({config.PROXY_IP}:{config.PROXY_PORT})...")
        return TelegramClient(session_name, config.API_ID, config.API_HASH, proxy=proxy)
    else:
        return TelegramClient(session_name, config.API_ID, config.API_HASH)

async def start_bot() -> None:
    """Initializes and runs the Telegram Bot Daemon directly, bypassing CLI prompts."""
    logger.info("Initializing SQLite database...")
    db = Database("userbot.db")
    await db.seed_settings(config.OWNER_ID)
    
    logger.info("Initializing Telegram client (Session: bot_session)...")
    client = get_telegram_client("bot_session")
    register_all_handlers(client, db)
    
    logger.info("Starting Telegram Bot daemon flow...")
    await client.start(bot_token=config.BOT_TOKEN)
    
    # Initialize owner userbot client if a saved session exists
    client.user_client = None
    if os.path.exists("owner_session.session"):
        logger.info("Saved owner userbot session detected. Initializing userbot client...")
        try:
            user_client = get_telegram_client("owner_session")
            await user_client.connect()
            if await user_client.is_user_authorized():
                logger.info("Userbot client is authorized! Starting userbot client daemon...")
                await user_client.start()
                client.user_client = user_client
            else:
                logger.info("Userbot client session found but not authorized. Disconnecting userbot client.")
                await user_client.disconnect()
        except Exception as uce:
            logger.error(f"Failed to auto-start owner userbot: {uce}")
            
    # Pre-populate bot entity cache by fetching dialogs
    logger.info("Caching bot dialogs...")
    try:
        await client.get_dialogs()
    except Exception as gde:
        logger.warning(f"Could not fetch bot dialogs on startup: {gde}")
    
    # Register Bot commands in Telegram Menu
    try:
        from telethon.tl.functions.bots import SetBotCommandsRequest
        from telethon.tl.types import BotCommand, BotCommandScopeDefault
        await client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code="",
            commands=[
                BotCommand(command="start", description="Welcome message & Quick Menu"),
                BotCommand(command="help", description="Show all bot commands"),
                BotCommand(command="settings", description="View bot configurations"),
                BotCommand(command="setowner", description="Change or add bot owner ID"),
                BotCommand(command="userbot", description="Check owner userbot status"),
                BotCommand(command="addaccount", description="Connect owner userbot account"),
                BotCommand(command="setgroup", description="Manually register current group as daily room"),
                BotCommand(command="btc", description="Show BTC wallet address"),
                BotCommand(command="eth", description="Show ETH wallet address"),
                BotCommand(command="ltc", description="Show LTC wallet address"),
                BotCommand(command="tos", description="Show Terms of Service")
            ]
        ))
        logger.info("Successfully registered Telegram Bot menu commands.")
    except Exception as bce:
        logger.warning(f"Could not register Bot menu commands: {bce}")
        
    me = await client.get_me()
    client.me_id = me.id  # Cache bot ID directly on the client
    await db.update_settings(owner_id=config.OWNER_ID)
    
    logger.info(f"✅ Bot successfully authorized! Logged in as: {me.first_name} (@{me.username})")
    logger.info("Running daemon... Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Unhandled bot crash: {e}", exc_info=True)
