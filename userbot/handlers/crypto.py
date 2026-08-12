from telethon import TelegramClient, events
from userbot.services.permissions import owner_command
from userbot.utils.helpers import (
    validate_btc_address,
    validate_eth_address,
    validate_ltc_address
)

def register_crypto_handlers(client: TelegramClient, db) -> None:
    @client.on(events.NewMessage(pattern=r'^[./]btc$'))
    async def btc_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        addr = settings.get("btc_address")
        if not addr:
            await event.respond("❌ **BTC Address is not configured.**\nUse `/setbtc <address>` to set it.")
            return
        await event.respond(f"**BTC Address**\n\n`{addr}`\n\nNetwork: Bitcoin")

    @client.on(events.NewMessage(pattern=r'^[./]eth$'))
    async def eth_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        addr = settings.get("eth_address")
        if not addr:
            await event.respond("❌ **ETH Address is not configured.**\nUse `/seteth <address>` to set it.")
            return
        await event.respond(f"**ETH Address**\n\n`{addr}`\n\nNetwork: Ethereum (ERC-20)")

    @client.on(events.NewMessage(pattern=r'^[./]ltc$'))
    async def ltc_command(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        addr = settings.get("ltc_address")
        if not addr:
            await event.respond("❌ **LTC Address is not configured.**\nUse `/setltc <address>` to set it.")
            return
        await event.respond(f"**LTC Address**\n\n`{addr}`\n\nNetwork: Litecoin")

    @client.on(events.NewMessage(pattern=r'^[./]setbtc(?:\s+(.+))?$'))
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

    @client.on(events.NewMessage(pattern=r'^[./]seteth(?:\s+(.+))?$'))
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

    @client.on(events.NewMessage(pattern=r'^[./]setltc(?:\s+(.+))?$'))
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
