import logging
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import BlockRequest
from telethon.tl.functions.messages import DeleteHistoryRequest
from userbot.services.permissions import owner_command, is_owner

logger = logging.getLogger(__name__)

def register_moderation_handlers(client: TelegramClient, db) -> None:
    @client.on(events.NewMessage(pattern=r'^[./]block$'))
    @owner_command(db)
    async def block_command(event: events.NewMessage.Event) -> None:
        if not event.is_reply:
            await event.respond("❌ **Usage**: Reply to a user's message with `.block` to block them and clear DMs.")
            return
            
        reply_msg = await event.get_reply_message()
        if not reply_msg:
            await event.respond("❌ **Error**: Could not fetch replied message.")
            return
            
        target_user_id = reply_msg.sender_id
        if not target_user_id:
            await event.respond("❌ **Error**: Could not resolve sender ID from the replied message.")
            return
            
        try:
            target_user = await client.get_entity(target_user_id)
        except Exception as e:
            await event.respond(f"❌ **Error**: Could not resolve target user entity: {e}")
            return
            
        # Security check: Prevent blocking the owner
        if await is_owner(target_user.id, db):
            await event.respond("❌ **Error**: Cannot block the owner account.")
            return
            
        username = getattr(target_user, "username", None)
        username_str = f"@{username}" if username else str(target_user.id)
        
        status_lines = []
        block_success = False
        
        # 1. Block user
        try:
            await client(BlockRequest(id=target_user.id))
            block_success = True
            status_lines.append(f"✅ Blocked {username_str} on Telegram.")
        except Exception as e:
            logger.error(f"Failed to block user {target_user.id}: {e}")
            status_lines.append(f"❌ Failed to block on Telegram: {e}")
            
        # 2. Add to blocked list in database
        if block_success:
            try:
                await db.add_blocked_user(target_user.id, username)
                status_lines.append("✅ Recorded in blocked_users database.")
            except Exception as e:
                logger.error(f"Failed to write block user {target_user.id} to SQLite: {e}")
                status_lines.append(f"❌ Database record failed: {e}")
                
        # 3. Clean up DM conversation if permissions allow
        try:
            # Delete private conversation history for both parties (revoke=True)
            await client(DeleteHistoryRequest(peer=target_user.id, max_id=0, revoke=True))
            status_lines.append("✅ Cleared private DM history for both sides.")
        except Exception as e:
            logger.warning(f"Could not clear chat history with {target_user.id}: {e}")
            status_lines.append(f"ℹ️ History cleanup skipped (or not a private DM chat): {e}")
            
        # Final status report
        report = "🚫 **Block Operations Executed**\n\n" + "\n".join(status_lines)
        await event.respond(report)
