from telethon import TelegramClient, events
from userbot.services.permissions import owner_command

def register_settings_handlers(client: TelegramClient, db) -> None:
    @client.on(events.NewMessage(pattern=r'^[./]settings$'))
    @owner_command(db)
    async def settings_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        total_deals, active_deals = await db.get_stats()
        
        tos_ok = "✅ Yes" if settings.get("tos_text") else "❌ No"
        fee_pct = settings.get("fee_percentage", "3.0")
        min_fee = settings.get("min_fee", "0.0")
        
        response = (
            "⚙️ **Spinify Escrow Settings**\n\n"
            f"• **Fee Rate**: `{fee_pct}%`\n"
            f"• **Minimum Fee**: `${float(min_fee or 0):,.2f}`\n"
            f"• **BTC Wallet**: `{settings.get('btc_address') or 'Not Configured'}`\n"
            f"• **ETH Wallet**: `{settings.get('eth_address') or 'Not Configured'}`\n"
            f"• **LTC Wallet**: `{settings.get('ltc_address') or 'Not Configured'}`\n"
            f"• **TOS Status**: {tos_ok}\n\n"
            f"• **Active Deals**: `{active_deals}`\n"
            f"• **Total Deals**: `{total_deals}`"
        )
        await event.respond(response)

    @client.on(events.NewMessage(pattern=r'^[./]setowner(?:\s+(.+))?$'))
    @owner_command(db)
    async def setowner_command(event: events.NewMessage.Event) -> None:
        """Sets a new owner ID. Can be run with an ID argument or in reply to a user."""
        args = event.pattern_match.group(1)
        new_owner_id = None
        
        # Check if replying to a message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            new_owner_id = reply_msg.sender_id
        elif args:
            try:
                new_owner_id = int(args.strip())
            except ValueError:
                await event.respond("❌ **Error**: Invalid owner ID format. Must be a numeric ID.")
                return
                
        if not new_owner_id:
            await event.respond("❌ **Error**: Please provide a numeric user ID or reply to a user's message with `/setowner`.")
            return
            
        await db.update_settings(owner_id=new_owner_id)
        await event.respond(f"✅ **Success**: Owner ID updated to `{new_owner_id}`.")
