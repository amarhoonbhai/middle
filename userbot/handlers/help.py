import os
import logging
from telethon import TelegramClient, events, Button
from telethon.tl.types import ReplyKeyboardMarkup, KeyboardButtonRow, KeyboardButton
from userbot.services.permissions import owner_command, is_owner
from userbot.services import group_service

logger = logging.getLogger(__name__)

def register_help_handlers(client: TelegramClient, db, is_userbot: bool = False) -> None:
    
    if is_userbot:
        @client.on(events.NewMessage(pattern=r'^\.help'))
        @owner_command(db)
        async def help_command(event: events.NewMessage.Event) -> None:
            help_text = (
                "ℹ️ **Spinify Escrow Userbot Commands**\n\n"
                "• `.mm @buyer @seller` - Register daily deal\n"
                "• `.setgroup` - Set current group as daily room\n"
                "• `.close` - Close current deal\n"
                "• `.name <title>` - Rename current group\n"
                "• `.fee <amount>` - Calculate transaction fee\n"
                "• `.rec` - Mark funds as received\n"
                "• `.tos` - View Terms of Service\n"
                "• `.btc` / `.eth` / `.ltc` - View crypto addresses\n"
                "• `.settings` - View current configuration\n"
                "• `.setfee <%>` - Set default fee percentage\n"
                "• `.setminfee <val>` - Set minimum fee amount\n"
                "• `.setbtc <addr>` - Set BTC wallet address\n"
                "• `.seteth <addr>` - Set ETH wallet address\n"
                "• `.setltc <addr>` - Set LTC wallet address\n"
                "• `.settos <text>` - Set Terms of Service text\n"
                "• `.block` - Block user (reply to their message)"
            )
            await event.respond(help_text)
        return

    @client.on(events.NewMessage(pattern=r'^[./]start$'))
    async def start_command(event: events.NewMessage.Event) -> None:
        """Welcomes users in DM with their profile photo and bold name."""
        import io
        sender = await event.get_sender()
        if not sender:
            return

        first_name = getattr(sender, 'first_name', '') or ''
        last_name  = getattr(sender, 'last_name',  '') or ''
        # Bold name using Telegram markdown
        bold_name  = f"**{(first_name + ' ' + last_name).strip() or 'User'}**"

        # Check if the user is the owner
        owner_active = await is_owner(sender.id, db)

        welcome_text = (
            f"👋 Welcome to **Spinify Escrow**\n\n"
            f"Hello {bold_name}!\n"
            f"I am your automated escrow manager.\n\n"
            f"• **ID**: `{sender.id}`\n"
        )
        if owner_active:
            welcome_text += "• **Role**: `Owner` 👑\n\n"
            welcome_text += "Use the buttons below to manage deals, wallets and settings."
        else:
            welcome_text += "\nUse the buttons below to check wallets or terms of service."

        # Build inline buttons — enhanced glass style
        if owner_active:
            buttons = [
                [
                    Button.inline("📜 Terms of Service", data="btn_tos"),
                    Button.inline("ℹ️ Help",             data="btn_help"),
                ],
                [
                    Button.inline("💎 Wallets",    data="btn_crypto"),
                    Button.inline("📊 Stats",       data="btn_stats"),
                ],
                [
                    Button.inline("🔌 Connect Userbot",  data="btn_connect_userbot"),
                    Button.inline("🏠 Set Group",         data="btn_set_escrow_group"),
                ],
                [
                    Button.inline("👑 Manage Admins", data="btn_manage_admins"),
                ]
            ]
            reply_keyboard = ReplyKeyboardMarkup(
                rows=[
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="🧊 Join Group"),
                        KeyboardButton(text="📜 Terms of Service")
                    ]),
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="💎 Escrow Wallets"),
                        KeyboardButton(text="📊 Escrow Stats")
                    ]),
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="🔌 Connect Userbot"),
                        KeyboardButton(text="🏠 Set Escrow Group")
                    ]),
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="👑 Manage Admins"),
                        KeyboardButton(text="⚙️ Settings")
                    ]),
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="ℹ️ Help")
                    ])
                ],
                resize=True
            )
        else:
            buttons = [
                [
                    Button.inline("📜 Terms of Service", data="btn_tos"),
                    Button.inline("ℹ️ Help",             data="btn_help"),
                ],
                [
                    Button.inline("💎 Escrow Wallets", data="btn_crypto")
                ]
            ]
            reply_keyboard = ReplyKeyboardMarkup(
                rows=[
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="🧊 Join Group"),
                        KeyboardButton(text="📜 Terms of Service")
                    ]),
                    KeyboardButtonRow(buttons=[
                        KeyboardButton(text="💎 Escrow Wallets"),
                        KeyboardButton(text="ℹ️ Help")
                    ])
                ],
                resize=True
            )

        # Try to fetch and send profile photo with caption
        photo_sent = False
        try:
            buf = io.BytesIO()
            result = await client.download_profile_photo(sender.id, file=buf)
            if result:
                buf.seek(0)
                await client.send_file(
                    event.chat_id,
                    file=buf,
                    caption=welcome_text,
                    buttons=buttons,
                    parse_mode="md"
                )
                photo_sent = True
        except Exception as pe:
            logger.warning(f"Could not fetch profile photo for {sender.id}: {pe}")

        # Fallback: send text-only welcome if no photo
        if not photo_sent:
            try:
                await event.respond(welcome_text, buttons=buttons)
            except Exception as e:
                logger.error(f"Error sending start welcome: {e}")

        # Send persistent bottom reply keyboard
        try:
            await event.respond("⌨️ Quick menu:", buttons=reply_keyboard)
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
                await event.reply("⚠️ **Closing Deal**: Type `.close` or `.close confirm` in this chat to execute.")
                
        elif data == "btn_connect_userbot":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**: Only the Middleman Owner can connect userbots.")
            else:
                from userbot.handlers.settings import login_state
                login_state["step"] = "awaiting_phone"
                await event.reply(
                    "🔌 **Connect Owner Userbot Account**\n\n"
                    "Please enter your phone number (including country code, e.g. `+1234567890`) directly in this chat:",
                    buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
                )
                
        elif data == "btn_cancel_login":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**.")
            else:
                from userbot.handlers.settings import login_state
                user_client = login_state.get("client")
                if user_client:
                    try:
                        await user_client.disconnect()
                    except Exception:
                        pass
                login_state["phone"] = None
                login_state["phone_code_hash"] = None
                login_state["client"] = None
                login_state["step"] = None
                await event.reply("❌ **Userbot login cancelled.**")
                
        elif data == "btn_manage_admins":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**: Only the Owner can manage admins.")
            else:
                admins = await db.list_admins()
                if admins:
                    lines = [f"• `{a['user_id']}` {('@' + a['username']) if a.get('username') else ''}".strip() for a in admins]
                    admin_list = "\n".join(lines)
                else:
                    admin_list = "_No secondary admins added yet._"
                await event.reply(
                    f"👑 **Admin Management**\n\n"
                    f"**Current Admins**:\n{admin_list}\n\n"
                    f"Choose an action:",
                    buttons=[
                        [Button.inline("➕ Add Admin",    data="btn_add_admin")],
                        [Button.inline("➖ Remove Admin", data="btn_remove_admin")],
                        [Button.inline("❌ Close",        data="btn_close_panel")],
                    ]
                )

        elif data == "btn_add_admin":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**.")
            else:
                from userbot.handlers.settings import login_state
                login_state["step"] = "awaiting_admin_id"
                login_state["admin_action"] = "add"
                await event.reply(
                    "➕ **Add Admin**\n\n"
                    "Send the **Telegram User ID** of the person you want to grant admin rights to.\n"
                    "_(You can get their ID by forwarding their message to @userinfobot)_",
                    buttons=[Button.inline("❌ Cancel", data="btn_cancel_login")]
                )

        elif data == "btn_remove_admin":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**.")
            else:
                from userbot.handlers.settings import login_state
                login_state["step"] = "awaiting_admin_id"
                login_state["admin_action"] = "remove"
                await event.reply(
                    "➖ **Remove Admin**\n\n"
                    "Send the **Telegram User ID** of the admin you want to revoke.",
                    buttons=[Button.inline("❌ Cancel", data="btn_cancel_login")]
                )

        elif data == "btn_close_panel":
            await event.delete()

        elif data == "btn_set_escrow_group":
            if not await is_owner(event.sender_id, db):
                await event.reply("❌ **Access Denied**: Only the Middleman Owner can set escrow groups.")
            else:
                from userbot.handlers.settings import login_state
                login_state["step"] = "awaiting_group"
                await event.reply(
                    "🏠 **Set Escrow Group**\n\n"
                    "Please send the **Group ID** or **invite link** of the group you want to register as today's active escrow room.\n\n"
                    "**Examples**:\n"
                    "`-1001234567890`\n"
                    "`https://t.me/joinchat/...`",
                    buttons=[Button.inline("❌ Cancel", data="btn_cancel_login")]
                )

        elif data == "btn_help":
            owner_active = await is_owner(event.sender_id, db)
            if owner_active:
                help_text = (
                    "ℹ️ **Spinify Escrow — Owner Commands**\n\n"
                    "**Userbot Commands** (run inside group):\n"
                    "• `.mm @buyer @seller` — Register daily deal\n"
                    "• `.setgroup` — Set current group as daily room\n"
                    "• `.setgroup <id>` — Set group by ID (from DM)\n"
                    "• `.close` — Close current deal\n"
                    "• `.name <title>` — Rename current group\n"
                    "• `.setamount <amt>` — Set deal amount\n"
                    "• `.status` — Show deal status\n\n"
                    "**Finance Commands**:\n"
                    "• `.fee <amount>` — Calculate transaction fee\n"
                    "• `.setfee <%>` — Set default fee percentage\n"
                    "• `.setminfee <val>` — Set minimum fee amount\n\n"
                    "**Crypto Wallet Commands**:\n"
                    "• `.btc` / `.eth` / `.ltc` — View crypto addresses\n"
                    "• `.setbtc <addr>` — Set BTC wallet address\n"
                    "• `.seteth <addr>` — Set ETH wallet address\n"
                    "• `.setltc <addr>` — Set LTC wallet address\n\n"
                    "**Other Commands**:\n"
                    "• `.rec` — Mark funds received\n"
                    "• `.tos` — View Terms of Service\n"
                    "• `.settos <text>` — Set Terms of Service text\n"
                    "• `.block` — Block a user (reply to message)\n"
                    "• `.settings` — View current configuration\n"
                    "• `.addaccount` — Connect userbot account"
                )
            else:
                help_text = (
                    "ℹ️ **Spinify Escrow — Help**\n\n"
                    "• 🧊 **Join Group** — Get a link to today's active escrow room\n"
                    "• 🫧 **Terms of Service** — View the escrow terms\n"
                    "• 💎 **Escrow Wallets** — View accepted crypto addresses\n\n"
                    "For deal assistance, contact the Middleman Owner."
                )
            await event.reply(help_text)

    # --- Persistent Reply Keyboard Listeners ---

    @client.on(events.NewMessage(pattern=r'^🧊 Join Group$'))
    async def join_group_button_handler(event: events.NewMessage.Event) -> None:
        """Sends today's daily group invite link to the user so they can join it."""
        settings = await db.get_settings()
        daily_group_id = settings.get("daily_group_id")
        daily_group_date = settings.get("daily_group_date")
        
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if daily_group_id and daily_group_date == today_str:
            try:
                chat_entity = await group_service.resolve_chat_entity(event.client, daily_group_id)
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

    @client.on(events.NewMessage(pattern=r'^💎 Escrow Wallets$'))
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

    @client.on(events.NewMessage(pattern=r'^📊 Escrow Stats$'))
    async def stats_button_handler(event: events.NewMessage.Event) -> None:
        total, active = await db.get_stats()
        stats_info = (
            "📊 **Escrow Statistics**\n\n"
            f"• **Active Deals**: `{active}`\n"
            f"• **Total Closed Deals**: `{total}`"
        )
        await event.respond(stats_info)

    @client.on(events.NewMessage(pattern=r'^🔌 Connect Userbot$'))
    @owner_command(db)
    async def connect_userbot_button_handler(event: events.NewMessage.Event) -> None:
        from userbot.handlers.settings import login_state
        login_state["step"] = "awaiting_phone"
        from telethon import Button
        await event.respond(
            "🔌 **Connect Owner Userbot Account**\n\n"
            "Please enter your phone number (including country code, e.g. `+1234567890`) directly in this chat:",
            buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
        )

    @client.on(events.NewMessage(pattern=r'^🏠 Set Escrow Group$'))
    @owner_command(db)
    async def set_escrow_group_button_handler(event: events.NewMessage.Event) -> None:
        from userbot.handlers.settings import login_state
        login_state["step"] = "awaiting_group"
        from telethon import Button
        await event.respond(
            "🏠 **Set Escrow Group**\n\n"
            "Please send the **Group ID** or **invite link** of the group you want to register as today's active escrow room.\n\n"
            "**Examples**:\n"
            "`-1001234567890`\n"
            "`https://t.me/joinchat/...`",
            buttons=[Button.inline("❌ Cancel", data="btn_cancel_login")]
        )

    @client.on(events.NewMessage(pattern=r'^ℹ️ Help$'))
    async def help_button_handler(event: events.NewMessage.Event) -> None:
        """Shows help text from the bottom reply keyboard Help button."""
        owner_active = await is_owner(event.sender_id, db)
        if owner_active:
            help_text = (
                "ℹ️ **Spinify Escrow — Owner Commands**\n\n"
                "**Userbot Commands** (run inside group):\n"
                "• `.mm @buyer @seller` — Register daily deal\n"
                "• `.setgroup` — Set current group as daily room\n"
                "• `.setgroup <id>` — Set group by ID (from DM)\n"
                "• `.close` — Close current deal\n"
                "• `.name <title>` — Rename current group\n"
                "• `.setamount <amt>` — Set deal amount\n"
                "• `.status` — Show deal status\n\n"
                "**Finance Commands**:\n"
                "• `.fee <amount>` — Calculate transaction fee\n"
                "• `.setfee <%>` — Set default fee percentage\n"
                "• `.setminfee <val>` — Set minimum fee amount\n\n"
                "**Crypto Wallet Commands**:\n"
                "• `.btc` / `.eth` / `.ltc` — View crypto addresses\n"
                "• `.setbtc <addr>` — Set BTC wallet address\n"
                "• `.seteth <addr>` — Set ETH wallet address\n"
                "• `.setltc <addr>` — Set LTC wallet address\n\n"
                "**Other Commands**:\n"
                "• `.rec` — Mark funds received\n"
                "• `.tos` — View Terms of Service\n"
                "• `.settos <text>` — Set Terms of Service text\n"
                "• `.block` — Block a user (reply to message)\n"
                "• `.settings` — View current configuration\n"
                "• `.addaccount` — Connect userbot account"
            )
        else:
            help_text = (
                "ℹ️ **Spinify Escrow — Help**\n\n"
                "• 🧊 **Join Group** — Get a link to today's active escrow room\n"
                "• 📜 **Terms of Service** — View the escrow terms\n"
                "• 💎 **Escrow Wallets** — View accepted crypto addresses\n\n"
                "For deal assistance, contact the Middleman Owner."
            )
        await event.respond(help_text)

    @client.on(events.NewMessage(pattern=r'^👑 Manage Admins$'))
    @owner_command(db)
    async def manage_admins_button_handler(event: events.NewMessage.Event) -> None:
        """Shows admin management panel from bottom keyboard."""
        admins = await db.list_admins()
        if admins:
            lines = [f"• `{a['user_id']}` {('@' + a['username']) if a.get('username') else ''}".strip() for a in admins]
            admin_list = "\n".join(lines)
        else:
            admin_list = "_No secondary admins added yet._"
        from telethon import Button as Btn
        await event.respond(
            f"👑 **Admin Management**\n\n"
            f"**Current Admins**:\n{admin_list}\n\n"
            f"Choose an action:",
            buttons=[
                [Btn.inline("➕ Add Admin",    data="btn_add_admin")],
                [Btn.inline("➖ Remove Admin", data="btn_remove_admin")],
                [Btn.inline("❌ Close",        data="btn_close_panel")],
            ]
        )
