import os
import sys
import logging
import argparse
from telethon import TelegramClient

# Add parent directory to system path to enable robust module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from userbot.config import config
from userbot.database import Database
from userbot.handlers import register_all_handlers

# Determine logging level: only show info logs if starting the daemon
log_level = logging.INFO
if len(sys.argv) > 1 and sys.argv[1] not in ("start",):
    log_level = logging.WARNING

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/userbot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("userbot.main")

def get_telegram_client(session_name: str) -> TelegramClient:
    """Initializes TelegramClient with SOCKS5 Proxy if configured in the environment."""
    if config.PROXY_IP and config.PROXY_PORT:
        import socks
        proxy = (socks.SOCKS5, config.PROXY_IP, config.PROXY_PORT, True, config.PROXY_USER, config.PROXY_PASS)
        logger.info(f"Initializing TelegramClient with SOCKS5 Proxy ({config.PROXY_IP}:{config.PROXY_PORT})...")
        return TelegramClient(session_name, config.API_ID, config.API_HASH, proxy=proxy)
    else:
        return TelegramClient(session_name, config.API_ID, config.API_HASH)

async def interactive_menu(db: Database) -> None:
    """Runs a terminal-based interactive administration menu."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        
        print("\n=========================================")
        print("Telegram Middleman Bot Administration Menu")
        print("=========================================")
        print(f" Status: Token Configured")
        print("-" * 41)
        print(" 1. Start Bot Daemon")
        print(" 2. View Settings & Stats")
        print(" 3. List Registered Deals")
        print(" 4. Configure Fee Percentage")
        print(" 5. Configure Minimum Fee")
        print(" 6. Configure Crypto Addresses (BTC/ETH/LTC)")
        print(" 7. Configure Terms of Service (TOS)")
        print(" 8. Exit")
        print("=========================================")
        
        choice = input("\nSelect an option (1-8): ").strip()
        
        if choice == "1":
            print(f"\n⏳ Starting Telegram Bot Daemon...")
            print("Keep this terminal open while the bot runs.")
            print("To stop the bot, press Ctrl+C.")
            print("-" * 40)
            
            client = get_telegram_client("bot_session")
            register_all_handlers(client, db)
            
            await client.start(bot_token=config.BOT_TOKEN)
            
            me = await client.get_me()
            client.me_id = me.id  # Cache bot ID directly on the client
            await db.update_settings(owner_id=config.OWNER_ID)
            print(f"✅ Bot is active. Logged in as: {me.first_name} (@{me.username})")
            print("Listening for commands on Telegram...")
            
            await client.run_until_disconnected()
            break
            
        elif choice == "2":
            s = await db.get_settings()
            total, active = await db.get_stats()
            print("\n⚙️  CURRENT CONFIGURATION & STATISTICS")
            print("=" * 45)
            print(f"Owner ID:            {s.get('owner_id')}")
            print(f"Fee Percentage:      {s.get('fee_percentage')}%")
            print(f"Minimum Fee:         ${float(s.get('min_fee') or 0):,.2f}")
            print(f"BTC Address:         {s.get('btc_address') or 'Not Configured'}")
            print(f"ETH Address:         {s.get('eth_address') or 'Not Configured'}")
            print(f"LTC Address:         {s.get('ltc_address') or 'Not Configured'}")
            print(f"TOS Configured:      {'Yes' if s.get('tos_text') else 'No'}")
            print(f"Total Deals:         {total}")
            print(f"Active Deals:        {active}")
            print("=" * 45)
            input("\nPress Enter to return to menu...")
            
        elif choice == "3":
            deals = await db.get_all_deals()
            if not deals:
                print("\nNo deals found in SQLite database.")
            else:
                print("\n📂 REGISTERED DEALS LIST")
                print("-" * 108)
                print(f"{'Deal ID':<8} | {'Chat ID':<18} | {'Status':<8} | {'Amount':<11} | {'Fee':<9} | {'Funds Rec.':<10} | {'Created At':<26}")
                print("-" * 108)
                for d in deals:
                    formatted_id = f"#{d['deal_id']:04d}"
                    funds_str = "Yes" if d["funds_received"] else "No"
                    print(f"{formatted_id:<8} | {d['chat_id']:<18} | {d['status']:<8} | ${float(d['amount'] or 0):<10.2f} | ${float(d['fee'] or 0):<8.2f} | {funds_str:<10} | {d['created_at'][:26]}")
                print("-" * 108)
            input("\nPress Enter to return to menu...")
            
        elif choice == "4":
            val = input("\nEnter new default fee percentage (0 to 100): ").strip()
            try:
                pct = float(val)
                if pct < 0 or pct > 100:
                    print("Error: Fee percentage must be between 0 and 100.")
                else:
                    await db.update_settings(fee_percentage=str(pct))
                    print(f"✅ Success: Default fee percentage updated to {pct}%.")
            except ValueError:
                print("Error: Invalid numeric input.")
            input("\nPress Enter to return to menu...")
            
        elif choice == "5":
            val = input("\nEnter new minimum fee amount: ").strip()
            try:
                amount = float(val)
                if amount < 0:
                    print("Error: Minimum fee amount must be non-negative.")
                else:
                    await db.update_settings(min_fee=str(amount))
                    print(f"✅ Success: Minimum fee updated to ${amount:,.2f}.")
            except ValueError:
                print("Error: Invalid numeric input.")
            input("\nPress Enter to return to menu...")
            
        elif choice == "6":
            print("\nSelect Crypto Address to Configure:")
            print("1. BTC")
            print("2. ETH")
            print("3. LTC")
            crypto_choice = input("Select option (1-3): ").strip()
            
            if crypto_choice == "1":
                addr = input("Enter BTC Address: ").strip()
                from userbot.utils.helpers import validate_btc_address
                if not validate_btc_address(addr):
                    print("Error: Invalid BTC address format.")
                else:
                    await db.update_settings(btc_address=addr)
                    print(f"✅ Success: BTC address updated to {addr}.")
            elif crypto_choice == "2":
                addr = input("Enter ETH Address: ").strip()
                from userbot.utils.helpers import validate_eth_address
                if not validate_eth_address(addr):
                    print("Error: Invalid ETH address format.")
                else:
                    await db.update_settings(eth_address=addr)
                    print(f"✅ Success: ETH address updated to {addr}.")
            elif crypto_choice == "3":
                addr = input("Enter LTC Address: ").strip()
                from userbot.utils.helpers import validate_ltc_address
                if not validate_ltc_address(addr):
                    print("Error: Invalid LTC address format.")
                else:
                    await db.update_settings(ltc_address=addr)
                    print(f"✅ Success: LTC address updated to {addr}.")
            else:
                print("Invalid selection.")
            input("\nPress Enter to return to menu...")
            
        elif choice == "7":
            print("\nEnter Terms of Service text below.")
            print("(When done, press Enter and type 'END' on a new line to finish):")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            tos_text = "\n".join(lines).strip()
            if tos_text:
                await db.update_settings(tos_text=tos_text)
                print("✅ Success: Terms of Service updated.")
            else:
                print("Error: TOS content cannot be empty.")
            input("\nPress Enter to return to menu...")
            
        elif choice == "8":
            print("\nExiting. Goodbye!")
            sys.exit(0)
        else:
            print("\nInvalid choice. Choose between 1 and 8.")
            input("\nPress Enter to return to menu...")

async def run_cli() -> None:
    db = Database("userbot.db")
    await db.seed_settings(config.OWNER_ID)
    
    # If no arguments provided, launch the interactive main menu
    if len(sys.argv) == 1:
        await interactive_menu(db)
        return
        
    parser = argparse.ArgumentParser(
        description="Telegram Middleman Bot - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="CLI commands")
    
    subparsers.add_parser("start", help="Start the Telegram bot daemon")
    subparsers.add_parser("settings", help="Show configurations and statistics")
    subparsers.add_parser("stats", help="Show transaction statistics")
    subparsers.add_parser("list-deals", help="List all registered deals")
    
    setfee_parser = subparsers.add_parser("setfee", help="Set the default fee percentage")
    setfee_parser.add_argument("percentage", type=float)
    
    setminfee_parser = subparsers.add_parser("setminfee", help="Set the minimum fee amount")
    setminfee_parser.add_argument("amount", type=float)
    
    setbtc_parser = subparsers.add_parser("setbtc", help="Set the BTC address")
    setbtc_parser.add_argument("address", type=str)
    
    seteth_parser = subparsers.add_parser("seteth", help="Set the ETH address")
    seteth_parser.add_argument("address", type=str)
    
    setltc_parser = subparsers.add_parser("setltc", help="Set the LTC address")
    setltc_parser.add_argument("address", type=str)
    
    settos_parser = subparsers.add_parser("settos", help="Set the TOS text")
    settos_parser.add_argument("text", type=str)
    
    args = parser.parse_args()
    
    if args.command == "start":
        logger.info("Initializing SQLite database...")
        logger.info("Initializing Telegram client (Session: bot_session)...")
        client = get_telegram_client("bot_session")
        register_all_handlers(client, db)
        
        logger.info("Starting Telegram Client login flow...")
        await client.start(bot_token=config.BOT_TOKEN)
        
        me = await client.get_me()
        client.me_id = me.id
        await db.update_settings(owner_id=config.OWNER_ID)
        logger.info(f"✅ Bot successfully authorized! Logged in as: {me.first_name} (@{me.username})")
        logger.info("Running daemon... Press Ctrl+C to stop.")
        
        await client.run_until_disconnected()
        
    elif args.command == "settings":
        s = await db.get_settings()
        total, active = await db.get_stats()
        print(f"Fee: {s.get('fee_percentage')}% | Min Fee: ${float(s.get('min_fee') or 0):.2f}")
        print(f"BTC: {s.get('btc_address') or 'Not Set'}")
        print(f"ETH: {s.get('eth_address') or 'Not Set'}")
        print(f"LTC: {s.get('ltc_address') or 'Not Set'}")
        print(f"Deals - Total: {total} | Active: {active}")
        
    elif args.command == "stats":
        total, active = await db.get_stats()
        print(f"Total: {total} | Active: {active}")
        
    elif args.command == "list-deals":
        deals = await db.get_all_deals()
        for d in deals:
            print(f"Deal #{d['deal_id']:04d} | Chat: {d['chat_id']} | Status: {d['status']} | Amount: {d['amount']}")
            
    elif args.command == "setfee":
        pct = args.percentage
        if 0 <= pct <= 100:
            await db.update_settings(fee_percentage=str(pct))
            print(f"Default fee percentage updated to {pct}%.")
            
    elif args.command == "setminfee":
        amount = args.amount
        if amount >= 0:
            await db.update_settings(min_fee=str(amount))
            print(f"Minimum fee updated to ${amount:,.2f}.")
            
    elif args.command == "setbtc":
        addr = args.address.strip()
        from userbot.utils.helpers import validate_btc_address
        if validate_btc_address(addr):
            await db.update_settings(btc_address=addr)
            print(f"BTC address updated to {addr}.")
            
    elif args.command == "seteth":
        addr = args.address.strip()
        from userbot.utils.helpers import validate_eth_address
        if validate_eth_address(addr):
            await db.update_settings(eth_address=addr)
            print(f"ETH address updated to {addr}.")
            
    elif args.command == "setltc":
        addr = args.address.strip()
        from userbot.utils.helpers import validate_ltc_address
        if validate_ltc_address(addr):
            await db.update_settings(ltc_address=addr)
            print(f"LTC address updated to {addr}.")
            
    elif args.command == "settos":
        text = args.text.strip()
        await db.update_settings(tos_text=text)
        print("Terms of Service text updated.")

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Unhandled bot crash: {e}", exc_info=True)
