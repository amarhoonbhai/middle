import os
import logging
from telethon import TelegramClient, events, Button
from userbot.services.permissions import owner_command, is_owner

logger = logging.getLogger(__name__)

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

    @client.on(events.NewMessage(pattern=r'^[./]start$'))
    async def start_command(event: events.NewMessage.Event) -> None:
        """Welcomes users in DM, fetches their First/Last name and PFP, showing inline buttons."""
        sender = await event.get_sender()
        if not sender:
            return
            
        first_name = getattr(sender, 'first_name', '') or ''
        last_name = getattr(sender, 'last_name', '') or ''
        full_name = f"{first_name} {last_name}".strip() or "User"
        
        # Create temporary dir for profiles
        os.makedirs("logs/profiles", exist_ok=True)
        pfp_path = None
        
        try:
            # Download sender profile picture
            pfp_path = await event.client.download_profile_photo(sender, file="logs/profiles/")
        except Exception as e:
            logger.warning(f"Could not download profile photo for {sender.id}: {e}")
            
        welcome_text = (
            f"👋 **Welcome to the Escrow Middleman Bot, {full_name}!**\n\n"
            "I am your automated transaction security manager. "
            "I help buyers, sellers, and middlemen trade digital assets safely.\n\n"
            "**Quick Actions Menu:**"
        )
        
        # Build interactive inline buttons
        buttons = [
            [
                Button.inline("📜 View Terms of Service", data="btn_tos"),
            ],
            [
                Button.inline("💰 Wallets", data="btn_crypto"),
                Button.inline("📈 Statistics", data="btn_stats")
            ]
        ]
        
        try:
            if pfp_path and os.path.exists(pfp_path):
                # Send photo with welcome text as caption
                await event.client.send_file(
                    event.chat_id,
                    pfp_path,
                    caption=welcome_text,
                    buttons=buttons
                )
                # Remove file from disk after sending
                try:
                    os.remove(pfp_path)
                except Exception:
                    pass
            else:
                await event.respond(welcome_text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error executing start command: {e}")
            await event.respond(welcome_text, buttons=buttons)

    @client.on(events.CallbackQuery)
    async def callback_query_handler(event: events.CallbackQuery.Event) -> None:
        """Handles inline keyboard button callback queries."""
        data = event.data.decode("utf-8")
        settings = await db.get_settings()
        
        # Acknowledge the callback immediately to remove loading spinner
        await event.answer()
        
        if data == "btn_tos":
            tos_text = settings.get("tos_text") or "Terms of Service not configured yet."
            await event.reply(f"📜 **Terms of Service**\n\n{tos_text}")
            
        elif data == "btn_crypto":
            btc = settings.get("btc_address") or "Not Set"
            eth = settings.get("eth_address") or "Not Set"
            ltc = settings.get("ltc_address") or "Not Set"
            wallet_info = (
                "💰 **Escrow Crypto Addresses:**\n\n"
                f"• **BTC**: `{btc}`\n"
                f"• **ETH**: `{eth}`\n"
                f"• **LTC**: `{ltc}`"
            )
            await event.reply(wallet_info)
            
        elif data == "btn_stats":
            total, active = await db.get_stats()
            stats_info = (
                "📊 **Escrow Statistics:**\n\n"
                f"• **Active Deals**: {active}\n"
                f"• **Total Closed Deals**: {total}"
            )
            await event.reply(stats_info)
            
        elif data == "btn_close_deal":
            # Check if clicker is the registered owner
            clicker_id = event.sender_id
            if not await is_owner(clicker_id, db):
                await event.reply("❌ **Access Denied**: Only the Middleman Owner can close deals.")
            else:
                await event.reply("⚠️ **Closing Deal**: Please type `/close` or `/close confirm` in the chat to execute closure.")
