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
    @client.on(events.NewMessage(pattern=r'^[./]mm(?:\s+(.+))?$'))
    @owner_command(db)
    async def mm_command(event: events.NewMessage.Event) -> None:
        args = event.pattern_match.group(1)
        from userbot.config import config
        
        # 1. Hybrid check: If no arguments and executed in DMs, warn and return
        if not args and not event.is_group:
            await event.respond(
                "❌ **Usage**: `.mm <user1> <user2>`\n"
                "(Specify participants in private chat to create/reuse a daily group, or run `.mm` inside a group chat to activate it)"
            )
            return

        from telethon.tl import types
        from telethon.errors import UserPrivacyRestrictedError, RPCError
        import json
        
        chat_id = event.chat_id
        is_group = event.is_group
        
        settings = await db.get_settings()
        
        # 1. Existing Group Activation Pathway (typed without arguments inside an ad-hoc group chat)
        if is_group and not args:
            # Check if there is already an active deal in this group
            existing_deal = await db.get_deal(chat_id)
            if existing_deal:
                formatted_deal_id = f"{existing_deal['deal_id']:04d}"
                await event.respond(f"⚠️ **Notice**: This group is already registered for active **Deal #{formatted_deal_id}**.")
                return
                
            # Parse participants list from current group members
            participants = []
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
            
            welcome_text = (
                f"🤝 **Deal #{formatted_deal_id} activated in this group.**\n\n"
                "Please read the Terms of Service before proceeding.\n"
                "Both parties should confirm the agreed amount and transaction terms before payment.\n\n"
                f"• **Participants**: {', '.join(participants)}"
            )
            # Attach interactive buttons
            from telethon import Button
            welcome_buttons = [
                [
                    Button.inline("📜 Read TOS", data="btn_tos"),
                    Button.inline("💰 Wallets", data="btn_crypto")
                ],
                [
                    Button.inline("🏁 Close Deal", data="btn_close_deal")
                ]
            ]
            await event.respond(welcome_text, buttons=welcome_buttons)
            
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
            return

        # 2. Daily Group Activation / Creation Pathway (runs when arguments are provided)
        if not args:
            await event.respond(
                "❌ **Usage**: `.mm <user1> <user2>`\n"
                "(Specify participants in private chat to create/reuse a daily group, or run `.mm` inside a group chat to activate it)"
            )
            return
            
        parts = args.split()
        if len(parts) != 2:
            await event.respond("❌ **Usage**: `.mm <user1> <user2>` (Must provide exactly two participants)")
            return
            
        # Determine today's UTC date
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Load daily group settings
        daily_group_id = settings.get("daily_group_id")
        daily_group_date = settings.get("daily_group_date")
        
        target_chat_id = None
        invite_link = None
        new_group_created = False
        chat_entity = None
        
        # Check if we can reuse today's daily group
        if daily_group_id and daily_group_date == today_str:
            try:
                chat_entity = await client.get_entity(daily_group_id)
                target_chat_id = daily_group_id
                logger.info(f"Reusing today's registered daily group: {target_chat_id}")
            except Exception as e:
                logger.warning(f"Today's registered daily group {daily_group_id} is inaccessible: {e}. Recreating...")
                
        # If we need to create/recreate a new daily group
        if not target_chat_id:
            # Leave previous day's daily group to clean it up (daily cleanup)
            if daily_group_id:
                try:
                    logger.info(f"Cleaning up/leaving previous daily group: {daily_group_id}...")
                    old_entity = await client.get_entity(daily_group_id)
                    await group_service.leave_group(client, old_entity)
                except Exception as le:
                    logger.warning(f"Could not automatically clean up old daily group {daily_group_id}: {le}")
            
            # Create today's daily room title (e.g. MM Room - 12 Aug)
            day_label = datetime.now(timezone.utc).strftime("%d %b")
            title = f"MM Room - {day_label}"
            
            status_msg = await event.respond(f"⏳ Creating new daily group room **{title}**...")
            try:
                chat_entity, added, failed = await group_service.create_mm_group(client, title, parts)
                from telethon import utils
                target_chat_id = utils.get_peer_id(chat_entity)
                new_group_created = True
                
                # Save daily group info in database settings
                await db.update_settings(daily_group_id=target_chat_id, daily_group_date=today_str)
                await status_msg.delete()
            except Exception as e:
                logger.error(f"Failed to create daily group: {e}")
                await status_msg.edit(f"❌ **Failed to create daily group**: {str(e)}")
                return
                
        # SQLite Placeholder Deal Creation (to reserve sequential deal_id)
        deal_id = await db.create_deal(target_chat_id, parts)
        formatted_deal_id = f"{deal_id:04d}"
        
        # Try to invite participants if reusing today's group
        if not new_group_created:
            added = []
            failed = []
            # Reusing existing group: try to add the participants into it
            from telethon.tl.functions.messages import AddChatUserRequest
            from telethon.tl.functions.channels import InviteToChannelRequest
            from telethon.errors import UserAlreadyParticipantError
            from userbot.services.group_service import call_with_retry
            
            chat_peer = await client.get_input_entity(target_chat_id)
            
            for p in parts:
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
                        logger.warning(f"Failed to add participant {p} directly to daily group: {ae}")
                        failed.append(p)
                except Exception as e:
                    logger.error(f"Failed to resolve/add participant {p}: {e}")
                    failed.append(p)
        else:
            # Newly created group: participants were already returned
            pass
            
        # Update SQLite deal record with all resolved participants
        all_participants = added + failed
        await db.update_deal(deal_id, participants=json.dumps(all_participants))
        
        # Export group invite link
        if not chat_entity:
            chat_entity = await client.get_entity(target_chat_id)
        invite_link = await group_service.get_invite_link(client, chat_entity)
        
        # Attempt to DM invite link to failed users
        failed_notified = []
        failed_unnotified = []
        
        if failed and invite_link:
            for p_id in failed:
                try:
                    await client.send_message(
                        p_id,
                        f"🤝 **Hello! You have been invited to join Deal #{formatted_deal_id}** in our daily room.\n\n"
                        f"Since your privacy settings prevented adding you automatically, "
                        f"please click the link below to join today's deal room:\n{invite_link}"
                    )
                    failed_notified.append(p_id)
                except Exception as dme:
                    logger.warning(f"Could not send DM invite link to {p_id}: {dme}")
                    failed_unnotified.append(p_id)
        else:
            failed_unnotified = list(failed)
            
        # Welcome message inside the daily group chat
        welcome_text = (
            f"🤝 **Deal #{formatted_deal_id} registered in this daily room.**\n\n"
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
                
        # Attach interactive buttons
        from telethon import Button
        welcome_buttons = [
            [
                Button.inline("📜 Read TOS", data="btn_tos"),
                Button.inline("💰 Wallets", data="btn_crypto")
            ],
            [
                Button.inline("🏁 Close Deal", data="btn_close_deal")
            ]
        ]
        await client.send_message(target_chat_id, welcome_text, buttons=welcome_buttons)
        
        # Pin TOS
        tos_text = settings.get("tos_text")
        if tos_text:
            tos_msg = await client.send_message(
                target_chat_id, 
                f"📜 **Terms of Service for Deal #{formatted_deal_id}**\n\n{tos_text}"
            )
            try:
                await client.pin_message(target_chat_id, tos_msg.id, notify=True)
            except Exception as pe:
                logger.warning(f"Could not pin TOS message in daily group {target_chat_id}: {pe}")
                
        # Send confirmation to the owner in command chat
        day_label = datetime.now(timezone.utc).strftime("%d %b")
        response_text = f"✅ **Deal #{formatted_deal_id} registered in daily room!**\n• **Group Title**: MM Room - {day_label}"
        if invite_link:
            response_text += f"\n• **Invite Link**: {invite_link}"
        if failed:
            response_text += f"\n\n⚠️ **Participants not added directly**: {', '.join(failed)}"
            
        await event.respond(response_text)

    @client.on(events.NewMessage(pattern=r'^[./]name(?:\s+(.+))?$'))
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

    @client.on(events.NewMessage(pattern=r'^[./]close(?:\s+(.+))?$'))
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
            
            # Kick participants from this deal instead of the bot leaving the daily room
            import json
            participants_data = deal.get("participants")
            kicked_users = []
            if participants_data:
                try:
                    participants_list = json.loads(participants_data)
                    if isinstance(participants_list, list):
                        for p in participants_list:
                            if p and p != "Group Members":
                                try:
                                    await group_service.kick_user(client, chat_id, p)
                                    kicked_users.append(p)
                                except Exception as ke:
                                    logger.warning(f"Could not kick participant {p}: {ke}")
                except Exception as pe:
                    logger.error(f"Failed to parse participants JSON to kick: {pe}")
            
            if kicked_users:
                await event.respond(f"🧹 **Cleaned up daily room**: Removed participants: {', '.join(kicked_users)}")
