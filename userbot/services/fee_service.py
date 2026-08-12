from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple

def calculate_fee(amount: Decimal, fee_percentage: Decimal, min_fee: Decimal = Decimal('0.00')) -> Tuple[Decimal, Decimal]:
    """
    Calculates the middleman fee based on the transaction amount.
    
    Calculates the fee as: max(amount * (fee_percentage / 100), min_fee).
    Returns a tuple of (fee, total) where total = amount + fee.
    All calculations are rounded to 2 decimal places using ROUND_HALF_UP to avoid floating point issues.
    """
    # Calculate fee
    fee = amount * (fee_percentage / Decimal('100'))
    if fee < min_fee:
        fee = min_fee
        
    # Quantize to two decimal places
    fee = fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = (amount + fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return fee, total
