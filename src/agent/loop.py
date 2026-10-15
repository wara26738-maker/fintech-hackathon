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
    block_card
)


# ═══════════════════════════════════════════
# PENDING STATES
# ═══════════════════════════════════════════

_pending_otps = {}           # {user_id: {"otp": "123456", "intent": {...}, "attempts": 0}}
_pending_suggestions = {}    # {user_id: {"original": "...", "suggestion": "..."}}
MAX_OTP_ATTEMPTS = 3


# ═══════════════════════════════════════════
# MAIN ENTRY
# ═══════════════════════════════════════════

def process_message(user_input: str, user_id: int = 1) -> Dict[str, Any]:
    """Process user message → return response"""
    
    intent = parse_intent(user_input)
    action = intent.get("action", "unknown")
    params = intent.get("params", {})
    
    # ─── Unknown → check suggestion ───
    if action == "unknown":
        suggestion = params.get("suggestion")
        
        if suggestion:
            _pending_suggestions[user_id] = {
                "original": user_input,
                "suggestion": suggestion
            }
            
            return {
                "reply": f"🤔 I don't understand '{user_input}'.\n\n"
                         f"Did you mean **'{suggestion}'**? [yes/no]",
                "status": "pending_suggestion",
                "tier": "green",
                "requires_confirmation": False
            }
        
        return {
            "reply": f"Sorry, I don't understand '{user_input}' 😅\n"
                     f"Type 'help' to see available commands",
            "status": "unknown",
            "tier": "green"
        }
    
    # ─── Help ───
    if action == "help":
        return {
            "reply": _help_text(),
            "status": "success",
            "tier": "green"
        }
    
    # ─── Check tier ───
    amount = params.get("amount", 0)
    tier = check_tier(action, amount)
    
    # ─── Red → OTP ───
    if tier == Tier.RED:
        return _create_otp_challenge(user_id, action, params, intent)
    
    # ─── Yellow → confirm ───
    if tier == Tier.YELLOW:
        summary = _summarize_action(action, params)
        return {
            "reply": f"⚠️ {summary}\n\nConfirm? [y/n]",
            "status": "pending_confirmation",
            "tier": "yellow",
            "requires_confirmation": True,
            "intent": intent
        }
    
    # ─── Green → execute ───
    return _execute_action(action, params, user_id)


# ═══════════════════════════════════════════
# SUGGESTION HANDLING
# ═══════════════════════════════════════════

def handle_suggestion(user_id: int, answer: str) -> Dict[str, Any]:
    """Handle user response to spell suggestion"""
    if user_id not in _pending_suggestions:
        return {
            "reply": "No pending suggestion. Please type your command.",
            "status": "error",
            "tier": "green"
        }
    
    pending = _pending_suggestions[user_id]
    answer_lower = answer.lower().strip()
    
    if answer_lower in ["yes", "y", "ใช่", "yes please", "ok"]:
        del _pending_suggestions[user_id]
        suggestion = pending["suggestion"]
        original = pending["original"]
        
        # แทนที่คำที่พิมพ์ผิดด้วยคำที่แนะนำ
        # ตัวอย่าง: "tranfers 500 to mom" → "transfer 500 to mom"
        # หาคำที่ใกล้เคียงแล้วแทน
        new_text = original
        
        # หา keyword ในข้อความ
        import re as _re
        from ..intent.parser import KEYWORDS, find_similar_word
        
        words = _re.findall(r'[a-zA-Zก-๙]+', original)
        for word in words:
            if len(word) >= 3:
                sim = find_similar_word(word)
                if sim == suggestion:
                    new_text = _re.sub(r'\b' + _re.escape(word) + r'\b', suggestion, new_text, count=1)
                    break
        
        return {
            "reply": f"✅ OK, interpreting as '{new_text}'...\n\n" + 
                     f"Processing...",
            "status": "success",
            "tier": "green",
            "retry_message": new_text
        }
    
    elif answer_lower in ["no", "n", "ไม่", "nope"]:
        del _pending_suggestions[user_id]
        return {
            "reply": "OK. Please type again.",
            "status": "success",
            "tier": "green"
        }
    
    return {
        "reply": "Please answer 'yes' or 'no'.",
        "status": "error",
        "tier": "green"
    }


