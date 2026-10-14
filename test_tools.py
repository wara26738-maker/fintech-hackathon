# test_tools.py

from src.tools.banking import (
    get_user, get_accounts, get_balance,
    get_transactions, get_subscriptions,
    get_cards, get_beneficiaries, find_beneficiary
)

print("=" * 50)
print("TEST 1: get_user")
print("=" * 50)
result = get_user(1)
print(f"Status: {result['status']}")
print(f"Name: {result['data']['full_name']}")

print("\n" + "=" * 50)
print("TEST 2: get_accounts")
print("=" * 50)
result = get_accounts(1)
print(f"Count: {result['count']}")
for acc in result['data']:
    print(f"  {acc['account_number']}: ฿{acc['balance']:,.2f}")

print("\n" + "=" * 50)
print("TEST 3: get_balance")
print("=" * 50)
result = get_balance(1)
print(f"Balance: ฿{result['data']['balance']:,.2f}")

print("\n" + "=" * 50)
print("TEST 4: get_transactions")
print("=" * 50)
result = get_transactions(1, limit=3)
print(f"Count: {result['count']}")
for tx in result['data']:
    print(f"  ฿{tx['amount']} | {tx['category']} | {tx['note']}")

print("\n" + "=" * 50)
print("TEST 5: get_subscriptions")
print("=" * 50)
result = get_subscriptions(1)
print(f"Count: {result['count']}")
print(f"Monthly: ฿{result['monthly_total']:,.2f}")

print("\n" + "=" * 50)
print("TEST 6: get_cards")
print("=" * 50)
result = get_cards(1)
print(f"Count: {result['count']}")

print("\n" + "=" * 50)
print("TEST 7: get_beneficiaries")
print("=" * 50)
result = get_beneficiaries(1)
print(f"Count: {result['count']}")
for ben in result['data']:
    print(f"  {ben['nickname']}: {ben['full_name']}")

print("\n" + "=" * 50)
print("TEST 8: find_beneficiary")
print("=" * 50)
result = find_beneficiary(1, "Mom")
print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Found: {result['data']['full_name']}")

print("\n✅ All tests passed!")