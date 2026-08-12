from telethon import TelegramClient
from userbot.database import Database
from userbot.handlers.help import register_help_handlers
from userbot.handlers.settings import register_settings_handlers
from userbot.handlers.fees import register_fee_handlers
from userbot.handlers.crypto import register_crypto_handlers
from userbot.handlers.deals import register_deal_handlers
from userbot.handlers.groups import register_group_handlers
from userbot.handlers.moderation import register_moderation_handlers

def register_all_handlers(client: TelegramClient, db: Database) -> None:
    """Registers all command handlers onto the given Telethon client."""
    register_help_handlers(client, db)
    register_settings_handlers(client, db)
    register_fee_handlers(client, db)
    register_crypto_handlers(client, db)
    register_deal_handlers(client, db)
    register_group_handlers(client, db)
    register_moderation_handlers(client, db)
