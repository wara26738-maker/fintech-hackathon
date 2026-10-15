# src/agent/loop.py
# Agent Loop — combines all components

from typing import Dict, Any, Optional
from ..intent.parser import parse_intent
from ..security.permission import check_tier, Tier
from ..tools.banking import (
    get_user, get_accounts, get_balance, get_transactions,
    transfer, get_subscriptions, cancel_subscription,
    get_cards, get_beneficiaries, find_beneficiary
)


# ═══════════════════════════════════════════
# MAIN ENTRY: PROCESS MESSAGE
# ═══════════════════════════════════════════

def process_message(user_input: str, user_id: int = 1) -> Dict[str, Any]:
    """
    Process user message → return response
    
    Returns:
        {
            "reply": str,
            "status": "success" | "error" | "pending_confirmation" | "pending_mfa",
            "tier": str,
            "requires_confirmation": bool,
            "requires_mfa": bool,
            "data": Any
        }
    """
    # 1. Parse intent
    intent = parse_intent(user_input)
    action = intent.get("action", "unknown")
    params = intent.get("params", {})
    
    # 2. Handle unknown / help
    if action == "unknown":
        return {
            "reply": f"Sorry, I don't understand '{user_input}' 😅\n"
                     f"Type 'help' to see available commands",
            "status": "unknown",
            "tier": "green"
        }
    
    if action == "help":
        return {
            "reply": _help_text(),
            "status": "success",
            "tier": "green"
        }
    
    # 3. Check permission tier
    amount = params.get("amount", 0)
    tier = check_tier(action, amount)
    
    # 4. Red tier → requires MFA
    if tier == Tier.RED:
        return {
            "reply": f"⚠️ This action requires additional verification (MFA)\n"
                     f"Please enter your OTP code",
            "status": "pending_mfa",
            "tier": "red",
            "requires_mfa": True,
            "intent": intent
        }
    
    # 5. Yellow tier → requires confirmation
    if tier == Tier.YELLOW:
        summary = _summarize_action(action, params)
        return {
            "reply": f"⚠️ {summary}\n\nConfirm? [y/n]",
            "status": "pending_confirmation",
            "tier": "yellow",
            "requires_confirmation": True,
            "intent": intent
        }
    
    # 6. Green tier → execute immediately
    return _execute_action(action, params, user_id)


# ═══════════════════════════════════════════
# EXECUTE ACTION
# ═══════════════════════════════════════════

