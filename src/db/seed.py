# src/db/seed.py

from datetime import datetime, timedelta
from .session import SessionLocal
from .models import (
    User, Account, Transaction, Card,
    Subscription, Beneficiary,
    AccountType, TransactionType, TransactionStatus,
    CardType, CardStatus
)


def seed_data():
    db = SessionLocal()
    
    try:
        # Clear old data
        db.query(Beneficiary).delete()
        db.query(Subscription).delete()
        db.query(Card).delete()
        db.query(Transaction).delete()
        db.query(Account).delete()
        db.query(User).delete()
        db.commit()
        print("Cleared old data")
        
        # ─── Users ───
        users = [
            User(
                id=1,
                full_name="Sarah",
                phone="0812345678",
                email="sarah@gmail.com",
                national_id="1234567890123",
                date_of_birth=datetime(1990, 5, 15)
            ),
            User(
                id=2,
                full_name="Sarah",
                phone="0823456789",
                email="sarah@hotmail.com",
                national_id="2345678901234",
                date_of_birth=datetime(1992, 8, 20)
            ),
            User(
                id=3,
                full_name="Sompong Meesuk",
                phone="0834567890",
                email="sompong@example.com",
                national_id="3456789012345",
                date_of_birth=datetime(1988, 12, 3)
            ),
        ]
        db.add_all(users)
        db.commit()
        print(f"Added {len(users)} users")
        
        # ─── Accounts ───
        accounts = [
            Account(
                id=1, user_id=1,
                account_number="001-1-12345-6",
                account_type=AccountType.SAVINGS,
                balance=50000, currency="THB"
            ),
            Account(
                id=2, user_id=1,
                account_number="001-1-12345-7",
                account_type=AccountType.CURRENT,
                balance=15000, currency="THB"
            ),
            Account(
                id=3, user_id=2,
                account_number="002-2-23456-7",
                account_type=AccountType.SAVINGS,
                balance=80000, currency="THB"
            ),
            Account(
                id=4, user_id=3,
                account_number="003-3-34567-8",
                account_type=AccountType.SAVINGS,
                balance=120000, currency="THB"
            ),
        ]
        db.add_all(accounts)
        db.commit()
        print(f"Added {len(accounts)} accounts")
        
        # ─── Beneficiaries ───
        beneficiaries = [
            Beneficiary(
                id=1, user_id=1, nickname="Mom",
                full_name="Mrs. Sommai Jaidee",
                phone="0891111111",
                account_number="004-4-45678-9",
                bank_name="KBank"
            ),
            Beneficiary(
                id=2, user_id=1, nickname="Wife",
                full_name="Ms. Somrak Jaidee",
                phone="0892222222",
                account_number="005-5-56789-0",
                bank_name="SCB"
            ),
        ]
        db.add_all(beneficiaries)
        db.commit()
        print(f"Added {len(beneficiaries)} beneficiaries")
        
                # ─── Transactions ───
        now = datetime.utcnow()
        transactions = [
            Transaction(
                from_account_id=1, to_account_id=3, amount=250,
                transaction_type=TransactionType.TRANSFER,
                status=TransactionStatus.COMPLETED,
                category="food", note="Lunch",
                created_at=now - timedelta(days=5)
            ),
            Transaction(
                from_account_id=1, to_account_id=3, amount=80,
                transaction_type=TransactionType.TRANSFER,
                status=TransactionStatus.COMPLETED,
                category="transportation", note="BTS fare",
                created_at=now - timedelta(days=3)
            ),
            Transaction(
                from_account_id=1, to_account_id=3, amount=5000,
                transaction_type=TransactionType.TRANSFER,
                status=TransactionStatus.COMPLETED,
                category="transfer", note="Transfer to Mom",
                created_at=now - timedelta(days=2)
            ),
            # เพิ่ม Card
            Transaction(
                from_account_id=1, to_account_id=4, amount=1200,
                transaction_type=TransactionType.PAYMENT,
                status=TransactionStatus.COMPLETED,
                category="card", note="Card payment",
                created_at=now - timedelta(hours=12)
            ),
            # เพิ่ม Subscription
            Transaction(
                from_account_id=1, to_account_id=4, amount=419,
                transaction_type=TransactionType.PAYMENT,
                status=TransactionStatus.COMPLETED,
                category="subscription", note="Netflix",
                created_at=now - timedelta(hours=6)
            ),
        ]
        db.add_all(transactions)
        
        db.add_all(transactions)
        db.commit()
        print(f"Added {len(transactions)} transactions")
        
        # ─── Cards ───
        cards = [
            Card(
                id=1, user_id=1, account_id=1,
                card_number="4111-1111-1111-1111",
                card_type=CardType.DEBIT,
                status=CardStatus.ACTIVE,
                daily_limit=20000,
                expires_at=datetime(2027, 12, 31)
            ),
            Card(
                id=2, user_id=1, account_id=2,
                card_number="5555-5555-5555-5555",
                card_type=CardType.CREDIT,
                status=CardStatus.ACTIVE,
                daily_limit=50000,
                expires_at=datetime(2028, 6, 30)
            ),
        ]
        db.add_all(cards)
        db.commit()
        print(f"Added {len(cards)} cards")
        
        # ─── Subscriptions ───
        subscriptions = [
            Subscription(
                user_id=1, account_id=1,
                merchant_name="Netflix", amount=419,
                billing_cycle="monthly",
                next_billing_date=now + timedelta(days=10)
            ),
            Subscription(
                user_id=1, account_id=1,
                merchant_name="Spotify", amount=159,
                billing_cycle="monthly",
                next_billing_date=now + timedelta(days=5)
            ),
            Subscription(
                user_id=1, account_id=1,
                merchant_name="iCloud+", amount=35,
                billing_cycle="monthly",
                next_billing_date=now + timedelta(days=20)
            ),
        ]
        db.add_all(subscriptions)
        db.commit()
        print(f"Added {len(subscriptions)} subscriptions")
        
        print("\nSeed data inserted successfully!")
    
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()