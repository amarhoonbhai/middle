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
            "ℹ️ **SPINIFY ESCROW SYSTEM COMMANDS**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤝 **Escrow Management:**\n"
            " • `/mm @buyer @seller` — Register/setup daily deal room\n"
            " • `/setgroup` — Register current group chat as daily room\n"
            " • `/close` — Initiate secure escrow closure\n"
            " • `/name <title>` — Rename the current group room\n"
            " • `/fee <amount>` — Calculate middleman transaction fee\n"
            " • `/rec` — Mark transaction funds as received\n"
            " • `/tos` — Display configured Terms of Service\n\n"
            "💰 **Crypto Wallets:**\n"
            " • `/btc` — View BTC payment address\n"
            " • `/eth` — View ETH payment address\n"
            " • `/ltc` — View LTC payment address\n\n"
            "⚙️ **Admin Configurations:**\n"
            " • `/settings` — View service parameters and history\n"
            " • `/setfee <%>` — Update default fee rate\n"
            " • `/setminfee <val>` — Update minimum fee amount\n"
            " • `/setbtc <addr>` — Configure BTC payout wallet\n"
            " • `/seteth <addr>` — Configure ETH payout wallet\n"
            " • `/setltc <addr>` — Configure LTC payout wallet\n"
            " • `/settos <text>` — Update Terms of Service text\n\n"
            "🛡️ **Moderation:**\n"
            " • `/block` — Block user from using system (reply to message)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Note: Commands support both `/` and `.` prefixes.*"
        )
        await event.respond(help_text)

    @client.on(events.NewMessage(pattern=r'^[./]start$'))
    async def start_command(event: events.NewMessage.Event) -> None:
        """Welcomes users in DM, displays the premium system banner, greets them, and registers the bottom menu."""
        sender = await event.get_sender()
        if not sender:
            return
            
        first_name = getattr(sender, 'first_name', '') or ''
        last_name = getattr(sender, 'last_name', '') or ''
        full_name = f"{first_name} {last_name}".strip() or "Valued Client"
        
        banner_path = "userbot/assets/banner.jpg"
        
        welcome_text = (
            f"🛡️ **SPINIFY ESCROW SYSTEM SECURED**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👋 **Welcome, {full_name}!**\n\n"
            "I am your automated transaction security manager. "
            "I secure trades between buyers, sellers, and middlemen.\n\n"
            "• **Account Verification**: `Active`\n"
            f"• **Telegram ID**: `{sender.id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ **Quick Action Buttons:**"
        )
        
        # Build interactive inline buttons
        buttons = [
            [
                Button.inline("📜 Terms of Service", data="btn_tos"),
            ],
            [
                Button.inline("💰 Escrow Wallets", data="btn_crypto"),
                Button.inline("📊 Stats Dashboard", data="btn_stats")
            ]
        ]
        
        # Bottom persistent reply keyboard buttons
        reply_keyboard = [
            [Button.text("🔗 Join Group"), Button.text("📜 Terms of Service")],
            [Button.text("💰 Escrow Wallets"), Button.text("📊 Bot Stats")]
        ]
        
        try:
            if os.path.exists(banner_path):
                # Send premium official system banner with welcome text as caption
                await event.client.send_file(
                    event.chat_id,
                    banner_path,
                    caption=welcome_text,
                    buttons=buttons
                )
            else:
                await event.respond(welcome_text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error executing start command: {e}")
            await event.respond(welcome_text, buttons=buttons)
            
        # Send persistent bottom menu as a second message
        try:
            await event.respond("⌨️ Use the bottom menu buttons for quick navigation:", buttons=reply_keyboard, resize_keyboard=True)
        except Exception as e:
            logger.warning(f"Could not send reply keyboard: {e}")

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
            clicker_id = event.sender_id
            if not await is_owner(clicker_id, db):
                await event.reply("❌ **Access Denied**: Only the Middleman Owner can close deals.")
            else:
                await event.reply("⚠️ **Closing Deal**: Please type `/close` or `/close confirm` in the chat to execute closure.")

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
            "💰 **Escrow Crypto Addresses:**\n\n"
            f"• **BTC**: `{btc}`\n"
            f"• **ETH**: `{eth}`\n"
            f"• **LTC**: `{ltc}`"
        )
        await event.respond(wallet_info)

    @client.on(events.NewMessage(pattern=r'^📊 Bot Stats$'))
    async def stats_button_handler(event: events.NewMessage.Event) -> None:
        total, active = await db.get_stats()
        stats_info = (
            "📊 **Escrow Statistics:**\n\n"
            f"• **Active Deals**: {active}\n"
            f"• **Total Closed Deals**: {total}"
        )
        await event.respond(stats_info)