def has_pending_suggestion(user_id: int) -> bool:
    return user_id in _pending_suggestions


# ═══════════════════════════════════════════
# OTP HANDLING
# ═══════════════════════════════════════════

def _create_otp_challenge(user_id: int, action: str, params: Dict, intent: Dict) -> Dict[str, Any]:
    otp = f"{random.randint(100000, 999999)}"
    
    _pending_otps[user_id] = {
        "otp": otp,
        "intent": intent,
        "attempts": 0
    }
    
    summary = _summarize_action(action, params)
    
    return {
        "reply": f"🔴 HIGH-RISK ACTION\n"
                 f"{summary}\n\n"
                 f"📱 OTP sent to your phone.\n"
                 f"🔑 Demo OTP: {otp}\n\n"
                 f"Please enter the 6-digit OTP:",
        "status": "pending_mfa",
        "tier": "red",
        "requires_mfa": True,
        "intent": intent
    }


def verify_otp(user_id: int, otp: str) -> Dict[str, Any]:
    if user_id not in _pending_otps:
        return {
            "reply": "❌ No pending OTP. Please start again.",
            "status": "error",
            "tier": "red"
        }
    
    pending = _pending_otps[user_id]
    pending["attempts"] += 1
    
    if pending["attempts"] > MAX_OTP_ATTEMPTS:
        del _pending_otps[user_id]
        return {
            "reply": "🔒 Too many failed attempts. Action cancelled.",
            "status": "error",
            "tier": "red"
        }
    
    if otp.strip() != pending["otp"]:
        remaining = MAX_OTP_ATTEMPTS - pending["attempts"]
        return {
            "reply": f"❌ Invalid OTP. {remaining} attempts remaining.",
            "status": "error",
            "tier": "red"
        }
    
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
# CONFIRM
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
            return {
                "reply": f"✅ Cancelled {result['data']['merchant_name']}",
                "status": "success",
                "tier": "yellow",
                "data": result["data"]
            }
        return _error_response(result)
    
    if action == "block_card":
        card_id = params.get("card_id", 1)  # default first card
        result = block_card(card_id)
        
        if result["status"] == "success":
            return {
                "reply": f"✅ Card blocked\n"
                         f"💳 {result['data']['card_number']}",
                "status": "success",
                "tier": "yellow",
                "data": result["data"]
            }
        return _error_response(result)
    
    return {
        "reply": "❌ Cannot perform this action",
        "status": "error",
        "tier": "yellow"
    }


# ═══════════════════════════════════════════
# EXECUTE ACTION
# ═══════════════════════════════════════════

