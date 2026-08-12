import os
import logging
from telethon import TelegramClient, events, Button
from userbot.services.permissions import owner_command, is_owner
from userbot.services import group_service

logger = logging.getLogger(__name__)

def register_help_handlers(client: TelegramClient, db) -> None:
    
    @client.on(events.NewMessage(pattern=r'^[./]help'))
    @owner_command(db)
    async def help_command(event: events.NewMessage.Event) -> None:
        help_text = (
            "ℹ️ **Spinify Escrow Commands**\n\n"
            "**Escrow Commands**\n"
            "• `/mm @buyer @seller` - Register daily deal\n"
            "• `/setgroup` - Set current group as daily room\n"
            "• `/close` - Close current deal\n"
            "• `/name <title>` - Rename current group\n"
            "• `/fee <amount>` - Calculate transaction fee\n"
            "• `/rec` - Mark funds as received\n"
            "• `/tos` - View Terms of Service\n\n"
            "**Crypto Addresses**\n"
            "• `/btc` - View BTC address\n"
            "• `/eth` - View ETH address\n"
            "• `/ltc` - View LTC address\n\n"
            "**Settings (Owner Only)**\n"
            "• `/settings` - View current configuration\n"
            "• `/setfee <%>` - Set default fee percentage\n"
            "• `/setminfee <val>` - Set minimum fee amount\n"
            "• `/setbtc <addr>` - Set BTC wallet address\n"
            "• `/seteth <addr>` - Set ETH wallet address\n"
            "• `/setltc <addr>` - Set LTC wallet address\n"
            "• `/settos <text>` - Set Terms of Service text\n"
            "• `/block` - Block user (reply to their message)\n\n"
            "*(Commands support both / and . prefixes)*"
        )
        await event.respond(help_text)

    @client.on(events.NewMessage(pattern=r'^[./]start$'))
    async def start_command(event: events.NewMessage.Event) -> None:
        """Welcomes users in DM, greets them, and registers the bottom menu."""
        sender = await event.get_sender()
        if not sender:
            return
            
        first_name = getattr(sender, 'first_name', '') or ''
        last_name = getattr(sender, 'last_name', '') or ''
        full_name = f"{first_name} {last_name}".strip() or "User"
        
        # Check if the user is the owner
        owner_active = await is_owner(sender.id, db)
        
        welcome_text = (
            f"👋 **Welcome to Spinify Escrow**\n\n"
            f"Hello {full_name}, I am your automated escrow manager.\n\n"
            f"• **Your Telegram ID**: `{sender.id}`\n\n"
        )
        if owner_active:
            welcome_text += "Use the buttons below or `/help` to see all admin commands."
        else:
            welcome_text += "Use the buttons below to check wallets or terms of service."
        
        # Build interactive inline buttons
        if owner_active:
            buttons = [
                [
                    Button.inline("📜 Terms of Service", data="btn_tos"),
                ],
                [
                    Button.inline("💰 Escrow Wallets", data="btn_crypto"),
                    Button.inline("📊 Bot Stats", data="btn_stats")
                ]
            ]
            
            # Bottom persistent reply keyboard buttons for Owner
            reply_keyboard = [
                [Button.text("🔗 Join Group"), Button.text("📜 Terms of Service")],
                [Button.text("💰 Escrow Wallets"), Button.text("📊 Bot Stats")],
                [Button.text("⚙️ Settings")]
            ]
        else:
            buttons = [
                [
                    Button.inline("📜 Terms of Service", data="btn_tos"),
                ],
                [
                    Button.inline("💰 Escrow Wallets", data="btn_crypto")
                ]
            ]
            
            # Bottom persistent reply keyboard buttons for General Users
            reply_keyboard = [
                [Button.text("🔗 Join Group"), Button.text("📜 Terms of Service")],
                [Button.text("💰 Escrow Wallets")]
            ]
        
        try:
            await event.respond(welcome_text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error executing start command: {e}")
            
        # Send persistent bottom menu
        try:
            await event.respond("⌨️ Quick menu:", buttons=reply_keyboard, resize_keyboard=True)
        except Exception as e:
            logger.warning(f"Could not send reply keyboard: {e}")

    @client.on(events.NewMessage(pattern=r'^⚙️ Settings$'))
    @owner_command(db)
    async def settings_button_handler(event: events.NewMessage.Event) -> None:
        """Triggers settings display from bottom menu button (restricted to owner)."""
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

    @client.on(events.CallbackQuery)
    async def callback_query_handler(event: events.CallbackQuery.Event) -> None:
        """Handles inline keyboard button callback queries."""
        data = event.data.decode("utf-8")
        settings = await db.get_settings()
        
        # Acknowledge the callback immediately
        await event.answer()
        
        if data == "btn_tos":
            tos_text = settings.get("tos_text") or "Terms of Service not configured yet."
            await event.reply(f"📜 **Terms of Service**\n\n{tos_text}")
            
        elif data == "btn_crypto":
            btc = settings.get("btc_address") or "Not Set"
            eth = settings.get("eth_address") or "Not Set"
            ltc = settings.get("ltc_address") or "Not Set"
            wallet_info = (
                "💰 **Escrow Crypto Addresses**\n\n"
                f"• **BTC**: `{btc}`\n"
                f"• **ETH**: `{eth}`\n"
                f"• **LTC**: `{ltc}`"
            )
            await event.reply(wallet_info)
            
        elif data == "btn_stats":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**: Only the Middleman Owner can view stats.")
            else:
                total, active = await db.get_stats()
                stats_info = (
                    "📊 **Escrow Statistics**\n\n"
                    f"• **Active Deals**: `{active}`\n"
                    f"• **Total Closed Deals**: `{total}`"
                )
                await event.reply(stats_info)
            
        elif data == "btn_close_deal":
            clicker_id = event.sender_id
            if not await is_owner(clicker_id, db):
                await event.reply("❌ **Access Denied**: Only the Middleman Owner can close deals.")
            else:
                await event.reply("⚠️ **Closing Deal**: Type `/close` or `/close confirm` in this chat to execute.")

    # --- Persistent Reply Keyboard Listeners ---

    @client.on(events.NewMessage(pattern=r'^🔗 Join Group$'))
    async def join_group_button_handler(event: events.NewMessage.Event) -> None:
        """Sends today's daily group invite link to the user so they can join it."""
        settings = await db.get_settings()
        daily_group_id = settings.get("daily_group_id")
        daily_group_date = settings.get("daily_group_date")
        
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if daily_group_id and daily_group_date == today_str:
            try:
                chat_entity = await event.client.get_entity(daily_group_id)
                invite_link = await group_service.get_invite_link(event.client, chat_entity)
                if invite_link:
                    await event.respond(
                        f"🔗 **Daily Room Active**\n\n"
                        f"Click the link below to join today's active escrow deal room:\n{invite_link}"
                    )
                else:
                    await event.respond("⚠️ Today's daily group is active, but I couldn't generate the invite link. Please ask the Middleman Owner for assistance.")
            except Exception as e:
                logger.error(f"Error fetching daily group entity: {e}")
                await event.respond("⚠️ Today's daily group is active, but I could not access it. Please contact the Middleman Owner.")
        else:
            await event.respond(
                "ℹ️ **No active group room for today yet.**\n\n"
                "The Middleman Owner will create or register the room once a deal is initiated."
            )

    @client.on(events.NewMessage(pattern=r'^📜 Terms of Service$'))
    async def tos_button_handler(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        tos_text = settings.get("tos_text") or "Terms of Service not configured yet."
        await event.respond(f"📜 **Terms of Service**\n\n{tos_text}")

    @client.on(events.NewMessage(pattern=r'^💰 Escrow Wallets$'))
    async def wallets_button_handler(event: events.NewMessage.Event) -> None:
        settings = await db.get_settings()
        btc = settings.get("btc_address") or "Not Set"
        eth = settings.get("eth_address") or "Not Set"
        ltc = settings.get("ltc_address") or "Not Set"
        wallet_info = (
            "💰 **Escrow Crypto Addresses**\n\n"
            f"• **BTC**: `{btc}`\n"
            f"• **ETH**: `{eth}`\n"
            f"• **LTC**: `{ltc}`"
        )
        await event.respond(wallet_info)

    @client.on(events.NewMessage(pattern=r'^📊 Bot Stats$'))
    async def stats_button_handler(event: events.NewMessage.Event) -> None:
        total, active = await db.get_stats()
        stats_info = (
            "📊 **Escrow Statistics**\n\n"
            f"• **Active Deals**: `{active}`\n"
            f"• **Total Closed Deals**: `{total}`"
        )
        await event.respond(stats_info)
