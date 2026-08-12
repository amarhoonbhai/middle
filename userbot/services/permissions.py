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
    1. Verifies that the sender matches the running logged-in account ID.
    2. Runs the command handler with error logging and friendly chat output.
    3. Deletes the outgoing command trigger on success if DELETE_COMMANDS is True.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(event: events.NewMessage.Event, *args: Any, **kwargs: Any) -> None:
            if not event.sender_id:
                return
            
            # Fetch and cache the currently logged-in account's user ID on the client
            client = event.client
            me_id = getattr(client, "me_id", None)
            if me_id is None:
                try:
                    me = await client.get_me()
                    if me:
                        client.me_id = me.id
                        me_id = me.id
                except Exception as e:
                    logger.error(f"Failed to fetch logged-in user entity: {e}")
            
            # Perform validation: accept command if sender is the bot account itself OR the configured owner_id
            is_valid_owner = False
            if me_id is not None and event.sender_id == me_id:
                is_valid_owner = True
            else:
                # Fallback to DB configuration check
                if await is_owner(event.sender_id, db):
                    is_valid_owner = True
            
            if not is_valid_owner:
                return
            
            try:
                # Log execution start
                logger.info(f"Owner ({event.sender_id}) executed command: {event.text} in chat {event.chat_id}")
                
                # Execute the handler
                await func(event, *args, **kwargs)
                
                # Delete command if outgoing (sent by self) and configured
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

