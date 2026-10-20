# src/agent/loop.py
# Agent Loop — combines all components

import random
from typing import Dict, Any, Optional
from ..intent.parser import parse_intent
from ..security.permission import check_tier, Tier
from ..tools.banking import (
    get_user, get_accounts, get_balance, get_transactions,
    transfer, get_subscriptions, cancel_subscription,
    get_cards, get_beneficiaries, find_beneficiary,
    block_card, cancel_card, get_card_by_id
)

# ═══════════════════════════════════════════
# PENDING STATES
# ═══════════════════════════════════════════

_pending_otps = {}
_pending_suggestions = {}
MAX_OTP_ATTEMPTS = 3


# ═══════════════════════════════════════════
# MAIN ENTRY
# ═══════════════════════════════════════════

def process_message(user_input: str, user_id: int = 1) -> Dict[str, Any]:
    intent = parse_intent(user_input)
    action = intent.get("action", "unknown")
    params = intent.get("params", {})

    if action == "unknown":
        suggestion = params.get("suggestion")
        if suggestion:
            _pending_suggestions[user_id] = {"original": user_input, "suggestion": suggestion}
            return {"reply": f"🤔 I don't understand '{user_input}'.\n\nDid you mean **'{suggestion}'**? [yes/no]",
                    "status": "pending_suggestion", "tier": "green", "requires_confirmation": False}
        return {"reply": f"Sorry, I don't understand '{user_input}' 😅\nType 'help' to see available commands",
                "status": "unknown", "tier": "green"}

    if action == "help":
        return {"reply": _help_text(), "status": "success", "tier": "green"}

    amount = params.get("amount", 0)
    tier = check_tier(action, amount)

    if tier == Tier.RED:
        return _create_otp_challenge(user_id, action, params, intent)

    if tier == Tier.YELLOW:
        summary = _summarize_action(action, params)
        return {"reply": f"⚠️ {summary}\n\nConfirm? [y/n]",
                "status": "pending_confirmation", "tier": "yellow",
                "requires_confirmation": True, "intent": intent}

    return _execute_action(action, params, user_id)


# ═══════════════════════════════════════════
# SUGGESTION HANDLING
# ═══════════════════════════════════════════

def handle_suggestion(user_id: int, answer: str) -> Dict[str, Any]:
    if user_id not in _pending_suggestions:
        return {"reply": "No pending suggestion. Please type your command.", "status": "error", "tier": "green"}
    pending = _pending_suggestions[user_id]
    answer_lower = answer.lower().strip()
    if answer_lower in ["yes", "y", "ใช่", "ok"]:
        del _pending_suggestions[user_id]
        return {"reply": f"✅ OK, interpreting as '{pending['suggestion']}'...",
                "status": "success", "tier": "green", "retry_message": pending["suggestion"]}
    elif answer_lower in ["no", "n", "ไม่"]:
        del _pending_suggestions[user_id]
        return {"reply": "OK. Please type again.", "status": "success", "tier": "green"}
    return {"reply": "Please answer 'yes' or 'no'.", "status": "error", "tier": "green"}


def has_pending_suggestion(user_id: int) -> bool:
    return user_id in _pending_suggestions


# ═══════════════════════════════════════════
# OTP HANDLING
# ═══════════════════════════════════════════

def _create_otp_challenge(user_id: int, action: str, params: Dict, intent: Dict) -> Dict[str, Any]:
    otp = f"{random.randint(100000, 999999)}"
    _pending_otps[user_id] = {"otp": otp, "intent": intent, "attempts": 0}
    summary = _summarize_action(action, params)
    return {"reply": f"🔴 HIGH-RISK ACTION\n{summary}\n\n📱 OTP sent to your phone.\n🔑 Demo OTP: {otp}\n\nPlease enter the 6-digit OTP:",
            "status": "pending_mfa", "tier": "red", "requires_mfa": True, "intent": intent}


