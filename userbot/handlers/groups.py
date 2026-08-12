import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict
from telethon import TelegramClient, events
from userbot.services.permissions import owner_command
from userbot.services import group_service

logger = logging.getLogger(__name__)

# Memory store for pending close confirmations: chat_id -> timestamp
pending_closes: Dict[int, datetime] = {}

def register_group_handlers(client: TelegramClient, db) -> None:
    @client.on(events.NewMessage(pattern=r'^\.mm(?:\s+(.+))?$'))
    @owner_command(db)
    async def mm_command(event: events.NewMessage.Event) -> None:
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.mm <user1> <user2>`\n(e.g., `.mm @buyer @seller` or `.mm 123456789 987654321`)")
            return
            
        parts = args.split()
        if len(parts) != 2:
            await event.respond("❌ **Usage**: `.mm <user1> <user2>` (Must provide exactly two participants)")
            return
            
        # 1. Insert a placeholder in the database to acquire the sequential deal_id
        placeholder_chat_id = None
        try:
            # We insert with a temporary negative chat ID to bypass UNIQUE constraints during setup, 
            # or NULL if unique constraints are not triggered.
            # In SQLite, NULL doesn't trigger UNIQUE constraints, but to be safe and clean, 
            # we create the deal record, retrieve the deal_id, and then update it once the group is created.
            deal_id = await db.create_deal(0, parts)  # Temporary chat_id = 0
        except Exception as e:
            logger.error(f"Failed to initialize deal in database: {e}")
            await event.respond(f"❌ **Database Error**: Could not initialize deal: {e}")
            return
            
        formatted_deal_id = f"{deal_id:04d}"
        
        # 2. Get settings for group title template and TOS
        settings = await db.get_settings()
        naming_template = settings.get("group_naming_template", "MM • Deal #{deal_id}")
        title = naming_template.replace("{deal_id}", formatted_deal_id)
        
        status_msg = await event.respond(f"⏳ Creating group **{title}**...")
        
        # 3. Create the group
        try:
            chat_entity, added, failed = await group_service.create_mm_group(client, title, parts)
        except Exception as e:
            # Clean up the placeholder if group creation completely failed
            # We'll use database queries to delete the placeholder so we don't pollute deal IDs
            def _delete_deal(d_id: int):
                with db.lock:
                    conn = db._get_conn()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM deal_events WHERE deal_id = ?", (d_id,))
                    cursor.execute("DELETE FROM deals WHERE deal_id = ?", (d_id,))
                    conn.commit()
                    conn.close()
            await asyncio.to_thread(_delete_deal, deal_id)
            
            logger.error(f"Group creation failed: {e}")
            await status_msg.edit(f"❌ **Failed to create group**: {str(e)}")
            return
            
        # 4. Success! Update the deal with the real chat ID and participants list
        # Chat IDs returned by Telethon can be signed. Let's get the signed peer ID
        from telethon import utils
        signed_chat_id = utils.get_peer_id(chat_entity)
        
        await db.update_deal(deal_id, chat_id=signed_chat_id, participants=str(added))
        
        # Export group invite link
        invite_link = await group_service.get_invite_link(client, chat_entity)
        
        # Attempt to send private message (DM) with invite link to failed participants
        failed_notified = []
        failed_unnotified = []
        
        if failed and invite_link:
            for p_id in failed:
                try:
                    await client.send_message(
                        p_id,
                        f"🤝 **Hello! You have been invited to join Deal #{formatted_deal_id}** ({title}).\n\n"
                        f"Since your privacy settings prevented adding you automatically, "
                        f"please click the link below to join the group:\n{invite_link}"
                    )
                    failed_notified.append(p_id)
                except Exception as dme:
                    logger.warning(f"Could not send DM invite link to {p_id}: {dme}")
                    failed_unnotified.append(p_id)
        else:
            failed_unnotified = list(failed)
            
        welcome_text = (
            f"🤝 **Deal #{formatted_deal_id} created.**\n\n"
            "Please read the Terms of Service before proceeding.\n"
            "Both parties should confirm the agreed amount and transaction terms before payment.\n\n"
            f"• **Buyer/Seller Added**: {', '.join(added) if added else 'None'}\n"
        )
        if failed_notified:
            welcome_text += f"✉️ **Invite Link Sent via DM to**: {', '.join(failed_notified)} (due to group invite privacy settings)\n"
        if failed_unnotified:
            welcome_text += f"⚠️ **Failed to add/DM**: {', '.join(failed_unnotified)}\n"
            if invite_link:
                welcome_text += f"🔗 **Manual Invite Link**: {invite_link}\n"
            
        await client.send_message(signed_chat_id, welcome_text)
        
        # Send and pin TOS if configured
        tos_text = settings.get("tos_text")
        if tos_text:
            tos_msg = await client.send_message(
                signed_chat_id, 
                f"📜 **Terms of Service for Deal #{formatted_deal_id}**\n\n{tos_text}"
            )
            try:
                await client.pin_message(signed_chat_id, tos_msg.id, notify=True)
            except Exception as pe:
                logger.warning(f"Could not pin TOS message in group {signed_chat_id}: {pe}")
                
        await status_msg.edit(f"✅ **Deal #{formatted_deal_id} group created successfully!**\nGroup Title: {title}")

    @client.on(events.NewMessage(pattern=r'^\.name(?:\s+(.+))?$'))
    @owner_command(db)
    async def name_command(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        deal = await db.get_deal(chat_id)
        if not deal:
            await event.respond("❌ **Error**: This command must be executed inside a registered MM group.")
            return
            
        if deal.get("status") == "closed":
            await event.respond("⚠️ **Notice**: This deal is already closed.")
            return
            
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.name <new_name>`")
            return
            
        new_title = args.strip()
        
        # Update group title via Telegram API
        await group_service.rename_group(client, chat_id, new_title)
        
        # Log event in DB
        await db.log_deal_event(deal["deal_id"], "renamed", f"Group renamed to: {new_title}")
        
        await event.respond(f"✅ **Group renamed to**: {new_title}")

    @client.on(events.NewMessage(pattern=r'^\.close(?:\s+(.+))?$'))
    @owner_command(db)
    async def close_command(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        deal = await db.get_deal(chat_id)
        if not deal:
            await event.respond("❌ **Error**: This command must be executed inside a registered MM group.")
            return
            
        deal_id = deal["deal_id"]
        formatted_deal_id = f"{deal_id:04d}"
        
        if deal.get("status") == "closed":
            await event.respond("⚠️ **Notice**: This deal is already closed.")
            return
            
        args = event.pattern_match.group(1)
        
        # 1. Initiating closure
        if not args:
            pending_closes[chat_id] = datetime.now(timezone.utc)
            await event.respond(
                f"⚠️ **Close Deal #{formatted_deal_id}?**\n\n"
                "Run `.close confirm` within 60 seconds to execute closure."
            )
            return
            
        # 2. Confirming closure
        if args.strip().lower() == "confirm":
            init_time = pending_closes.get(chat_id)
            if not init_time or (datetime.now(timezone.utc) - init_time).total_seconds() > 60:
                await event.respond("❌ **Error**: Confirmation window expired or not initiated. Run `.close` first.")
                return
                
            # Clear confirmation window
            pending_closes.pop(chat_id, None)
            
            # Close deal in DB
            await db.close_deal(deal_id)
            
            await event.respond(f"🏁 **Deal #{formatted_deal_id} is now closed.**")
            
            # Optionally leave the group
            try:
                await event.respond("⏳ Leaving group...")
                await group_service.leave_group(client, chat_id)
            except Exception as e:
                logger.error(f"Failed to leave group {chat_id} after closure: {e}")
                await event.respond(f"⚠️ Could not leave the group automatically: {e}")