def _execute_action(action: str, params: Dict, user_id: int) -> Dict[str, Any]:
    """Execute action based on intent"""
    
    try:
        # ─── get_balance ───
        if action == "get_balance":
            result = get_balance(account_id=1)
            if result["status"] == "success":
                balance = result["data"]["balance"]
                return {
                    "reply": f"💰 Your savings account balance: ฿{balance:,.2f}",
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
                    lines.append(f"  • {acc['account_number']}: ฿{acc['balance']:,.2f}")
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
                    lines.append(f"  • ฿{tx['amount']:,.2f} | {tx['category']} | {tx['note']}")
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
                    lines.append(f"  • {sub['merchant_name']}: ฿{sub['amount']:,.2f}/month")
                lines.append(f"\n💵 Monthly total: ฿{result['monthly_total']:,.2f}")
                return {
                    "reply": "\n".join(lines),
                    "status": "success",
                    "tier": "green",
                    "data": result["data"]
                }
            return _error_response(result)
        
        # ─── get_beneficiaries ───
        if action == "get_beneficiaries":
            result = get_beneficiaries(user_id)
            if result["status"] == "success":
                lines = ["👥 Saved beneficiaries:"]
                for ben in result["data"]:
                    lines.append(f"  • {ben['nickname']}: {ben['full_name']} ({ben['bank_name']})")
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
        
        # ─── transfer (requires confirmation) ───
        if action == "transfer":
            return _execute_transfer(params, user_id)
        
        # ─── cancel_subscription ───
        if action == "cancel_subscription":
            return _execute_cancel_subscription(params, user_id)
        
        # ─── report_card_lost ───
        if action == "report_card_lost":
            return {
                "reply": "⚠️ Identity verification required to report lost card (MFA)",
                "status": "pending_mfa",
                "tier": "red",
                "requires_mfa": True
            }
        
        # ─── fallback ───
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


def _execute_transfer(params: Dict, user_id: int) -> Dict[str, Any]:
    """Transfer money"""
    beneficiary_name = params.get("beneficiary_name", "")
    amount = params.get("amount", 0)
    
    if not beneficiary_name or not amount:
        return {
            "reply": "⚠️ Please specify recipient and amount\nExample: Transfer 500 to Mom",
            "status": "error",
            "tier": "yellow"
        }
    
    # Find beneficiary
    ben_result = find_beneficiary(user_id, beneficiary_name)
    if ben_result["status"] != "success":
        return {
            "reply": f"❌ Beneficiary '{beneficiary_name}' not found",
            "status": "error",
            "tier": "yellow"
        }
    
    ben = ben_result["data"]
    
    # Check tier by amount
    tier = check_tier("transfer", amount)
    
    # Red tier → MFA
    if tier == Tier.RED:
        return {
            "reply": f"⚠️ Transfer ฿{amount:,.2f} exceeds 1,000 THB\nMFA verification required",
            "status": "pending_mfa",
            "tier": "red",
            "requires_mfa": True
        }
    
    # Yellow tier → confirm
    return {
        "reply": f"⚠️ Transfer ฿{amount:,.2f} to {ben['nickname']} ({ben['full_name']})\n"
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
    """Cancel subscription"""
    merchant = params.get("merchant_name", "")
    
    if not merchant:
        return {
            "reply": "⚠️ Please specify subscription to cancel\nExample: Cancel Netflix",
            "status": "error",
            "tier": "yellow"
        }
    
    # Find subscription
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
        "reply": f"⚠️ Cancel {target['merchant_name']} (฿{target['amount']}/month)\n"
                 f"Confirm? [y/n]",
        "status": "pending_confirmation",
        "tier": "yellow",
        "requires_confirmation": True,
        "intent": {
            "action": "cancel_subscription",
            "params": {"subscription_id": target["id"]}
        }
    }


# ═══════════════════════════════════════════
# CONFIRM ACTION
# ═══════════════════════════════════════════

def confirm_action(intent: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    """
    Execute action after user confirmation
    """
    action = intent.get("action")
    params = intent.get("params", {})
    
    # ─── transfer ───
    if action == "transfer":
        to_id = params.get("to_account_id", 3)
        amount = params.get("amount", 0)
        
        result = transfer(
            from_account_id=1,
            to_account_id=to_id,
            amount=amount,
            note=params.get("beneficiary_name", "")
        )
        
        if result["status"] == "success":
            data = result["data"]
            return {
                "reply": f"✅ Transferred ฿{data['amount']:,.2f} to {params.get('beneficiary_name')}\n"
                         f"💰 New balance: ฿{data['new_balance']:,.2f}",
                "status": "success",
                "tier": "yellow",
                "data": data
            }
        return _error_response(result)
    
    # ─── cancel_subscription ───
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
    
    return {
        "reply": "❌ Cannot perform this action",
        "status": "error",
        "tier": "yellow"
    }


# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def _error_response(result: Dict) -> Dict[str, Any]:
    """Build error response"""
    return {
        "reply": f"❌ {result.get('message', 'An error occurred')}",
        "status": "error",
        "tier": "green"
    }


def _summarize_action(action: str, params: Dict) -> str:
    """Summarize action for user"""
    if action == "transfer":
        return f"Transfer ฿{params.get('amount', 0):,.2f} to {params.get('beneficiary_name', '?')}"
    if action == "cancel_subscription":
        return f"Cancel {params.get('merchant_name', '?')}"
    if action == "report_card_lost":
        return "Report card lost"
    return f"Perform action: {action}"


def _help_text() -> str:
    """Help text"""
    return """🤖 Here's what I can do:

💰 Finance:
  • "Check balance" — View account balance
  • "Show accounts" — List all accounts
  • "Show transactions" — View transactions

💸 Transfers:
  • "Transfer 500 to Mom" — Send money
  • "Show beneficiaries" — List recipients

🔄 Subscriptions:
  • "What am I paying for"
  • "Cancel Netflix"

💳 Cards:
  • "Show cards" — View all cards
  • "Report card lost"

👤 Other:
  • "My profile" — View user info
  • "help" — Show this menu
  • "exit" — Quit"""