def verify_otp(user_id: int, otp: str) -> Dict[str, Any]:
    if user_id not in _pending_otps:
        return {"reply": "❌ No pending OTP. Please start again.", "status": "error", "tier": "red"}
    pending = _pending_otps[user_id]
    pending["attempts"] += 1
    if pending["attempts"] > MAX_OTP_ATTEMPTS:
        del _pending_otps[user_id]
        return {"reply": "🔒 Too many failed attempts. Action cancelled.", "status": "error", "tier": "red"}
    if otp.strip() != pending["otp"]:
        remaining = MAX_OTP_ATTEMPTS - pending["attempts"]
        return {"reply": f"❌ Invalid OTP. {remaining} attempts remaining.", "status": "error", "tier": "red"}
    
    intent = pending["intent"]
    del _pending_otps[user_id]
    action = intent.get("action")
    params = intent.get("params", {})
    
    if action == "transfer":
        result = _execute_transfer(params, user_id, verified=True)
    else:
        result = _execute_action(action, params, user_id)
    result["reply"] = "✅ OTP verified!\n\n" + result["reply"]
    return result


# ═══════════════════════════════════════════
# CONFIRM ACTION
# ═══════════════════════════════════════════

def confirm_action(intent: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    action = intent.get("action")
    params = intent.get("params", {})

    if action == "transfer":
        return _execute_transfer(params, user_id, verified=True)

    if action == "cancel_subscription":
        sub_id = params.get("subscription_id")
        result = cancel_subscription(sub_id)
        if result["status"] == "success":
            return {"reply": f"✅ Cancelled {result['data']['merchant_name']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    if action == "block_card":
        card_id = params.get("card_id", 1)
        result = block_card(card_id)
        if result["status"] == "success":
            return {"reply": f"✅ Card blocked\n💳 {result['data']['card_number']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    if action == "cancel_card":
        card_id = params.get("card_id", 1)
        result = cancel_card(card_id)
        if result["status"] == "success":
            return {"reply": f"✅ Card cancelled\n💳 {result['data']['card_number']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    return {"reply": "❌ Cannot perform this action", "status": "error", "tier": "yellow"}


# ═══════════════════════════════════════════
# EXECUTE ACTION
# ═══════════════════════════════════════════

def _execute_action(action: str, params: Dict, user_id: int) -> Dict[str, Any]:
    try:
        if action == "get_balance":
            result = get_balance(account_id=1)
            if result["status"] == "success":
                balance = int(result["data"]["balance"])
                return {"reply": f"💰 Your savings account balance: ฿{balance:,}",
                        "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_accounts":
            result = get_accounts(user_id)
            if result["status"] == "success":
                lines = ["💰 Your accounts:"]
                for acc in result["data"]:
                    lines.append(f"  • {acc['account_number']}: ฿{int(acc['balance']):,}")
                return {"reply": "\n".join(lines), "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_transactions":
            limit = params.get("limit", 10)
            result = get_transactions(account_id=1, limit=limit)
            if result["status"] == "success":
                # ──── Table format ────
                lines = [f"📊 Recent transactions ({result['count']}):", ""]
                lines.append(f"{'#':<3} {'Amount':>12}  {'Category':<14} {'Recipient':<15}")
                lines.append("─" * 50)
                for i, tx in enumerate(result["data"], 1):
                    amount_str = f"฿{int(tx['amount']):,}"
                    category = (tx['category'] or 'transfer').capitalize()
                    recipient = (tx['note'] or '-')[:14]
                    lines.append(f"{i:<3} {amount_str:>12}  {category:<14} {recipient:<15}")
                return {"reply": "\n".join(lines), "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_cards":
            result = get_cards(user_id)
            if result["status"] == "success":
                lines = [f"💳 Your cards ({result['count']}):", ""]
                for card in result["data"]:
                    lines.append(f"  [{card['id']}] {card['card_number']} ({card['card_type']}) — {card['status']}")
                return {"reply": "\n".join(lines), "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_subscriptions":
            result = get_subscriptions(user_id)
            if result["status"] == "success":
                lines = [f"🔄 Your subscriptions ({result['count']}):", ""]
                for sub in result["data"]:
                    lines.append(f"  [{sub['id']}] {sub['merchant_name']}: ฿{int(sub['amount']):,}/month")
                lines.append(f"\n💵 Monthly total: ฿{int(result['monthly_total']):,}")
                return {"reply": "\n".join(lines), "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_beneficiaries":
            result = get_beneficiaries(user_id)
            if result["status"] == "success":
                lines = ["👥 Your contacts / beneficiaries:"]
                for ben in result["data"]:
                    lines.append(f"  • {ben['nickname']}: {ben['full_name']}")
                    lines.append(f"    📱 {ben['phone']} | 🏦 {ben['bank_name']}")
                return {"reply": "\n".join(lines), "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_user":
            result = get_user(user_id)
            if result["status"] == "success":
                data = result["data"]
                return {"reply": f"👤 Your profile:\n  • Name: {data['full_name']}\n  • Phone: {data['phone']}\n  • Email: {data['email']}",
                        "status": "success", "tier": "green", "data": data}
            return _error_response(result)

        if action == "transfer":
            return _execute_transfer(params, user_id, verified=False)

        if action == "cancel_subscription":
            return _execute_cancel_subscription(params, user_id)

        if action == "block_card":
            return _execute_block_card(params, user_id)

        if action == "cancel_card":
            return _execute_cancel_card(params, user_id)

        if action == "report_card_lost":
            return {"reply": "✅ Card reported as lost.\nA new card will be sent within 7 days.",
                    "status": "success", "tier": "red"}

        return {"reply": f"Sorry, action '{action}' is not supported yet", "status": "unsupported", "tier": "green"}

    except Exception as e:
        return {"reply": f"❌ Error: {str(e)}", "status": "error", "tier": "green"}


# ═══════════════════════════════════════════
# SUB-EXECUTORS
# ═══════════════════════════════════════════

def _execute_transfer(params: Dict, user_id: int, verified: bool = False) -> Dict[str, Any]:
    beneficiary_name = params.get("beneficiary_name", "")
    amount = params.get("amount", 0)
    
    if not beneficiary_name or not amount:
        return {"reply": "⚠️ Please specify recipient and amount\nExample: Transfer 500 to Mom",
                "status": "error", "tier": "yellow"}
                
    ben_result = find_beneficiary(user_id, beneficiary_name)
    if ben_result["status"] != "success":
        return {"reply": f"❌ Beneficiary '{beneficiary_name}' not found", "status": "error", "tier": "yellow"}
    ben = ben_result["data"]

    if verified:
        result = transfer(
            from_account_id=1,
            to_account_id=params.get("to_account_id", 3),
            amount=amount,
            note=beneficiary_name,
            category="transfer"  # <-- เพิ่ม Category ตรงนี้
        )
        if result["status"] == "success":
            data = result["data"]
            return {"reply": f"✅ Transferred ฿{int(data['amount']):,} to {ben['nickname']}\n💰 New balance: ฿{int(data['new_balance']):,}",
                    "status": "success", "tier": "yellow" if amount <= 1000 else "red", "data": data}
        return _error_response(result)

    tier = check_tier("transfer", amount)
    if tier == Tier.RED:
        return _create_otp_challenge(user_id, "transfer", params, {
            "action": "transfer",
            "params": {"beneficiary_name": beneficiary_name, "amount": amount, "to_account_id": 3}
        })
        
    return {"reply": f"⚠️ Transfer ฿{int(amount):,} to {ben['nickname']} ({ben['full_name']})\nConfirm? [y/n]",
            "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
            "intent": {"action": "transfer", "params": {"beneficiary_name": beneficiary_name, "amount": amount, "to_account_id": 3}}}


def _execute_cancel_subscription(params: Dict, user_id: int) -> Dict[str, Any]:
    merchant = params.get("merchant_name", "")
    if not merchant:
        return {"reply": "⚠️ Please specify subscription to cancel\nExample: Cancel Netflix", "status": "error", "tier": "yellow"}
        
    subs_result = get_subscriptions(user_id)
    if subs_result["status"] != "success":
        return _error_response(subs_result)
        
    target = None
    for sub in subs_result["data"]:
        if merchant.lower() in sub["merchant_name"].lower():
            target = sub
            break
            
    if not target:
        return {"reply": f"❌ Subscription '{merchant}' not found", "status": "error", "tier": "yellow"}
        
    return {"reply": f"⚠️ Cancel {target['merchant_name']} (฿{int(target['amount']):,}/month)\nConfirm? [y/n]",
            "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
            "intent": {"action": "cancel_subscription", "params": {"subscription_id": target["id"]}}}


def _execute_block_card(params: Dict, user_id: int) -> Dict[str, Any]:
    cards_result = get_cards(user_id)
    if cards_result["status"] != "success":
        return _error_response(cards_result)
    
    cards = cards_result["data"]
    if not cards:
        return {"reply": "❌ No cards found", "status": "error", "tier": "yellow"}
    
    # ถ้า User ระบุ ID มาแล้ว
    card_id = params.get("card_id")
    if card_id:
        target = next((c for c in cards if c["id"] == card_id), None)
        if not target:
            return {"reply": f"❌ Card #{card_id} not found", "status": "error", "tier": "yellow"}
        return {"reply": f"⚠️ Block card {target['card_number']} ({target['card_type']})\nConfirm? [y/n]",
                "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
                "intent": {"action": "block_card", "params": {"card_id": target["id"]}}}
    
    # ถ้าไม่ระบุ ID -> แสดงรายการให้เลือก
    active_cards = [c for c in cards if c["status"] == "active"]
    if not active_cards:
        return {"reply": "❌ No active cards to block", "status": "error", "tier": "yellow"}
        
    lines = ["💳 Which card do you want to block?\n"]
    for c in active_cards:
        lines.append(f"  [{c['id']}] {c['card_number']} ({c['card_type']})")
    lines.append("\nType the card ID (e.g., 'block card 1')")
    
    return {"reply": "\n".join(lines), "status": "success", "tier": "green"}


def _execute_cancel_card(params: Dict, user_id: int) -> Dict[str, Any]:
    cards_result = get_cards(user_id)
    if cards_result["status"] != "success":
        return _error_response(cards_result)
    
    cards = cards_result["data"]
    if not cards:
        return {"reply": "❌ No cards found", "status": "error", "tier": "yellow"}
    
    # ถ้า User ระบุ ID มาแล้ว
    card_id = params.get("card_id")
    if card_id:
        target = next((c for c in cards if c["id"] == card_id), None)
        if not target:
            return {"reply": f"❌ Card #{card_id} not found", "status": "error", "tier": "yellow"}
        return {"reply": f"⚠️ Cancel card {target['card_number']} ({target['card_type']})?\nConfirm? [y/n]",
                "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
                "intent": {"action": "cancel_card", "params": {"card_id": target["id"]}}}
    
    # ถ้าไม่ระบุ ID -> แสดงรายการให้เลือก
    active_cards = [c for c in cards if c["status"] == "active"]
    if not active_cards:
        return {"reply": "❌ No active cards to cancel", "status": "error", "tier": "yellow"}
        
    lines = ["💳 Which card do you want to cancel?\n"]
    for c in active_cards:
        lines.append(f"  [{c['id']}] {c['card_number']} ({c['card_type']})")
    lines.append("\nType the card ID (e.g., 'cancel card 1')")
    
    return {"reply": "\n".join(lines), "status": "success", "tier": "green"}


# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def _error_response(result: Dict) -> Dict[str, Any]:
    return {"reply": f"❌ {result.get('message', 'An error occurred')}", "status": "error", "tier": "green"}

def _summarize_action(action: str, params: Dict) -> str:
    if action == "transfer":
        return f"Transfer ฿{int(params.get('amount', 0)):,} to {params.get('beneficiary_name', '?')}"
    if action == "cancel_subscription":
        return f"Cancel {params.get('merchant_name', '?')}"
    if action == "block_card":
        return "Block card"
    if action == "cancel_card":
        return "Cancel card"
    if action == "report_card_lost":
        return "Report card lost"
    return f"Perform action: {action}"

def _help_text() -> str:
    return """🤖 Here's what I can do:

💰 Finance:
  • "Check balance"
  • "Show accounts"
  • "Show transactions"

💸 Transfers:
  • "Transfer 500 to Mom"

🔄 Subscriptions:
  • "What am I paying for"
  • "Cancel Netflix"

💳 Cards:
  • "Show cards"
  • "Block card" (confirm)
  • "Cancel card" (confirm)
  • "Report card lost" (OTP)

👤 Other:
  • "My profile"
  • "help"
  • "exit\""""