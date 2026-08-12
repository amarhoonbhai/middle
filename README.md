# Telegram Middleman Userbot

A production-ready Telegram userbot built using **Python 3.11+**, **Telethon**, and **SQLite**. Designed for escrow/middleman operations, allowing you to manage deals, calculate fees, track transaction stages, block malicious users, and configure payment addresses directly from your Telegram account using commands starting with a dot (`.`).

---

## Features

- 🛠️ **Group Creation (`.mm`)**: Automatically spawns legacy group chats, registers participants, sends and pins Terms of Service, and posts welcome instructions.
- 🔒 **Owner Protected**: Commands only respond to the authorized owner Telegram ID.
- ⚙️ **Configurable SQLite Settings**: Manage BTC, ETH, and LTC wallet addresses, terms of service text, and fee structures in a persistent SQLite database.
- 🔢 **Sequential Deal IDs**: Automatically formats deals as `#0001`, `#0002`, etc., storing comprehensive state transitions.
- 💰 **Decimal Fee Calculation**: Uses Python's `Decimal` module to prevent floating-point calculation errors in financial math.
- 🚫 **Moderation & Cleanup**: Blocks target users and clears message histories on both sides for privacy (where supported).
- 🧹 **Outgoing Command Deletion**: Clean execution that optionally deletes the typed trigger command message once finished.

---

## Table of Contents
1. [Security Warnings](#security-warnings)
2. [Telegram API Credentials Setup](#telegram-api-credentials-setup)
3. [Windows Setup](#windows-setup)
4. [Ubuntu/Linux Setup](#ubuntulinux-setup)
5. [Configuration (.env)](#configuration-env)
6. [Command Documentation](#command-documentation)
7. [Database & Storage](#database--storage)
8. [Troubleshooting & API Limitations](#troubleshooting--api-limitations)

---

## Security Warnings
> [!CAUTION]
> - **Never share your `API_HASH` or session files** (`*.session`, `*.session-journal`). They grant absolute access to your Telegram account.
> - **Never hardcode credentials or wallet addresses** in source code. Use the database settings commands (`.setbtc`, `.seteth`, etc.) and the `.env` file instead.
> - Ensure your `.env` and `*.db` files are kept private and are not committed to source control (they are ignored by default in `.gitignore`).

---

## Telegram API Credentials Setup
To use a userbot, you need to acquire Telegram API credentials for your account:
1. Go to [https://my.telegram.org](https://my.telegram.org) and log in with your phone number.
2. Navigate to **API development tools**.
3. Create a new application (the title and short name do not matter).
4. Note down the **App api_id** (integer) and **App api_hash** (32-character hexadecimal string).

---

## Windows Setup

1. **Clone/Open Workspace**: Ensure you are in the project folder.
2. **Create Virtual Environment**:
   ```cmd
   python -m venv .venv
   ```
3. **Activate Virtual Environment**:
   ```cmd
   .venv\Scripts\activate
   ```
4. **Install Dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
5. **Configure Environment**:
   Copy `.env.example` to `.env` and fill in your credentials:
   ```cmd
   copy .env.example .env
   ```
6. **First Run & Login**:
   ```cmd
   python userbot/main.py
   ```
   *Follow the prompts in the terminal to enter your phone number, the verification code sent to your Telegram account, and your 2FA password (if enabled).*

---

## Ubuntu/Linux Setup

1. **Create Virtual Environment**:
   ```bash
   python3 -m venv .venv
   ```
2. **Activate Virtual Environment**:
   ```bash
   source .venv/bin/activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. **Configure Environment**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
5. **First Run & Login**:
   ```bash
   python userbot/main.py
   ```
   *Authorize the userbot in the terminal when prompted.*

---

## Configuration (.env)

The `.env` file supports the following parameters:
- `API_ID`: Your Telegram app `api_id` (obtained from my.telegram.org).
- `API_HASH`: Your Telegram app `api_hash`.
- `SESSION_NAME`: The name of the session file. Default is `userbot_session`.
- `OWNER_ID`: Your numeric Telegram User ID. You can find this using bots like `@userinfobot` or running the bot settings command.
- `DELETE_COMMANDS`: `True`/`False` (default `True`). If enabled, the userbot automatically deletes your trigger commands (e.g. `.fee 100`) after execution to keep chats clean.

---

## Command Documentation

All commands must be prefixed with a dot (`.`).

### MM Operations
- `.mm <user1> <user2>`
  Creates a new MM group chat, adds the buyer/seller, pins the Terms of Service, and registers the deal as active.
  *Example: `.mm @username1 @username2` or `.mm 123456789 987654321`*
- `.close`
  Initiates closure for the current MM group. Prompts to run `.close confirm` to verify.
- `.close confirm`
  Safely closes the deal in the database and leaves the group. Must be run within 60 seconds of `.close`.
- `.name <new_name>`
  Renames the current group. Only works inside registered active deal chats.
- `.fee <amount>`
  Calculates the middleman fee and transaction total using parameters in the settings database.
  *Example: `.fee 1500` -> calculates fee and total for $1,500.00.*
- `.rec`
  Confirms that funds have been received for the deal. Updates the deal's `funds_received` status in the database.
- `.tos`
  Sends the currently configured Terms of Service.

### Crypto Address Commands
- `.btc` / `.eth` / `.ltc`
  Sends the configured BTC, ETH, or LTC wallet address in a copy-friendly markdown format.

### Owner Settings
- `.setfee <percentage>`
  Sets the default middleman fee percentage (e.g., `.setfee 3` for 3%).
- `.setminfee <amount>`
  Sets the minimum fee charged for any deal (e.g., `.setminfee 10` for $10.00).
- `.setbtc <address>` / `.seteth <address>` / `.setltc <address>`
  Sets and validates the respective cryptocurrency address.
- `.settos <text>`
  Configures the Terms of Service text. You can also **reply to a long message** with `.settos` to set multiline TOS.
- `.settings`
  Displays the current bot configurations and deal statistics (fees, configured wallets, and deal counts).

### Moderation
- `.block`
  Reply to a user's message in a chat and run `.block`. The userbot will block the target on Telegram, record the block in SQLite, and clear the DM history with them for both sides.

---

## Database & Storage

The bot uses an SQLite database named `userbot.db` in the project root:
- It initializes automatically on first startup.
- Safe schema upgrades run without deleting historical data.
- **Deals history is kept permanently**, even if you leave or delete the Telegram group.

---

## Troubleshooting & API Limitations

- **FloodWaitError**: Telegram limits rapid actions (like creating groups or adding users). If you run into this, wait for the seconds specified in the error before triggering group creations again.
- **UserPrivacyRestrictedError**: If a participant restricts who can add them to groups in their Telegram privacy settings, the bot cannot add them. The bot handles this gracefully, creating the group with the other participant and warning you in the chat so you can send them a manual invite link.
- **Userbot Stopped**: To stop the userbot process, press `Ctrl+C` in the terminal.
