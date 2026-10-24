# src/tools/banking.py
# Mock Banking Tools
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from ..db.session import SessionLocal
from ..db.models import (
    User, Account, Transaction, Card,
    Subscription, Beneficiary,
    TransactionType, TransactionStatus, CardStatus
)


def get_user(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "error", "message": "User not found"}
        return {"status": "success", "data": {
            "id": user.id, "full_name": user.full_name, "phone": user.phone,
            "email": user.email,
            "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None
        }}
    finally:
        db.close()


def get_accounts(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        accounts = db.query(Account).filter(
            Account.user_id == user_id, Account.is_active == True
        ).all()
        return {"status": "success", "count": len(accounts), "data": [
            {"id": a.id, "account_number": a.account_number,
             "account_type": a.account_type.value if a.account_type else None,
             "balance": float(a.balance), "currency": a.currency}
            for a in accounts
        ]}
    finally:
        db.close()


def get_balance(account_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {"status": "error", "message": "Account not found"}
        return {"status": "success", "data": {
            "account_id": account.id, "account_number": account.account_number,
            "balance": float(account.balance), "currency": account.currency
        }}
    finally:
        db.close()


def get_transactions(account_id: int, limit: int = 10) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        txs = db.query(Transaction).filter(
            (Transaction.from_account_id == account_id) |
            (Transaction.to_account_id == account_id)
        ).order_by(Transaction.created_at.desc()).limit(limit).all()
        return {"status": "success", "count": len(txs), "data": [
            {"id": tx.id, "from_account_id": tx.from_account_id,
             "to_account_id": tx.to_account_id, "amount": float(tx.amount),
             "category": tx.category, "note": tx.note,
             "status": tx.status.value if tx.status else None,
             "created_at": tx.created_at.isoformat() if tx.created_at else None}
            for tx in txs
        ]}
    finally:
        db.close()


def transfer(
    from_account_id: int,
    to_account_id: int,
    amount: float,
    note: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        from_acc = db.query(Account).filter(Account.id == from_account_id).first()
        to_acc = db.query(Account).filter(Account.id == to_account_id).first()
        if not from_acc: return {"status": "error", "message": "Source account not found"}
        if not to_acc: return {"status": "error", "message": "Destination account not found"}
        if amount <= 0: return {"status": "error", "message": "Amount must be positive"}
        if float(from_acc.balance) < amount:
            return {"status": "error", "message": "Insufficient balance",
                    "current_balance": float(from_acc.balance)}

        from_acc.balance = float(from_acc.balance) - amount
        to_acc.balance = float(to_acc.balance) + amount

        tx = Transaction(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            note=note,
            category=category or "transfer",
            completed_at=datetime.utcnow()
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return {"status": "success", "data": {
            "transaction_id": tx.id, "amount": amount,
            "from_account": from_acc.account_number,
            "to_account": to_acc.account_number,
            "new_balance": float(from_acc.balance)
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def get_subscriptions(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id, Subscription.is_active == True
        ).all()
        monthly_total = sum(float(s.amount) for s in subs if s.billing_cycle == "monthly")
        return {"status": "success", "count": len(subs), "monthly_total": monthly_total, "data": [
            {"id": s.id, "merchant_name": s.merchant_name, "amount": float(s.amount),
             "billing_cycle": s.billing_cycle,
             "next_billing_date": s.next_billing_date.isoformat() if s.next_billing_date else None}
            for s in subs
        ]}
    finally:
        db.close()


def cancel_subscription(subscription_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub: return {"status": "error", "message": "Subscription not found"}
        if not sub.is_active: return {"status": "error", "message": "Subscription already cancelled"}
        sub.is_active = False
        db.commit()
        return {"status": "success", "data": {
            "subscription_id": sub.id, "merchant_name": sub.merchant_name,
            "message": f"Cancelled {sub.merchant_name}"
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def get_cards(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        cards = db.query(Card).filter(Card.user_id == user_id).all()
        return {"status": "success", "count": len(cards), "data": [
            {"id": c.id,
             "card_number": f"****-****-****-{c.card_number[-4:]}" if c.card_number else None,
             "card_type": c.card_type.value if c.card_type else None,
             "status": c.status.value if c.status else None,
             "daily_limit": float(c.daily_limit) if c.daily_limit else None}
            for c in cards
        ]}
    finally:
        db.close()


def get_card_by_id(card_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        card = db.query(Card).filter(Card.id == card_id).first()
        if not card:
            return {"status": "error", "message": "Card not found"}
        return {"status": "success", "data": {
            "id": card.id,
            "card_number": f"****-****-****-{card.card_number[-4:]}" if card.card_number else "****",
            "card_type": card.card_type.value if card.card_type else None,
            "status": card.status.value if card.status else None,
            "daily_limit": float(card.daily_limit) if card.daily_limit else None
        }}
    finally:
        db.close()

#--------------------------------------------------------------------------------------------
def block_card(card_id: int) -> Dict[str, Any]:
    # Keep digits only, so "1234 5678 9012" or "1234-5678-9012" also work
    digits = re.sub(r"\D", "", str(card_id))
    if len(digits) != 16:
        return {"status": "error", "message": "Please enter 16 digits of the card number"}

    db = SessionLocal()
    try:
        query = db.query(Card).filter(Card.card_id == digits)
        if card_id is not None:  # only match cards owned by the logged-in user
            query = query.filter(Card.card_number == card_id)
        card = query.first()

        if not card:
            return {"status": "error", "message": "Card not found"}
        if card.status == CardStatus.BLOCKED:
            return {"status": "error", "message": "Card already blocked"}

        card.status = CardStatus.BLOCKED
        db.commit()
        return {"status": "success", "data": {
            "card_id": card.id,
            "card_number": f"****-****-{card.card_number[-4:]}",
            "status": "blocked",
            "message": "Card blocked successfully"
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

#--------------------------------------------------------------------------------------------

def unblock_card(card_id: int) -> Dict[str, Any]:
    # Keep digits only, so "1234 5678 9012" or "1234-5678-9012" also work
    digits = re.sub(r"\D", "", str(card_id))
    if len(digits) != 16:
        return {"status": "error", "message": "Please enter 16 digits of the card number"}

    db = SessionLocal()
    try:
        query = db.query(Card).filter(Card.card_number == digits)
        if card_id is not None:  # only match cards owned by the logged-in user
            query = query.filter(Card.card_number == card_id)
        card = query.first()

        if not card:
            return {"status": "error", "message": "Card not found"}
        if card.status != CardStatus.BLOCKED:
            return {"status": "error", "message": "Card is not blocked"}

        card.status = CardStatus.ACTIVE
        db.commit()
        return {"status": "success", "data": {
            "card_id": card.id,
            "card_number": f"****-****-{card.card_number[-4:]}",
            "status": "active",
            "message": "Card unblocked successfully"
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
#--------------------------------------------------------------------------------------------

def cancel_card(card_id: int) -> Dict[str, Any]:
    """Cancel (permanently deactivate) a card"""
    db = SessionLocal()
    try:
        card = db.query(Card).filter(Card.id == card_id).first()
        if not card: return {"status": "error", "message": "Card not found"}
        if card.status == CardStatus.EXPIRED:
            return {"status": "error", "message": "Card already cancelled"}

        card.status = CardStatus.EXPIRED
        db.commit()
        return {"status": "success", "data": {
            "card_id": card.id,
            "card_number": f"****-****-****-{card.card_number[-4:]}" if card.card_number else "****",
            "status": "expired", "message": "Card cancelled successfully"
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def get_beneficiaries(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        bens = db.query(Beneficiary).filter(Beneficiary.user_id == user_id).all()
        return {"status": "success", "count": len(bens), "data": [
            {"id": b.id, "nickname": b.nickname, "full_name": b.full_name,
             "phone": b.phone, "account_number": b.account_number,
             "bank_name": b.bank_name}
            for b in bens
        ]}
    finally:
        db.close()


def find_beneficiary(user_id: int, nickname: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        ben = db.query(Beneficiary).filter(
            Beneficiary.user_id == user_id,
            Beneficiary.nickname.ilike(f"%{nickname}%")
        ).first()
        if not ben:
            return {"status": "error", "message": f"Beneficiary '{nickname}' not found"}
        return {"status": "success", "data": {
            "id": ben.id, "nickname": ben.nickname, "full_name": ben.full_name,
            "account_number": ben.account_number, "bank_name": ben.bank_name
        }}
    finally:
        db.close()