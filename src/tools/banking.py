# src/tools/banking.py
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from ..db.session import SessionLocal
from ..db.models import (
    User, Account, Transaction, Card, Subscription, Beneficiary,
    TransactionType, TransactionStatus, CardStatus, ScheduledTransfer, SplitBill, BillParticipant, SavingsGoal
)

def clean_card_number(card_number: str) -> Optional[str]:
    digits = re.sub(r"\D", "", str(card_number))
    if len(digits) != 16:
        return None
    return digits

def find_card(db, digits: str, user_id: Optional[int] = None):
    query = db.query(Card)
    if user_id is not None:
        query = query.filter(Card.user_id == user_id)
    for c in query.all():
        if c.card_number and re.sub(r"\D", "", c.card_number) == digits:
            return c
    return None

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
        
        alert_msg = ""
        try:
            analysis = get_savings_analysis(from_acc.user_id)
            if analysis["status"] == "success":
                tx_category = (category or "transfer").lower()
                for line in analysis["data"]["breakdown"].split("\n"):
                    if tx_category in line.lower() and "OVER BUDGET" in line:
                        alert_msg = (
                            f"\n\n🚨 **BUDGET ALERT** 🚨\n"
                            f"You have overspent on {tx_category.capitalize()}!\n"
                            f"{line.strip()}\n"
                            f"Type 'Show my budget' to see how to fix this."
                        )
                        break
        except Exception as e:
            print(f"⚠️ Bill analysis failed, but transfer succeeded: {e}")

        return {"status": "success", "data": {
            "transaction_id": tx.id, "amount": amount,
            "from_account": from_acc.account_number,
            "to_account": to_acc.account_number,
            "new_balance": float(from_acc.balance),
            "notification": alert_msg
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

def cancel_subscription(subscription_id: int = None, merchant_name: str = None) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if subscription_id:
            sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        elif merchant_name:
            sub = db.query(Subscription).filter(
                Subscription.merchant_name.ilike(f"%{merchant_name}%")
            ).first()
        else:
            return {"status": "error", "message": "No subscription ID or name provided"}

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

def block_card(card_number: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    digits = clean_card_number(card_number)
    if digits is None:
        return {"status": "error", "message": "Please enter all 16 digits of the card number"}

    db = SessionLocal()
    try:
        card = find_card(db, digits, user_id)
        if not card:
            return {"status": "error", "message": "Card not found"}
        if card.status == CardStatus.BLOCKED:
            return {"status": "error", "message": "Card already blocked"}

        card.status = CardStatus.BLOCKED
        db.commit()
        return {"status": "success", "data": {
            "card_id": card.id,
            "card_number": f"****-****-****-{digits[-4:]}",
            "status": "blocked",
            "message": "Card blocked successfully"
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

def unblock_card(card_number: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    digits = clean_card_number(card_number)
    if digits is None:
        return {"status": "error", "message": "Please enter all 16 digits of the card number"}

    db = SessionLocal()
    try:
        card = find_card(db, digits, user_id)
        if not card:
            return {"status": "error", "message": "Card not found"}
        if card.status != CardStatus.BLOCKED:
            return {"status": "error", "message": "Card is not blocked"}

        card.status = CardStatus.ACTIVE
        db.commit()
        return {"status": "success", "data": {
            "card_id": card.id,
            "card_number": f"****-****-****-{digits[-4:]}",
            "status": "active",
            "message": "Card unblocked successfully"
        }}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

def cancel_card(card_id: int) -> Dict[str, Any]:
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
            (Beneficiary.nickname.ilike(f"%{nickname}%")) | 
            (Beneficiary.full_name.ilike(f"%{nickname}%"))
        ).first()
        if not ben:
            return {"status": "error", "message": f"Beneficiary '{nickname}' not found"}
        return {"status": "success", "data": {
            "id": ben.id, "nickname": ben.nickname, "full_name": ben.full_name,
            "account_number": ben.account_number, "bank_name": ben.bank_name
        }}
    finally:
        db.close()

def find_all_beneficiaries(user_id: int, nickname: str) -> List[Dict]:
    db = SessionLocal()
    try:
        bens = db.query(Beneficiary).filter(
            Beneficiary.user_id == user_id,
            (Beneficiary.nickname.ilike(f"%{nickname}%")) | 
            (Beneficiary.full_name.ilike(f"%{nickname}%"))
        ).all()
        return [{"id": b.id, "nickname": b.nickname, "full_name": b.full_name, "phone": b.phone} for b in bens]
    finally:
        db.close()

def schedule_transfer(user_id: int, to_account_id: int, amount: float, date_str: str, note: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        sched_date = datetime.strptime(date_str, "%Y-%m-%d")
        sched = ScheduledTransfer(user_id=user_id, to_account_id=to_account_id, amount=amount, scheduled_date=sched_date, note=note)
        db.add(sched)
        db.commit()
        return {"status": "success", "message": f"Scheduled ฿{amount:,} to {note} on {date_str}"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

def create_split_bill(creator_id: int, total_amount: float, split_type: str, contact_ids: List[int], note: str, percentages: List[float] = None) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        bill = SplitBill(creator_id=creator_id, total_amount=total_amount, split_type=split_type, description=note)
        db.add(bill)
        db.commit()
        
        num_people = len(contact_ids) + 1
        msg_extra = ""
        
        for i, cid in enumerate(contact_ids):
            if split_type == "percentage" and percentages and i < len(percentages):
                pct = percentages[i]
                amount_owed = total_amount * (pct / 100)
                msg_extra += f"\n- Friend {i+1}: {pct}% (฿{amount_owed:,.2f})"
            else:
                amount_owed = total_amount / num_people
                
            p = BillParticipant(bill_id=bill.id, beneficiary_id=cid, amount_owed=amount_owed)
            db.add(p)
            
        db.commit()
        
        if split_type == "equal":
            per_person = total_amount / num_people
            msg_extra = f"Each owes: ฿{per_person:,.2f}"
        elif not msg_extra:
            msg_extra = "Percentage split calculated."

        return {
            "status": "success", 
            "message": f"Created split bill of ฿{total_amount:,} for {note}.\nSent invoices to {len(contact_ids)} friend(s).{msg_extra}"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

# ─── Savings & Budget ───
def get_savings_analysis(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        goal = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id, SavingsGoal.is_active == True).first()
        
        if not goal:
            target = 0.0
            priorities = ["food", "housing", "transportation", "entertainment", "subscription", "card"]
        else:
            target = float(goal.target_amount)
            priorities = [p.strip().lower() for p in goal.priority_ranking.split(",") if p.strip()]

        monthly_income = 50000.0
        spendable = monthly_income - target
        
        weights = {}
        if len(priorities) == 1:
            weights[priorities[0]] = 1.0
        elif len(priorities) == 2:
            weights[priorities[0]] = 0.60
            weights[priorities[1]] = 0.40
        elif len(priorities) == 3:
            weights[priorities[0]] = 0.40
            weights[priorities[1]] = 0.30
            weights[priorities[2]] = 0.30
        else:
            weights[priorities[0]] = 0.30
            weights[priorities[1]] = 0.25
            weights[priorities[2]] = 0.20
            remaining_weight = 1.0 - sum(weights.values())
            remaining_cats = priorities[3:]
            for cat in remaining_cats:
                weights[cat] = remaining_weight / len(remaining_cats) if remaining_cats else 0

        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1)
        
        txs = db.query(Transaction).filter(
            (Transaction.from_account_id == 1) | (Transaction.to_account_id == 1),
            Transaction.created_at >= start_of_month,
            Transaction.transaction_type == TransactionType.PAYMENT or Transaction.transaction_type == TransactionType.TRANSFER
        ).all()

        spent_by_cat = {cat: 0.0 for cat in priorities}
        for tx in txs:
            cat = tx.category.lower() if tx.category else "other"
            if cat in spent_by_cat:
                spent_by_cat[cat] += float(tx.amount)

        report = []
        total_spent = 0
        for cat in priorities:
            budget = spendable * weights.get(cat, 0)
            spent = spent_by_cat.get(cat, 0)
            total_spent += spent
            percent = (spent / budget * 100) if budget > 0 else 0
            
            status = "✅ on track"
            if percent > 100: status = "🚨 OVER BUDGET"
            elif percent > 80: status = "⚠️ nearing limit"

            report.append(f"- {cat.capitalize()}: ฿{spent:,.0f} / ฿{budget:,.0f} ({percent:.0f}%) {status}")

        actual_savings = monthly_income - total_spent
        
        return {
            "status": "success",
            "data": {
                "target": target,
                "income": monthly_income,
                "spent": total_spent,
                "actual_savings": actual_savings,
                "on_track": actual_savings >= target,
                "breakdown": "\n".join(report),
                "priorities": priorities
            }
        }
    finally:
        db.close()

def adjust_category_budget(user_id: int, from_category: str, to_category: str, amount: float) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        goal = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id, SavingsGoal.is_active == True).first()
        if not goal:
            return {"status": "error", "message": "No active savings goal found."}
            
        priorities = [p.strip().lower() for p in goal.priority_ranking.split(",")]
        
        if from_category.lower() not in priorities or to_category.lower() not in priorities:
            return {"status": "error", "message": "Invalid categories."}

        if priorities.index(from_category.lower()) < priorities.index(to_category.lower()):
            return {"status": "error", "message": f"Cannot shift budget. '{from_category}' is a higher priority than '{to_category}'."}
            
        return {
            "status": "success",
            "data": {
                "message": f"Successfully shifted ฿{amount:,.0f} from {from_category.capitalize()} to {to_category.capitalize()} to cover overspending. Your savings goal remains safe!"
            }
        }
    finally:
        db.close()

def get_subscription_dashboard(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id, Subscription.is_active == True
        ).all()
        
        if not subs:
            return {"status": "error", "message": "No active subscriptions found."}

        monthly_total = sum(float(s.amount) for s in subs)
        yearly_total = monthly_total * 12
        
        lines = [f"📊 **Subscription Dashboard**\n"]
        lines.append(f"💵 **Monthly Cost:** ฿{monthly_total:,.0f}")
        lines.append(f"📅 **Yearly Cost:** ฿{yearly_total:,.0f}\n")
        
        alerts = []
        for s in subs:
            usage = s.usage_frequency or 0
            bar = "█" * (usage // 10) + "░" * (10 - (usage // 10))
            
            card_name = "Unknown Card"
            card_info = db.query(Card).filter(Card.account_id == s.account_id).first()
            if card_info:
                card_name = f"****{card_info.card_number[-4:]}"
                
            lines.append(f"• **{s.merchant_name}** (฿{s.amount:,.0f}/mo)")
            lines.append(f"  💳 Paying with: {card_name}")
            lines.append(f"  📈 Usage: [{bar}] {usage}%")
            
            if usage <= 25:
                alerts.append(f"⚠️ **Low Usage Warning:** You rarely use {s.merchant_name} ({usage}%). Consider cancelling to save ฿{s.amount:,.0f}/mo.")
            lines.append("")

        total_balance = sum(float(a.balance) for a in db.query(Account).filter(Account.user_id == user_id).all())
        if total_balance < monthly_total:
            alerts.append(f"🚨 **Insufficient Funds Alert:** Your balance (฿{total_balance:,.0f}) is lower than your monthly subscriptions (฿{monthly_total:,.0f}). You may face overdraft!")

        return {
            "status": "success",
            "data": {
                "breakdown": "\n".join(lines),
                "alerts": "\n\n".join(alerts) if alerts else "",
                "monthly_total": monthly_total,
                "yearly_total": yearly_total
            }
        }
    finally:
        db.close()

# ─── Smart Investment ───
def execute_investment(user_id: int, total_amount: float, plan_details: str) -> Dict[str, Any]:
    """หักเงินจากบัญชีเพื่อลงทุน"""
    db = SessionLocal()
    try:
        acc = db.query(Account).filter(Account.id == 1).first()
        if not acc: 
            return {"status": "error", "message": "Source account not found"}
        if float(acc.balance) < total_amount:
            return {"status": "error", "message": "Insufficient balance for this investment."}

        # หักเงิน
        acc.balance = float(acc.balance) - total_amount
        
        # บันทึก Transaction (สมมติ Account 4 คือ Brokerage Account)
        tx = Transaction(
            from_account_id=1, to_account_id=4, 
            amount=total_amount,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            category="investment",
            note=f"Smart Invest: {plan_details[:50]}...",
            completed_at=datetime.utcnow()
        )
        db.add(tx)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Successfully invested ฿{total_amount:,.2f}!\nNew balance: ฿{acc.balance:,.2f}",
            "new_balance": float(acc.balance)
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()