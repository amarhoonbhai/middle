from telethon import TelegramClient, events
from userbot.services.permissions import owner_command

# In-memory login state for the owner userbot authorization
login_state = {
    "phone": None,
    "phone_code_hash": None,
    "client": None,
    "step": None
}

def get_user_client() -> TelegramClient:
    """Helper to instantiate TelegramClient for userbot with proxy configuration if present."""
    from userbot.config import config
    if config.PROXY_IP and config.PROXY_PORT:
        import socks
        proxy = (socks.SOCKS5, config.PROXY_IP, config.PROXY_PORT, True, config.PROXY_USER, config.PROXY_PASS)
        return TelegramClient("owner_session", config.API_ID, config.API_HASH, proxy=proxy)
    return TelegramClient("owner_session", config.API_ID, config.API_HASH)

def register_settings_handlers(client: TelegramClient, db, is_userbot: bool = False) -> None:
    
    if is_userbot:
        @client.on(events.NewMessage(pattern=r'^\.settings$'))
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

        @client.on(events.NewMessage(pattern=r'^\.setowner(?:\s+(.+))?$'))
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
        return

    @client.on(events.NewMessage)
    @owner_command(db)
    async def login_input_handler(event: events.NewMessage.Event) -> None:
        """Captures prefix-less inputs from the owner when an interactive login step is active."""
        if event.is_group:
            return
            
        step = login_state.get("step")
        if not step:
            return
            
        # Ignore messages starting with command prefix character
        text = (event.text or "").strip()
        if text.startswith((".", "/")):
            return
            
        if step == "awaiting_phone":
            phone = text.replace(" ", "")
            if not phone.startswith("+") and not phone.isdigit():
                await event.respond("❌ **Error**: Phone number should start with `+` and contain country code (e.g., `+1234567890`). Please try again:")
                return
                
            # Clear previous active client if exists to avoid sqlite locks
            old_client = login_state.get("client")
            if old_client:
                try:
                    await old_client.disconnect()
                except Exception:
                    pass
                login_state["client"] = None
                
            await event.respond(f"⏳ **Connecting to Telegram...**\nInitiating session for `{phone}`...")
            user_client = None
            try:
                user_client = get_user_client()
                await user_client.connect()
                
                # Check if already authorized
                if await user_client.is_user_authorized():
                    await event.respond("✅ **Userbot is already authorized and active!**\nThe bot will now use your account to perform group operations.")
                    from userbot.handlers import register_all_handlers
                    register_all_handlers(user_client, db, is_userbot=True)
                    client.user_client = user_client
                    login_state["step"] = None
                    return
                    
                sent_code = await user_client.send_code_request(phone)
                
                login_state["phone"] = phone
                login_state["phone_code_hash"] = sent_code.phone_code_hash
                login_state["client"] = user_client
                login_state["step"] = "awaiting_code"
                
                from telethon import Button
                await event.respond(
                    "📩 **Verification Code Sent!**\n\n"
                    "Please enter the verification code you received (OTP) directly as a message in this chat.",
                    buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
                )
            except Exception as e:
                if user_client:
                    try:
                        await user_client.disconnect()
                    except Exception:
                        pass
                await event.respond(f"❌ **Failed to initiate login**: {e}\n\nPlease try sending your phone number again:")
                
        elif step == "awaiting_code":
            code = text.replace(" ", "")
            if not code.isdigit():
                await event.respond("❌ **Error**: The code must contain digits only. Please try again:")
                return
                
            user_client = login_state["client"]
            phone = login_state["phone"]
            code_hash = login_state["phone_code_hash"]
            
            if not user_client:
                await event.respond("❌ **Error**: Connection lost. Please click the button to try again.")
                login_state["step"] = None
                return
                
            await event.respond("⏳ **Verifying code...**")
            
            try:
                from telethon.errors import SessionPasswordNeededError
                try:
                    await user_client.sign_in(phone, code, phone_code_hash=code_hash)
                    # Success!
                    await event.respond("✅ **Successfully authorized userbot account!**\nThe bot will now use your account to create groups and invite users.")
                    from userbot.handlers import register_all_handlers
                    register_all_handlers(user_client, db, is_userbot=True)
                    client.user_client = user_client
                    
                    # Clear state
                    login_state["phone"] = None
                    login_state["phone_code_hash"] = None
                    login_state["client"] = None
                    login_state["step"] = None
                except SessionPasswordNeededError:
                    login_state["step"] = "awaiting_password"
                    from telethon import Button
                    await event.respond(
                        "🔐 **Two-Step Verification (2FA) is active on this account!**\n\n"
                        "Please enter your 2FA password directly in this chat:",
                        buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
                    )
            except Exception as e:
                await event.respond(f"❌ **Sign-in failed**: {e}\n\nPlease enter the verification code again:")
                
        elif step == "awaiting_password":
            pwd = text
            user_client = login_state["client"]
            if not user_client:
                await event.respond("❌ **Error**: Connection lost. Please try again.")
                login_state["step"] = None
                return
                
            await event.respond("⏳ **Verifying 2FA password...**")
            
            try:
                await user_client.sign_in(password=pwd)
                await event.respond("✅ **Successfully authorized userbot account with 2FA!**\nThe bot will now use your account to create groups and invite users.")
                from userbot.handlers import register_all_handlers
                register_all_handlers(user_client, db, is_userbot=True)
                client.user_client = user_client
                
                # Clear state
                login_state["phone"] = None
                login_state["phone_code_hash"] = None
                login_state["client"] = None
                login_state["step"] = None
            except Exception as e:
                await event.respond(f"❌ **2FA password verification failed**: {e}\n\nPlease enter your 2FA password again:")

    @client.on(events.NewMessage(pattern=r'^\.addaccount(?:\s+(.+))?$'))
    @owner_command(db)
    async def addaccount_command(event: events.NewMessage.Event) -> None:
        """Starts the interactive authorization process to connect the owner's personal userbot account."""
        args = event.pattern_match.group(1)
        
        # Clear previous active client if exists to avoid sqlite locks
        old_client = login_state.get("client")
        if old_client:
            try:
                await old_client.disconnect()
            except Exception:
                pass
            login_state["client"] = None
            
        if not args:
            login_state["step"] = "awaiting_phone"
            from telethon import Button
            await event.respond(
                "🔌 **Connect Owner Userbot Account**\n\n"
                "Please enter your phone number (including country code, e.g. `+1234567890`) directly in this chat:",
                buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
            )
            return
            
        phone = args.strip()
        await event.respond(f"⏳ **Connecting to Telegram...**\nInitiating session for `{phone}`...")
        
        user_client = None
        try:
            user_client = get_user_client()
            await user_client.connect()
            
            # Check if already authorized
            if await user_client.is_user_authorized():
                await event.respond("✅ **Userbot is already authorized and active!**\nThe bot will now use your account to perform group operations.")
                from userbot.handlers import register_all_handlers
                register_all_handlers(user_client, db, is_userbot=True)
                client.user_client = user_client
                login_state["step"] = None
                return
                
            sent_code = await user_client.send_code_request(phone)
            
            login_state["phone"] = phone
            login_state["phone_code_hash"] = sent_code.phone_code_hash
            login_state["client"] = user_client
            login_state["step"] = "awaiting_code"
            
            from telethon import Button
            await event.respond(
                "📩 **Login code sent to Telegram!**\n\n"
                "Please enter the login code you received directly in this chat.",
                buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
            )
        except Exception as e:
            if user_client:
                try:
                    await user_client.disconnect()
                except Exception:
                    pass
            await event.respond(f"❌ **Failed to initiate login**: {e}")

    @client.on(events.NewMessage(pattern=r'^\.code(?:\s+(.+))?$'))
    @owner_command(db)
    async def code_command(event: events.NewMessage.Event) -> None:
        """Handles the verification code entry for userbot authorization."""
        if not login_state["client"] or not login_state["phone"]:
            await event.respond("❌ **Error**: No active login session found. Use `.addaccount <phone_number>` first.")
            return
            
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.code <verification_code>`")
            return
            
        code = args.strip().replace(" ", "")
        user_client = login_state["client"]
        phone = login_state["phone"]
        code_hash = login_state["phone_code_hash"]
        
        await event.respond("⏳ **Verifying code...**")
        
        try:
            from telethon.errors import SessionPasswordNeededError
            try:
                await user_client.sign_in(phone, code, phone_code_hash=code_hash)
                # Success!
                await event.respond("✅ **Successfully authorized userbot account!**\nThe bot will now use your account to create groups and invite users.")
                from userbot.handlers import register_all_handlers
                register_all_handlers(user_client, db, is_userbot=True)
                client.user_client = user_client
                
                # Clear state
                login_state["phone"] = None
                login_state["phone_code_hash"] = None
                login_state["client"] = None
                login_state["step"] = None
            except SessionPasswordNeededError:
                login_state["step"] = "awaiting_password"
                from telethon import Button
                await event.respond(
                    "🔐 **Two-Factor Authentication (2FA) is enabled!**\n\n"
                    "Please reply with your password directly in this chat:",
                    buttons=[Button.inline("❌ Cancel Login", data="btn_cancel_login")]
                )
        except Exception as e:
            await event.respond(f"❌ **Sign-in failed**: {e}")

    @client.on(events.NewMessage(pattern=r'^\.password(?:\s+(.+))?$'))
    @owner_command(db)
    async def password_command(event: events.NewMessage.Event) -> None:
        """Handles the 2FA password entry for userbot authorization."""
        if not login_state["client"] or not login_state["phone"]:
            await event.respond("❌ **Error**: No active login session found. Use `.addaccount <phone_number>` first.")
            return
            
        args = event.pattern_match.group(1)
        if not args:
            await event.respond("❌ **Usage**: `.password <2fa_password>`")
            return
            
        pwd = args.strip()
        user_client = login_state["client"]
        
        await event.respond("⏳ **Verifying 2FA password...**")
        
        try:
            await user_client.sign_in(password=pwd)
            await event.respond("✅ **Successfully authorized userbot account with 2FA!**\nThe bot will now use your account to create groups and invite users.")
            from userbot.handlers import register_all_handlers
            register_all_handlers(user_client, db, is_userbot=True)
            client.user_client = user_client
            
            # Clear state
            login_state["phone"] = None
            login_state["phone_code_hash"] = None
            login_state["client"] = None
            login_state["step"] = None
        except Exception as e:
            await event.respond(f"❌ **2FA verification failed**: {e}")

    @client.on(events.NewMessage(pattern=r'^\.userbot$'))
    @owner_command(db)
    async def userbot_status_command(event: events.NewMessage.Event) -> None:
        """Displays the connection status of the owner's userbot account."""
        user_client = getattr(client, "user_client", None)
        if user_client and await user_client.is_user_authorized():
            me = await user_client.get_me()
            name = f"{getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}".strip()
            username = f"@{me.username}" if me.username else "No Username"
            await event.respond(
                f"👤 **Userbot Connection Status**\n\n"
                f"• **Status**: `Connected` ✅\n"
                f"• **Account**: {name} ({username})\n"
                f"• **ID**: `{me.id}`"
            )
        else:
            await event.respond(
                f"👤 **Userbot Connection Status**\n\n"
                f"• **Status**: `Disconnected` ❌\n"
                f"• **Notice**: The bot is currently operating using standard Bot API limits. Use `.addaccount <phone_number>` or the helper buttons to connect your user account for enhanced group creation."
            )
