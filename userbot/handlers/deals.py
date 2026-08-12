from telethon import TelegramClient, events
from userbot.services.permissions import owner_command

def register_deal_handlers(client: TelegramClient, db, is_userbot: bool = False) -> None:
    if not is_userbot:
        return
        
    @client.on(events.NewMessage(pattern=r'^\.rec$'))
    @owner_command(db)
    async def rec_command(event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        deal = await db.get_deal(chat_id)
        if not deal:
            await event.respond("❌ **Error**: This command must be executed inside an active MM group.")
            return
            
        if deal.get("status") == "closed":
            await event.respond("⚠️ **Notice**: This deal is already closed.")
            return
            
        if deal.get("funds_received"):
            await event.respond("⚠️ **Notice**: Funds are already marked as received for this deal.")
            return
            
        deal_id = deal["deal_id"]
        formatted_deal_id = f"{deal_id:04d}"
        
        # Update database and record event
        await db.update_deal(deal_id, funds_received=1)
        await db.log_deal_event(deal_id, "funds_received", "Owner marked funds as received.")
        
        response = (
            "✅ **Funds Received**\n\n"
            f"Payment has been confirmed as received for **Deal #{formatted_deal_id}**.\n\n"
            "The transaction may now proceed to the next stage."
        )
        await event.respond(response)

    @client.on(events.NewMessage(pattern=r'^\.tos$'))
    async def tos_command(event: events.NewMessage.Event) -> None:
        deal = await db.get_deal(event.chat_id)
        settings = await db.get_settings()
        tos_text = settings.get("tos_text")
        
        if not tos_text:
            await event.respond("❌ **TOS is not configured.**\nUse `.settos <text>` to configure it.")
            return
            
        if deal:
            formatted_deal_id = f"{deal['deal_id']:04d}"
            prefix = f"📜 **Terms of Service for Deal #{formatted_deal_id}**\n\n"
        else:
            prefix = "📜 **Terms of Service**\n\n"
            
        await event.respond(f"{prefix}{tos_text}")

    @client.on(events.NewMessage(pattern=r'^\.settos(?:\s+([\s\S]+))?$'))
    @owner_command(db)
    async def settos_command(event: events.NewMessage.Event) -> None:
        tos_text = None
        args = event.pattern_match.group(1)
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                tos_text = reply_msg.text
        elif args:
            tos_text = args.strip()
            
        if not tos_text:
            await event.respond("❌ **Usage**: Reply to a message containing the TOS with `.settos` or run `.settos <text>`.")
            return
            
        await db.update_settings(tos_text=tos_text)
        await event.respond("✅ **Success**: Terms of Service configured successfully.")
