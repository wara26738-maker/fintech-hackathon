# src/tools/banking.py
# Mock Banking Tools — ฟังก์ชันที่ AI Agent เรียกใช้

from datetime import datetime
from typing import Optional, List, Dict, Any
from ..db.session import SessionLocal
from ..db.models import (
    User, Account, Transaction, Card,
    Subscription, Beneficiary,
    TransactionType, TransactionStatus, CardStatus
)


# ═══════════════════════════════════════════
# USER
# ═══════════════════════════════════════════

def get_user(user_id: int) -> Dict[str, Any]:
    """ดูข้อมูลผู้ใช้"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "error", "message": "User not found"}
        
        return {
            "status": "success",
            "data": {
                "id": user.id,
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None
            }
        }
    finally:
        db.close()


# ═══════════════════════════════════════════
# ACCOUNTS
# ═══════════════════════════════════════════

def get_accounts(user_id: int) -> Dict[str, Any]:
    """ดูบัญชีทั้งหมดของผู้ใช้"""
    db = SessionLocal()
    try:
        accounts = db.query(Account).filter(
            Account.user_id == user_id,
            Account.is_active == True
        ).all()
        
        return {
            "status": "success",
            "count": len(accounts),
            "data": [
                {
                    "id": acc.id,
                    "account_number": acc.account_number,
                    "account_type": acc.account_type.value if acc.account_type else None,
                    "balance": float(acc.balance),
                    "currency": acc.currency
                }
                for acc in accounts
            ]
        }
    finally:
        db.close()


def get_balance(account_id: int) -> Dict[str, Any]:
    """ดูยอดเงินในบัญชี"""
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {"status": "error", "message": "Account not found"}
        
        return {
            "status": "success",
            "data": {
                "account_id": account.id,
                "account_number": account.account_number,
                "balance": float(account.balance),
                "currency": account.currency
            }
        }
    finally:
        db.close()


# ═══════════════════════════════════════════
# TRANSACTIONS
# ═══════════════════════════════════════════

def get_transactions(account_id: int, limit: int = 10) -> Dict[str, Any]:
    """ดูธุรกรรมของบัญชี"""
    db = SessionLocal()
    try:
        txs = db.query(Transaction).filter(
            (Transaction.from_account_id == account_id) |
            (Transaction.to_account_id == account_id)
        ).order_by(Transaction.created_at.desc()).limit(limit).all()
        
        return {
            "status": "success",
            "count": len(txs),
            "data": [
                {
                    "id": tx.id,
                    "from_account_id": tx.from_account_id,
                    "to_account_id": tx.to_account_id,
                    "amount": float(tx.amount),
                    "category": tx.category,
                    "note": tx.note,
                    "status": tx.status.value if tx.status else None,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None
                }
                for tx in txs
            ]
        }
    finally:
        db.close()


def transfer(
    from_account_id: int,
    to_account_id: int,
    amount: float,
    note: Optional[str] = None
) -> Dict[str, Any]:
    """โอนเงินจากบัญชีหนึ่งไปอีกบัญชี"""
    db = SessionLocal()
    try:
        from_acc = db.query(Account).filter(Account.id == from_account_id).first()
        to_acc = db.query(Account).filter(Account.id == to_account_id).first()
        
        if not from_acc:
            return {"status": "error", "message": "Source account not found"}
        if not to_acc:
            return {"status": "error", "message": "Destination account not found"}
        if amount <= 0:
            return {"status": "error", "message": "Amount must be positive"}
        if float(from_acc.balance) < amount:
            return {
                "status": "error",
                "message": "Insufficient balance",
                "current_balance": float(from_acc.balance)
            }
        
        # Execute transfer
        from_acc.balance = float(from_acc.balance) - amount
        to_acc.balance = float(to_acc.balance) + amount
        
        tx = Transaction(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            note=note,
            completed_at=datetime.utcnow()
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        
        return {
            "status": "success",
            "data": {
                "transaction_id": tx.id,
                "amount": amount,
                "from_account": from_acc.account_number,
                "to_account": to_acc.account_number,
                "new_balance": float(from_acc.balance)
            }
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ═══════════════════════════════════════════
# SUBSCRIPTIONS
# ═══════════════════════════════════════════

def get_subscriptions(user_id: int) -> Dict[str, Any]:
    """ดู subscription ทั้งหมด"""
    db = SessionLocal()
    try:
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.is_active == True
        ).all()
        
        monthly_total = sum(
            float(s.amount) for s in subs if s.billing_cycle == "monthly"
        )
        
        return {
            "status": "success",
            "count": len(subs),
            "monthly_total": monthly_total,
            "data": [
                {
                    "id": s.id,
                    "merchant_name": s.merchant_name,
                    "amount": float(s.amount),
                    "billing_cycle": s.billing_cycle,
                    "next_billing_date": s.next_billing_date.isoformat() if s.next_billing_date else None
                }
                for s in subs
            ]
        }
    finally:
        db.close()


def cancel_subscription(subscription_id: int) -> Dict[str, Any]:
    """ยกเลิก subscription"""
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            return {"status": "error", "message": "Subscription not found"}
        if not sub.is_active:
            return {"status": "error", "message": "Subscription already cancelled"}
        
        sub.is_active = False
        db.commit()
        
        return {
            "status": "success",
            "data": {
                "subscription_id": sub.id,
                "merchant_name": sub.merchant_name,
                "message": f"Cancelled {sub.merchant_name}"
            }
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ═══════════════════════════════════════════
# CARDS
# ═══════════════════════════════════════════

def get_cards(user_id: int) -> Dict[str, Any]:
    """ดูบัตรทั้งหมด"""
    db = SessionLocal()
    try:
        cards = db.query(Card).filter(Card.user_id == user_id).all()
        
        return {
            "status": "success",
            "count": len(cards),
            "data": [
                {
                    "id": c.id,
                    "card_number": f"****-****-****-{c.card_number[-4:]}" if c.card_number else None,
                    "card_type": c.card_type.value if c.card_type else None,
                    "status": c.status.value if c.status else None,
                    "daily_limit": float(c.daily_limit) if c.daily_limit else None
                }
                for c in cards
            ]
        }
    finally:
        db.close()


# ═══════════════════════════════════════════
# BENEFICIARIES
# ═══════════════════════════════════════════

def get_beneficiaries(user_id: int) -> Dict[str, Any]:
    """ดูผู้รับโอนที่บันทึกไว้"""
    db = SessionLocal()
    try:
        bens = db.query(Beneficiary).filter(Beneficiary.user_id == user_id).all()
        
        return {
            "status": "success",
            "count": len(bens),
            "data": [
                {
                    "id": b.id,
                    "nickname": b.nickname,
                    "full_name": b.full_name,
                    "phone": b.phone,
                    "account_number": b.account_number,
                    "bank_name": b.bank_name
                }
                for b in bens
            ]
        }
    finally:
        db.close()


def find_beneficiary(user_id: int, nickname: str) -> Dict[str, Any]:
    """หาผู้รับโอนจากชื่อเล่น"""
    db = SessionLocal()
    try:
        ben = db.query(Beneficiary).filter(
            Beneficiary.user_id == user_id,
            Beneficiary.nickname.ilike(f"%{nickname}%")
        ).first()
        
        if not ben:
            return {"status": "error", "message": f"Beneficiary '{nickname}' not found"}
        
        return {
            "status": "success",
            "data": {
                "id": ben.id,
                "nickname": ben.nickname,
                "full_name": ben.full_name,
                "account_number": ben.account_number,
                "bank_name": ben.bank_name
            }
        }
    finally:
        db.close()