from telethon import TelegramClient, events
from userbot.services.permissions import owner_command
from userbot.utils.helpers import (
    validate_btc_address,
    validate_eth_address,
    validate_ltc_address
)

def register_crypto_handlers(client: TelegramClient, db, is_userbot: bool = False) -> None:
    if not is_userbot:
        return
        
    async def _get_deal_amount_suffix(chat_id: int) -> str:
        """Helper to get a detailed transaction summary suffix if an active deal has an amount set."""
        deal = await db.get_deal(chat_id)
        if deal:
            from userbot.utils.helpers import parse_decimal, format_currency
            amount = parse_decimal(deal.get("amount") or "0.00") or 0
            fee = parse_decimal(deal.get("fee") or "0.00") or 0
            if amount > 0:
                total = amount + fee
                return (
                    f"\n\n**Escrow Deal Info:**\n"
                    f"• **Amount**: {format_currency(amount)}\n"
                    f"• **Escrow Fee**: {format_currency(fee)}\n"
                    f"• **Total Expected Deposit**: `{format_currency(total)}`"
                )
        return ""

    @client.on(events.NewMessage(pattern=r'^\.btc$'))
    async def btc_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        addr = settings.get("btc_address")
        if not addr:
            await event.respond("❌ **BTC Address is not configured.**\nUse `.setbtc <address>` to set it.")
            return
        suffix = await _get_deal_amount_suffix(event.chat_id)
        await event.respond(f"💰 **BTC Payout Address**\n\n`{addr}`\n\nNetwork: Bitcoin{suffix}")

    @client.on(events.NewMessage(pattern=r'^\.eth$'))
    async def eth_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        addr = settings.get("eth_address")
        if not addr:
            await event.respond("❌ **ETH Address is not configured.**\nUse `.seteth <address>` to set it.")
            return
        suffix = await _get_deal_amount_suffix(event.chat_id)
        await event.respond(f"💰 **ETH Payout Address**\n\n`{addr}`\n\nNetwork: Ethereum (ERC-20){suffix}")

    @client.on(events.NewMessage(pattern=r'^\.ltc$'))
    async def ltc_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        addr = settings.get("ltc_address")
        if not addr:
            await event.respond("❌ **LTC Address is not configured.**\nUse `.setltc <address>` to set it.")
            return
        suffix = await _get_deal_amount_suffix(event.chat_id)
        await event.respond(f"💰 **LTC Payout Address**\n\n`{addr}`\n\nNetwork: Litecoin{suffix}")

    @client.on(events.NewMessage(pattern=r'^\.setbtc(?:\s+(.+))?$'))
    @owner_command(db)
    async def setbtc_command(event: events.NewMessage.Event) -> None:
        addr = event.pattern_match.group(1)
        if not addr:
            await event.respond("❌ **Usage**: `.setbtc <address>`")
            return
        addr = addr.strip()
        if not validate_btc_address(addr):
            await event.respond("❌ **Error**: Invalid BTC address format. It should start with `1`, `3`, or `bc1`.")
            return
        await db.update_settings(btc_address=addr)
        await event.respond(f"✅ **Success**: BTC address updated to:\n`{addr}`")

    @client.on(events.NewMessage(pattern=r'^\.seteth(?:\s+(.+))?$'))
    @owner_command(db)
    async def seteth_command(event: events.NewMessage.Event) -> None:
        addr = event.pattern_match.group(1)
        if not addr:
            await event.respond("❌ **Usage**: `.seteth <address>`")
            return
        addr = addr.strip()
        if not validate_eth_address(addr):
            await event.respond("❌ **Error**: Invalid ETH address format. It should start with `0x` followed by 40 hex characters.")
            return
        await db.update_settings(eth_address=addr)
        await event.respond(f"✅ **Success**: ETH address updated to:\n`{addr}`")

    @client.on(events.NewMessage(pattern=r'^\.setltc(?:\s+(.+))?$'))
    @owner_command(db)
    async def setltc_command(event: events.NewMessage.Event) -> None:
        addr = event.pattern_match.group(1)
        if not addr:
            await event.respond("❌ **Usage**: `.setltc <address>`")
            return
        addr = addr.strip()
        if not validate_ltc_address(addr):
            await event.respond("❌ **Error**: Invalid LTC address format. It should start with `L`, `M`, `3`, or `ltc1`.")
            return
        await db.update_settings(ltc_address=addr)
        await event.respond(f"✅ **Success**: LTC address updated to:\n`{addr}`")
