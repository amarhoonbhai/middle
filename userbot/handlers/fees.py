from decimal import Decimal
from telethon import TelegramClient, events
from userbot.services.permissions import owner_command
from userbot.services.fee_service import calculate_fee
from userbot.utils.helpers import format_currency, parse_decimal

def register_fee_handlers(client: TelegramClient, db, is_userbot: bool = False) -> None:
    if not is_userbot:
        return
        
    @client.on(events.NewMessage(pattern=r'^\.fee(?:\s+(.+))?$'))
    async def fee_command(event: events.NewMessage.Event) -> None:
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.fee <amount>` (e.g., `.fee 1000`)")
            return
            
        amount = parse_decimal(args)
        if amount is None or amount <= 0:
            await event.respond("❌ **Error**: Please provide a valid positive deal amount.")
            return
            
        settings = await db.get_settings()
        fee_pct = Decimal(settings.get("fee_percentage", "3.0"))
        min_fee = Decimal(settings.get("min_fee", "0.0"))
        
        fee, total = calculate_fee(amount, fee_pct, min_fee)
        
        response = (
            f"💰 **Fee Calculation**\n\n"
            f"• **Deal Amount**: {format_currency(amount)}\n"
            f"• **MM Fee ({fee_pct}%)**: {format_currency(fee)}\n"
            f"• **Total**: {format_currency(total)}"
        )
        await event.respond(response)

    @client.on(events.NewMessage(pattern=r'^\.setfee(?:\s+(.+))?$'))
    @owner_command(db)
    async def setfee_command(event: events.NewMessage.Event) -> None:
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.setfee <percentage>` (e.g., `.setfee 3` or `.setfee 2.5`)")
            return
            
        fee_pct = parse_decimal(args)
        if fee_pct is None or fee_pct < 0 or fee_pct > 100:
            await event.respond("❌ **Error**: Fee percentage must be a number between 0 and 100.")
            return
            
        await db.update_settings(fee_percentage=str(fee_pct))
        await event.respond(f"✅ **Success**: Default MM fee percentage updated to **{fee_pct}%**.")

    @client.on(events.NewMessage(pattern=r'^\.setminfee(?:\s+(.+))?$'))
    @owner_command(db)
    async def setminfee_command(event: events.NewMessage.Event) -> None:
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.setminfee <amount>` (e.g., `.setminfee 10`)")
            return
            
        min_fee = parse_decimal(args)
        if min_fee is None or min_fee < 0:
            await event.respond("❌ **Error**: Minimum fee must be a valid non-negative number.")
            return
            
        await db.update_settings(min_fee=str(min_fee))
        await event.respond(f"✅ **Success**: Minimum MM fee updated to **{format_currency(min_fee)}**.")