def _execute_action(action: str, params: Dict, user_id: int) -> Dict[str, Any]:
    try:
        # ─── get_balance ───
        if action == "get_balance":
            result = get_balance(account_id=1)
            if result["status"] == "success":
                balance = int(result["data"]["balance"])
                return {
                    "reply": f"💰 Your savings account balance: ฿{balance:,}",
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_accounts ───
        if action == "get_accounts":
            result = get_accounts(user_id)
            if result["status"] == "success":
                lines = ["💰 Your accounts:"]
                for acc in result["data"]:
                    lines.append(f"  • {acc['account_number']}: ฿{int(acc['balance']):,}")
                return {
                    "reply": "\n".join(lines),
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_transactions ───
        if action == "get_transactions":
            limit = params.get("limit", 5)
            result = get_transactions(account_id=1, limit=limit)
            if result["status"] == "success":
                lines = [f"📊 Recent transactions ({result['count']}):"]
                for tx in result["data"]:
                    lines.append(f"  • ฿{int(tx['amount']):,} | {tx['category']} | {tx['note']}")
                return {
                    "reply": "\n".join(lines),
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_cards ───
        if action == "get_cards":
            result = get_cards(user_id)
            if result["status"] == "success":
                lines = [f"💳 Your cards ({result['count']}):"]
                for card in result["data"]:
                    lines.append(f"  • {card['card_number']} ({card['card_type']}) — {card['status']}")
                return {
                    "reply": "\n".join(lines),
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_subscriptions ───
        if action == "get_subscriptions":
            result = get_subscriptions(user_id)
            if result["status"] == "success":
                lines = [f"🔄 Your subscriptions ({result['count']}):"]
                for sub in result["data"]:
                    lines.append(f"  • {sub['merchant_name']}: ฿{int(sub['amount']):,}/month")
                lines.append(f"\n💵 Monthly total: ฿{int(result['monthly_total']):,}")
                return {
                    "reply": "\n".join(lines),
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_beneficiaries (Contact list) ───
        if action == "get_beneficiaries":
            result = get_beneficiaries(user_id)
            if result["status"] == "success":
                lines = ["👥 Your contacts / beneficiaries:"]
                for ben in result["data"]:
                    lines.append(f"  • {ben['nickname']}: {ben['full_name']}")
                    lines.append(f"    📱 {ben['phone']} | 🏦 {ben['bank_name']}")
                return {
                    "reply": "\n".join(lines),
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_user ───
        if action == "get_user":
            result = get_user(user_id)
            if result["status"] == "success":
                data = result["data"]
                return {
                    "reply": f"👤 Your profile:\n"
                             f"  • Name: {data['full_name']}\n"
                             f"  • Phone: {data['phone']}\n"
                             f"  • Email: {data['email']}",
                    "status": "success",
                    "tier": "green",
                    "data": data
                }
            return _error_response(result)
        
        # ─── transfer ───
        if action == "transfer":
            return _execute_transfer(params, user_id, verified=False)
        
        # ─── cancel_subscription ───
        if action == "cancel_subscription":
            return _execute_cancel_subscription(params, user_id)
        
        # ─── block_card ───
        if action == "block_card":
            return _execute_block_card(params, user_id)
        
        # ─── report_card_lost ───
        if action == "report_card_lost":
            return {
                "reply": f"✅ Card reported as lost.\n"
                         f"A new card will be sent within 7 days.",
                "status": "success",
                "tier": "red"
            }
        
        return {
            "reply": f"Sorry, action '{action}' is not supported yet",
            "status": "unsupported",
            "tier": "green"
        }
    
    except Exception as e:
        return {
            "reply": f"❌ Error: {str(e)}",
            "status": "error",
            "tier": "green"
        }


def _execute_transfer(params: Dict, user_id: int, verified: bool = False) -> Dict[str, Any]:
    beneficiary_name = params.get("beneficiary_name", "")
    amount = params.get("amount", 0)
    
    if not beneficiary_name or not amount:
        return {
            "reply": "⚠️ Please specify recipient and amount\nExample: Transfer 500 to Mom",
            "status": "error",
            "tier": "yellow"
        }
    
    ben_result = find_beneficiary(user_id, beneficiary_name)
    if ben_result["status"] != "success":
        return {
            "reply": f"❌ Beneficiary '{beneficiary_name}' not found",
            "status": "error",
            "tier": "yellow"
        }
    
    ben = ben_result["data"]
    
    if verified:
        result = transfer(
            from_account_id=1,
            to_account_id=params.get("to_account_id", 3),
            amount=amount,
            note=beneficiary_name
        )
        
        if result["status"] == "success":
            data = result["data"]
            return {
                "reply": f"✅ Transferred ฿{int(data['amount']):,} to {ben['nickname']}\n"
                         f"💰 New balance: ฿{int(data['new_balance']):,}",
                "status": "success",
                "tier": "yellow" if amount <= 1000 else "red",
                "data": data
            }
        return _error_response(result)
    
    tier = check_tier("transfer", amount)
    
    if tier == Tier.RED:
        return _create_otp_challenge(user_id, "transfer", params, {
            "action": "transfer",
            "params": {
                "beneficiary_name": beneficiary_name,
                "amount": amount,
                "to_account_id": 3
            }
        })
    
    return {
        "reply": f"⚠️ Transfer ฿{int(amount):,} to {ben['nickname']} ({ben['full_name']})\n"
                 f"Confirm? [y/n]",
        "status": "pending_confirmation",
        "tier": "yellow",
        "requires_confirmation": True,
        "intent": {
            "action": "transfer",
            "params": {
                "beneficiary_name": beneficiary_name,
                "amount": amount,
                "to_account_id": 3
            }
        }
    }


def _execute_cancel_subscription(params: Dict, user_id: int) -> Dict[str, Any]:
    merchant = params.get("merchant_name", "")
    
    if not merchant:
        return {
            "reply": "⚠️ Please specify subscription to cancel\nExample: Cancel Netflix",
            "status": "error",
            "tier": "yellow"
        }
    
    subs_result = get_subscriptions(user_id)
    if subs_result["status"] != "success":
        return _error_response(subs_result)
    
    target = None
    for sub in subs_result["data"]:
        if merchant.lower() in sub["merchant_name"].lower():
            target = sub
            break
    
    if not target:
        return {
            "reply": f"❌ Subscription '{merchant}' not found",
            "status": "error",
            "tier": "yellow"
        }
    
    return {
        "reply": f"⚠️ Cancel {target['merchant_name']} (฿{int(target['amount']):,}/month)\n"
                 f"Confirm? [y/n]",
        "status": "pending_confirmation",
        "tier": "yellow",
        "requires_confirmation": True,
        "intent": {
            "action": "cancel_subscription",
            "params": {"subscription_id": target["id"]}
        }
    }


def _execute_block_card(params: Dict, user_id: int) -> Dict[str, Any]:
    """Block card — Yellow tier"""
    # Get user's cards
    cards_result = get_cards(user_id)
    if cards_result["status"] != "success":
        return _error_response(cards_result)
    
    cards = cards_result["data"]
    if not cards:
        return {
            "reply": "❌ No cards found",
            "status": "error",
            "tier": "yellow"
        }
    
    # หาบัตรที่ active
    target = None
    for card in cards:
        if card["status"] == "active":
            target = card
            break
    
    if not target:
        target = cards[0]
    
    return {
        "reply": f"⚠️ Block card {target['card_number']} ({target['card_type']})\n"
                 f"Confirm? [y/n]",
        "status": "pending_confirmation",
        "tier": "yellow",
        "requires_confirmation": True,
        "intent": {
            "action": "block_card",
            "params": {"card_id": target["id"]}
        }
    }


# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def _error_response(result: Dict) -> Dict[str, Any]:
    return {
        "reply": f"❌ {result.get('message', 'An error occurred')}",
        "status": "error",
        "tier": "green"
    }


def _summarize_action(action: str, params: Dict) -> str:
    if action == "transfer":
        return f"Transfer ฿{int(params.get('amount', 0)):,} to {params.get('beneficiary_name', '?')}"
    if action == "cancel_subscription":
        return f"Cancel {params.get('merchant_name', '?')}"
    if action == "block_card":
        return "Block card"
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
  • "Show contacts" / "Show beneficiaries"

🔄 Subscriptions:
  • "What am I paying for"
  • "Cancel Netflix"

💳 Cards:
  • "Show cards"
  • "Block card" (confirm)
  • "Report card lost" (OTP)

👤 Other:
  • "My profile"
  • "help"
  • "exit\""""