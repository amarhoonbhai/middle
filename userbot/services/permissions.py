from typing import Any, Callable
import os
import functools
import logging
from telethon import events
from userbot.config import config

logger = logging.getLogger(__name__)

async def is_owner(sender_id: int, db: Any) -> bool:
    """
    Checks if the sender_id matches the configured or registered owner of this userbot.
    Uses the SQLite database setting first, and falls back to the .env OWNER_ID.
    """
    if not sender_id:
        return False
    try:
        settings = await db.get_settings()
        db_owner_id = settings.get("owner_id")
        if db_owner_id is not None:
            return sender_id == int(db_owner_id)
    except Exception:
        # Fall back to env-level configuration in case of database issues
        pass
    
    return sender_id == config.OWNER_ID

def owner_command(db: Any) -> Callable:
    """
    Decorator for userbot commands.
    1. Verifies that the sender is the owner.
    2. Runs the command handler with error logging and friendly chat output.
    3. Deletes the outgoing command trigger on success if DELETE_COMMANDS is True.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(event: events.NewMessage.Event, *args: Any, **kwargs: Any) -> None:
            if not event.sender_id:
                return
            if not await is_owner(event.sender_id, db):
                return
            
            try:
                # Log execution start
                logger.info(f"Owner executed command: {event.text} in chat {event.chat_id}")
                
                # Execute the handler
                await func(event, *args, **kwargs)
                
                # Delete command if outgoing and configured
                delete_commands = os.getenv("DELETE_COMMANDS", "True").lower() in ("true", "1", "yes")
                if delete_commands and event.out:
                    try:
                        await event.delete()
                    except Exception as de:
                        logger.warning(f"Failed to delete command message: {de}")
            except Exception as e:
                # Log error details but do not leak secrets
                logger.error(f"Error executing command '{event.text}': {e}", exc_info=True)
                # Send user-friendly error message in chat
                await event.respond(f"❌ **Error**: {str(e)}")
        return wrapper
    return decorator

