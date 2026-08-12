from telethon import TelegramClient, events
from userbot.services.permissions import owner_command

def register_help_handlers(client: TelegramClient, db) -> None:
    @client.on(events.NewMessage(pattern=r'^[./]help'))
    @owner_command(db)
    async def help_command(event: events.NewMessage.Event) -> None:
        help_text = (
            "ℹ️ **Available Commands (Supports both / and . prefixes)**\n\n"
            "**MM Operations:**\n"
            "• `/mm @buyer @seller` - Register/setup daily deal room\n"
            "• `/close` - Close current deal safely (requires confirmation)\n"
            "• `/name <name>` - Rename the MM group\n"
            "• `/fee <amount>` - Calculate middleman fee\n"
            "• `/rec` - Mark funds as received\n"
            "• `/tos` - Send configured Terms of Service\n\n"
            "**Crypto Addresses:**\n"
            "• `/btc` - Show BTC address\n"
            "• `/eth` - Show ETH address\n"
            "• `/ltc` - Show LTC address\n\n"
            "**Owner Settings:**\n"
            "• `/settings` - View current settings and statistics\n"
            "• `/setfee <%>` - Set default fee percentage\n"
            "• `/setminfee <val>` - Set minimum fee amount\n"
            "• `/setbtc <addr>` - Set BTC wallet address\n"
            "• `/seteth <addr>` - Set ETH wallet address\n"
            "• `/setltc <addr>` - Set LTC wallet address\n"
            "• `/settos <text>` - Set Terms of Service (or reply with `/settos`)\n\n"
            "**Moderation:**\n"
            "• `/block` - Block user (reply to their message)"
        )
        await event.respond(help_text)
