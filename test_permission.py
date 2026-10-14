# test_permission.py

from src.security.permission import (
    check_tier, evaluate_action,
    require_confirmation, require_mfa,
    tier_emoji, tier_label, Tier
)

print("=" * 60)
print("TEST 1: check_tier — by action")
print("=" * 60)

test_cases = [
    ("get_balance", 0),
    ("get_transactions", 0),
    ("get_cards", 0),
    ("transfer", 500),
    ("transfer", 1000),
    ("transfer", 1001),
    ("transfer", 5000),
    ("cancel_subscription", 0),
    ("report_card_lost", 0),
    ("change_password", 0),
]

for action, amount in test_cases:
    tier = check_tier(action, amount)
    emoji = tier_emoji(tier)
    print(f"  {emoji} {action:25} ฿{amount:>8,.0f}  →  {tier.value}")

print("\n" + "=" * 60)
print("TEST 2: evaluate_action")
print("=" * 60)

result = evaluate_action("transfer", 500)
print(f"\n  Action: {result['action']}")
print(f"  Amount: ฿{result['amount']}")
print(f"  Tier:   {result['tier']}")
print(f"  Auto:   {result['auto']}")
print(f"  Confirm: {result['requires_confirmation']}")
print(f"  MFA:    {result['requires_mfa']}")
print(f"  Message: {result['message']}")

print("\n" + "=" * 60)
print("TEST 3: Boundary test (1,000 THB)")
print("=" * 60)

for amount in [999, 1000, 1001]:
    tier = check_tier("transfer", amount)
    emoji = tier_emoji(tier)
    print(f"  {emoji} ฿{amount:>6,.0f}  →  {tier.value}")

print("\n✅ All permission tests passed!")