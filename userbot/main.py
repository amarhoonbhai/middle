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

# Determine logging level: only show info/debug logs if starting the daemon
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

async def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Telegram Middleman Userbot - CLI Administration Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start                     Start the Telegram userbot daemon (default)
  settings                  View current configuration settings and statistics
  stats                     Show transaction counts
  list-deals                Print a formatted table of all registered deals
  setfee <percentage>       Configure default MM fee percentage (e.g. 2.5)
  setminfee <amount>        Configure minimum MM fee amount (e.g. 10)
  setbtc <address>          Configure BTC payout wallet address
  seteth <address>          Configure ETH payout wallet address
  setltc <address>          Configure LTC payout wallet address
  settos <text>             Configure Terms of Service message
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")
    
    # 1. start
    subparsers.add_parser("start", help="Start the Telegram userbot daemon (default)")
    
    # 2. settings
    subparsers.add_parser("settings", help="Show configurations and statistics")
    
    # 3. stats
    subparsers.add_parser("stats", help="Show deal count summaries")
    
    # 4. list-deals
    subparsers.add_parser("list-deals", help="List all registered deals from the database")
    
    # 5. setfee
    setfee_parser = subparsers.add_parser("setfee", help="Set the default fee percentage")
    setfee_parser.add_argument("percentage", type=float, help="Fee percentage (0 to 100)")
    
    # 6. setminfee
    setminfee_parser = subparsers.add_parser("setminfee", help="Set the minimum fee amount")
    setminfee_parser.add_argument("amount", type=float, help="Minimum fee amount")
    
    # 7. setbtc
    setbtc_parser = subparsers.add_parser("setbtc", help="Set the BTC wallet address")
    setbtc_parser.add_argument("address", type=str, help="Valid Bitcoin wallet address")
    
    # 8. seteth
    seteth_parser = subparsers.add_parser("seteth", help="Set the ETH wallet address")
    seteth_parser.add_argument("address", type=str, help="Valid Ethereum wallet address")
    
    # 9. setltc
    setltc_parser = subparsers.add_parser("setltc", help="Set the LTC wallet address")
    setltc_parser.add_argument("address", type=str, help="Valid Litecoin wallet address")
    
    # 10. settos
    settos_parser = subparsers.add_parser("settos", help="Set the default Terms of Service text")
    settos_parser.add_argument("text", type=str, help="Terms of Service content")
    
    # If no arguments provided, default to starting the bot
    if len(sys.argv) == 1:
        args = parser.parse_args(["start"])
    else:
        args = parser.parse_args()

    db = Database("userbot.db")
    await db.seed_settings(config.OWNER_ID)
    
    if args.command == "start":
        logger.info("Initializing SQLite database...")
        logger.info("Initializing Telegram client...")
        client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
        register_all_handlers(client, db)
        
        logger.info("Starting Telegram Client login flow...")
        await client.start()
        logger.info("Userbot successfully authorized and running! Press Ctrl+C to stop.")
        await client.run_until_disconnected()
        
    elif args.command == "settings":
        s = await db.get_settings()
        total, active = await db.get_stats()
        print("\n⚙️  CURRENT SETTINGS & STATS")
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
        
    elif args.command == "stats":
        total, active = await db.get_stats()
        print(f"Deals Summary -> Total: {total} | Active: {active}")
        
    elif args.command == "list-deals":
        deals = await db.get_all_deals()
        if not deals:
            print("No deals registered in database.")
            return
        print("\n📂 REGISTERED DEALS LIST")
        print("-" * 108)
        print(f"{'Deal ID':<8} | {'Chat ID':<18} | {'Status':<8} | {'Amount':<11} | {'Fee':<9} | {'Funds Rec.':<10} | {'Created At':<26}")
        print("-" * 108)
        for d in deals:
            formatted_id = f"#{d['deal_id']:04d}"
            funds_str = "Yes" if d["funds_received"] else "No"
            print(f"{formatted_id:<8} | {d['chat_id']:<18} | {d['status']:<8} | ${float(d['amount'] or 0):<10.2f} | ${float(d['fee'] or 0):<8.2f} | {funds_str:<10} | {d['created_at'][:26]}")
        print("-" * 108)
        
    elif args.command == "setfee":
        pct = args.percentage
        if pct < 0 or pct > 100:
            print("Error: Fee percentage must be between 0 and 100.")
            sys.exit(1)
        await db.update_settings(fee_percentage=str(pct))
        print(f"Success: Default fee percentage updated to {pct}%.")
        
    elif args.command == "setminfee":
        amount = args.amount
        if amount < 0:
            print("Error: Minimum fee amount must be positive.")
            sys.exit(1)
        await db.update_settings(min_fee=str(amount))
        print(f"Success: Minimum fee updated to ${amount:,.2f}.")
        
    elif args.command == "setbtc":
        addr = args.address.strip()
        from userbot.utils.helpers import validate_btc_address
        if not validate_btc_address(addr):
            print("Error: Invalid BTC address format.")
            sys.exit(1)
        await db.update_settings(btc_address=addr)
        print(f"Success: BTC address updated to {addr}.")
        
    elif args.command == "seteth":
        addr = args.address.strip()
        from userbot.utils.helpers import validate_eth_address
        if not validate_eth_address(addr):
            print("Error: Invalid ETH address format.")
            sys.exit(1)
        await db.update_settings(eth_address=addr)
        print(f"Success: ETH address updated to {addr}.")
        
    elif args.command == "setltc":
        addr = args.address.strip()
        from userbot.utils.helpers import validate_ltc_address
        if not validate_ltc_address(addr):
            print("Error: Invalid LTC address format.")
            sys.exit(1)
        await db.update_settings(ltc_address=addr)
        print(f"Success: LTC address updated to {addr}.")
        
    elif args.command == "settos":
        text = args.text.strip()
        await db.update_settings(tos_text=text)
        print("Success: Terms of Service text updated.")

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        logger.info("Userbot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Unhandled userbot crash: {e}", exc_info=True)
