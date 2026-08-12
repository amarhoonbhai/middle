from telethon import TelegramClient, events
from userbot.services.permissions import owner_command

def register_settings_handlers(client: TelegramClient, db) -> None:
    @client.on(events.NewMessage(pattern=r'^[./]settings$'))
    @owner_command(db)
    async def settings_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        total_deals, active_deals = await db.get_stats()
        
        btc_ok = "✅ Yes" if settings.get("btc_address") else "❌ No"
        eth_ok = "✅ Yes" if settings.get("eth_address") else "❌ No"
        ltc_ok = "✅ Yes" if settings.get("ltc_address") else "❌ No"
        tos_ok = "✅ Yes" if settings.get("tos_text") else "❌ No"
        
        fee_pct = settings.get("fee_percentage", "3.0")
        min_fee = settings.get("min_fee", "0.0")
        
        response = (
            "🛡️ **SPINIFY ESCROW SYSTEM STATUS**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ **Service Configurations:**\n"
            f" • **Fee Rate**: `{fee_pct}%`\n"
            f" • **Minimum Fee**: `${float(min_fee or 0):,.2f}`\n"
            f" • **BTC Wallet**: `{settings.get('btc_address') or 'Not Configured'}`\n"
            f" • **ETH Wallet**: `{settings.get('eth_address') or 'Not Configured'}`\n"
            f" • **LTC Wallet**: `{settings.get('ltc_address') or 'Not Configured'}`\n\n"
            "📊 **Escrow Statistics:**\n"
            f" • **TOS Status**: {tos_ok}\n"
            f" • **Active Deals**: `{active_deals}`\n"
            f" • **Total Processed**: `{total_deals}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await event.respond(response)
