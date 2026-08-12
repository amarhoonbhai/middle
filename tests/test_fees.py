from decimal import Decimal
from userbot.services.fee_service import calculate_fee

def test_standard_fee_calculation() -> None:
    # 3% fee on 1000 should be 30, total 1030
    amount = Decimal("1000.00")
    pct = Decimal("3.0")
    fee, total = calculate_fee(amount, pct)
    
    assert fee == Decimal("30.00")
    assert total == Decimal("1030.00")

def test_fee_with_minimum_fee() -> None:
    # 3% on 100 is 3, but min fee is 10, so fee should be 10, total 110
    amount = Decimal("100.00")
    pct = Decimal("3.0")
    min_fee = Decimal("10.00")
    fee, total = calculate_fee(amount, pct, min_fee)
    
    assert fee == Decimal("10.00")
    assert total == Decimal("110.00")

def test_fee_rounding_half_up() -> None:
    # 3% on 33.33 is 0.9999, which rounds to 1.00
    amount = Decimal("33.33")
    pct = Decimal("3.0")
    fee, total = calculate_fee(amount, pct)
    
    assert fee == Decimal("1.00")
    assert total == Decimal("34.33")
    
    # 3% on 10.15 is 0.3045, which rounds to 0.30
    amount = Decimal("10.15")
    fee, total = calculate_fee(amount, pct)
    assert fee == Decimal("0.30")
    assert total == Decimal("10.45")
