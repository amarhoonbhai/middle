import re
from decimal import Decimal
from typing import Optional, Union

def format_currency(amount: Decimal) -> str:
    """Formats a Decimal amount as a currency string (e.g., $1,000.00)."""
    return f"${amount:,.2f}"

def validate_btc_address(address: str) -> bool:
    """
    Validates a BTC address. Supports Legacy (1...), P2SH (3...), and Bech32/SegWit (bc1...).
    Keeps validation flexible to support future/newer valid formats.
    """
    address = address.strip()
    if not address:
        return False
    # Legacy (1...) or P2SH (3...)
    legacy_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    # Bech32 / Native SegWit (bc1q... or bc1p...)
    bech32_pattern = r"^bc1[ac-hj-np-z02-9]{11,71}$"
    
    return bool(re.match(legacy_pattern, address) or re.match(bech32_pattern, address, re.IGNORECASE))

def validate_eth_address(address: str) -> bool:
    """Validates an Ethereum address (0x followed by 40 hex chars)."""
    address = address.strip()
    if not address:
        return False
    eth_pattern = r"^0x[a-fA-F0-9]{40}$"
    return bool(re.match(eth_pattern, address))

def validate_ltc_address(address: str) -> bool:
    """
    Validates a Litecoin address. Supports Legacy (L...), P2SH (M... or 3...),
    and Bech32 (ltc1...).
    """
    address = address.strip()
    if not address:
        return False
    # Legacy (L...) or P2SH (M... or 3...)
    legacy_pattern = r"^[LM3][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    # Bech32 / Native SegWit (ltc1...)
    bech32_pattern = r"^ltc1[ac-hj-np-z02-9]{11,71}$"
    
    return bool(re.match(legacy_pattern, address) or re.match(bech32_pattern, address, re.IGNORECASE))

def parse_decimal(val: str) -> Optional[Decimal]:
    """Safely parses a string into a Decimal, stripping whitespace and currency symbols."""
    clean_val = val.strip().replace("$", "").replace(",", "")
    try:
        return Decimal(clean_val)
    except Exception:
        return None
