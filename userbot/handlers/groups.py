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
        from userbot.config import config
        
        # 1. Hybrid check: If no arguments and executed in a group, register the current group
        if not args:
            if not event.is_group:
                await event.respond(
        from telethon.tl import types
        from telethon.errors import UserPrivacyRestrictedError, RPCError
        
        chat_id = event.chat_id
        is_group = event.is_group
        
        settings = await db.get_settings()
        
        # 1. Existing Group Activation Pathway
        if is_group:
            # Check if there is already an active deal in this group
            existing_deal = await db.get_deal(chat_id)
            if existing_deal:
                formatted_deal_id = f"{existing_deal['deal_id']:04d}"
                await event.respond(f"⚠️ **Notice**: This group is already registered for active **Deal #{formatted_deal_id}**.")
                return
                
            # Parse participants list
            participants = []
            if args:
                parts = args.split()
                if len(parts) != 2:
                    await event.respond("❌ **Usage**: `.mm <user1> <user2>` (Must provide exactly two participants)")
                    return
                participants = parts
            else:
                # No arguments: iterate current group members
                try:
                    async for user in client.iter_participants(chat_id):
                        if not user.bot and user.id != config.OWNER_ID:
                            username = getattr(user, "username", None)
                            participants.append(f"@{username}" if username else str(user.id))
                except Exception as e:
                    logger.warning(f"Could not iterate participants in chat {chat_id}: {e}")
                    
                if not participants:
                    participants = ["Group Members"]
            
            # Create deal in SQLite bound to the current group
            deal_id = await db.create_deal(chat_id, participants)
            formatted_deal_id = f"{deal_id:04d}"
            
            naming_template = settings.get("group_naming_template", "MM • Deal #{deal_id}")
            title = naming_template.replace("{deal_id}", formatted_deal_id)
            status_msg = await event.respond(f"⏳ Activating **Deal #{formatted_deal_id}** in this group...")
            
            added = []
            failed = []
            
            # If arguments are provided, resolve and try to invite them into this group
            if args:
                from telethon.tl.functions.messages import AddChatUserRequest
                from telethon.tl.functions.channels import InviteToChannelRequest
                from telethon.errors import UserAlreadyParticipantError
                from userbot.services.group_service import call_with_retry
                
                chat_peer = await client.get_input_entity(chat_id)
                
                for p in participants:
                    try:
                        user_ent = await group_service.resolve_user_entity(client, p)
                        try:
                            if isinstance(chat_peer, types.InputPeerChat):
                                await call_with_retry(client, AddChatUserRequest(chat_id=chat_peer.chat_id, user_id=user_ent, fwd_limit=0))
                            else:
                                await call_with_retry(client, InviteToChannelRequest(channel=chat_peer, users=[user_ent]))
                            
                            identifier = getattr(user_ent, "username", None) or str(user_ent.id)
                            added.append(f"@{identifier}" if getattr(user_ent, "username", None) else identifier)
                        except UserAlreadyParticipantError:
                            identifier = getattr(user_ent, "username", None) or str(user_ent.id)
                            added.append(f"@{identifier}" if getattr(user_ent, "username", None) else identifier)
                        except (UserPrivacyRestrictedError, RPCError) as ae:
                            logger.warning(f"Failed to add {p} directly: {ae}")
                            failed.append(p)
                    except Exception as e:
                        logger.error(f"Failed to resolve/add participant {p}: {e}")
                        failed.append(p)
            else:
                # No arguments: they are already in the group
                added = list(participants)
                
            # Export group invite link
            chat_entity = await client.get_entity(chat_id)
            invite_link = await group_service.get_invite_link(client, chat_entity)
            
            # Attempt to DM invite link to failed users
            failed_notified = []
            failed_unnotified = []
            
            if failed and invite_link:
                for p_id in failed:
                    try:
                        await client.send_message(
                            p_id,
                            f"🤝 **Hello! You have been invited to join Deal #{formatted_deal_id}** in group chat.\n\n"
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
                f"🤝 **Deal #{formatted_deal_id} activated in this group.**\n\n"
                "Please read the Terms of Service before proceeding.\n"
                "Both parties should confirm the agreed amount and transaction terms before payment.\n\n"
                f"• **Participants Added**: {', '.join(added) if added else 'None'}\n"
            )
            if failed_notified:
                welcome_text += f"✉️ **Invite Link Sent via DM to**: {', '.join(failed_notified)} (due to group invite privacy settings)\n"
            if failed_unnotified:
                welcome_text += f"⚠️ **Failed to add/DM**: {', '.join(failed_unnotified)}\n"
                if invite_link:
                    welcome_text += f"🔗 **Manual Invite Link**: {invite_link}\n"
            
            await client.send_message(chat_id, welcome_text)
            
            # Pin TOS
            tos_text = settings.get("tos_text")
            if tos_text:
                tos_msg = await client.send_message(
                    chat_id, 
                    f"📜 **Terms of Service for Deal #{formatted_deal_id}**\n\n{tos_text}"
                )
                try:
                    await client.pin_message(chat_id, tos_msg.id, notify=True)
                except Exception as pe:
                    logger.warning(f"Could not pin TOS message in group {chat_id}: {pe}")
            
            await status_msg.delete()
            return

        # 2. New Group Creation Pathway (In DMs/Private Chat)
        if not args:
            await event.respond(
                "❌ **Usage**: `.mm <user1> <user2>`\n"
                "(Specify participants in private chat to create a new group, or run `.mm` inside a group chat to activate it)"
            )
            return
            
        parts = args.split()
        if len(parts) != 2:
            await event.respond("❌ **Usage**: `.mm <user1> <user2>` (Must provide exactly two participants)")
            return
            
        # Insert placeholder to get sequential deal_id
        try:
            deal_id = await db.create_deal(0, parts)  # Temporary chat_id = 0
        except Exception as e:
            logger.error(f"Failed to initialize deal in database: {e}")
            await event.respond(f"❌ **Database Error**: Could not initialize deal: {e}")
            return
            
        formatted_deal_id = f"{deal_id:04d}"
        naming_template = settings.get("group_naming_template", "MM • Deal #{deal_id}")
        title = naming_template.replace("{deal_id}", formatted_deal_id)
        
        status_msg = await event.respond(f"⏳ Creating group **{title}**...")
        
        try:
            chat_entity, added, failed = await group_service.create_mm_group(client, title, parts)
        except Exception as e:
            # Clean up placeholder
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
            
        from telethon import utils
        signed_chat_id = utils.get_peer_id(chat_entity)
        
        await db.update_deal(deal_id, chat_id=signed_chat_id, participants=str(added))
        
        # Export group invite link
        invite_link = await group_service.get_invite_link(client, chat_entity)
        
        # Attempt to DM invite link to failed users
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
        
        # Pin TOS
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
                
        await status_msg.delete()
        await event.respond(f"✅ **Deal #{formatted_deal_id} group created successfully!**\nGroup Title: {title}")

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
