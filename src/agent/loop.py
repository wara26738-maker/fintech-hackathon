# src/agent/loop.py
import random
import time
from typing import Dict, Any

from ..intent.parser import parse_intent
from ..security.permission import check_tier, Tier
from ..tools.banking import (
    get_user, get_accounts, get_balance, get_transactions,
    transfer, get_subscriptions, cancel_subscription,
    get_cards, get_beneficiaries, find_beneficiary, find_all_beneficiaries,
    block_card, unblock_card, cancel_card,
    get_savings_analysis, adjust_category_budget, create_split_bill
)

_pending_otps: Dict[int, Dict[str, Any]] = {}
_pending_suggestions: Dict[int, Dict[str, Any]] = {}
_pending_actions: Dict[int, Dict[str, Any]] = {}
MAX_OTP_ATTEMPTS = 3
OTP_TTL_SECONDS = 300

def clear_expired_otps() -> None:
    now = time.time()
    for uid in [u for u, p in _pending_otps.items() if now > p["expires_at"]]:
        del _pending_otps[uid]

def _summarize_action(action: str, params: Dict) -> str:
    if action == "transfer":
        recipient = params.get("beneficiary_name") or params.get("recipient") or params.get("to") or params.get("name") or "?"
        return f"Transfer ฿{int(params.get('amount', 0)):,} to {recipient}"
    if action == "cancel_subscription":
        merchant = params.get("merchant_name") or params.get("service")
        return f"Cancel {merchant}" if merchant else "Cancel subscription"
    if action == "block_card":
        return f"Block card {params.get('card_number', '?')}"
    if action == "unblock_card":
        return f"Unblock card {params.get('card_number', '?')}"
    if action == "cancel_card":
        return "Cancel card"
    if action == "report_card_lost":
        return "Report card lost"
    if action == "split_bill":
        return f"Split ฿{int(params.get('amount', 0)):,} with {', '.join(params.get('contacts', []))}"
    if action == "schedule_transfer":
        return f"Schedule ฿{int(params.get('amount', 0)):,} to {params.get('beneficiary_name', '?')} on {params.get('date')}"
    return f"Perform action: {action}"

def _error_response(result: Dict) -> Dict[str, Any]:
    return {"reply": f"❌ {result.get('message', 'An error occurred')}", "status": "error", "tier": "green"}

def _help_text() -> str:
    return ("🤖 Here's what I can do:\n\n"
            "💰 Finance:\n"
            "  • 'Check balance'\n"
            "  • 'Show accounts'\n"
            "  • 'Show transactions'\n\n"
            "💸 Transfers:\n"
            "  • 'Transfer 500 to Mom'\n\n"
            "🔄 Subscriptions:\n"
            "  • 'What am I paying for'\n"
            "  • 'Cancel Netflix'\n\n"
            "💳 Cards:\n"
            "  • 'Show cards'\n"
            "  • 'Block card 4111-1111-1111-1111'\n"
            "  • 'Unblock card 4111-1111-1111-1111'\n"
            "  • 'Cancel card'\n"
            "  • 'Report card lost'\n\n"
            "👤 Other:\n"
            "  • 'My profile'\n"
            "  • 'help'\n"
            "  • 'exit'")

# ═══════════════════════════════════════════
# SUGGESTION HANDLING
# ═══════════════════════════════════════════

def handle_suggestion(user_id: int, answer: str) -> Dict[str, Any]:
    if user_id not in _pending_suggestions:
        return {"reply": "No pending suggestion.", "status": "error", "tier": "green"}
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
# MAIN FLOW
# ═══════════════════════════════════════════

def process_message(user_input: str, user_id: int = 1) -> Dict[str, Any]:
    text_lower = user_input.lower().strip()

    # ⭐ STATE MACHINE: ดักจับ Flow การเลือกคนชื่อซ้ำ
    if user_id in _pending_actions and _pending_actions[user_id]["step"] == "select_duplicate":
        options = _pending_actions[user_id]["options"]
        intent = _pending_actions[user_id]["intent"]
        try:
            idx = int(text_lower) - 1
            if 0 <= idx < len(options):
                selected = options[idx]
                del _pending_actions[user_id]
                
                intent["params"]["beneficiary_name"] = selected["nickname"]
                intent["params"]["to_account_id"] = selected["id"]
                
                amount = intent["params"].get("amount", 0)
                tier = check_tier("transfer", amount)
                if tier == Tier.RED:
                    return _create_otp_challenge(user_id, "transfer", intent["params"], intent)
                
                return {"reply": f"⚠️ Transfer ฿{int(amount):,} to {selected['full_name']} ({selected['phone']})?\nConfirm? [y/n]",
                        "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True, "intent": intent}
        except ValueError:
            return {"reply": "Please type the number (1 or 2) to select.", "status": "error", "tier": "green"}

    # ─── Flow ปกติ ───
    intent = parse_intent(user_input)
    action = intent.get("action", "unknown")
    params = intent.get("params", {})

    if action == "transfer":
        if not params.get("beneficiary_name"):
            params["beneficiary_name"] = (
                params.get("recipient") or params.get("to") or params.get("name")
            )
    elif action == "cancel_subscription":
        if not params.get("merchant_name"):
            params["merchant_name"] = params.get("service")

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

    # ⭐ จัดการ Split Bill (รับมาจาก Modal ที่ส่ง type มาด้วย)
    if action == "split_bill":
        amt = params.get("amount", 1500)
        contacts = params.get("contacts", ["Mom", "Sarah"])
        split_type = params.get("split_type", "equal")
        
        res = create_split_bill(user_id, amt, split_type, [1, 2], "Dinner")
        return {"reply": f"🧾 {res['message']}\n\nSplit with: {', '.join(contacts)}", "status": "success", "tier": "yellow"}

    # ⭐ จัดการ Schedule Transfer (มาจาก Modal)
    if action == "schedule_transfer":
        amt = params.get("amount", 1000)
        ben = params.get("beneficiary_name", "Mom")
        date_str = params.get("date")
        time_str = params.get("time", "09:00")
        
        return {"reply": f"⏰ Scheduled Transfer:\nAmount: ฿{int(amt):,}\nTo: {ben}\nStart Date: {date_str} at {time_str}\n\nConfirm? [y/n]",
                "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True, "intent": intent}

    # ─── Transfer (with Duplicate Name Handling) ───
    if action == "transfer":
        try:
            amount = float(params.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0
            
        if amount <= 0 or not params.get("beneficiary_name"):
            return {"reply": "⚠️ Please specify recipient and amount\nExample: Transfer 500 to Sarah",
                    "status": "error", "tier": "yellow"}

        ben_name = params.get("beneficiary_name", "")
        
        matches = find_all_beneficiaries(user_id, ben_name)
        if len(matches) > 1:
            _pending_actions[user_id] = {"step": "select_duplicate", "options": matches, "intent": intent}
            lines = [f"🔍 I found {len(matches)} contacts named '{ben_name}':"]
            for i, m in enumerate(matches, 1):
                lines.append(f"  [{i}] {m['full_name']} - {m['phone']}")
            lines.append("\nWhich one do you mean? (Reply with 1 or 2)")
            return {"reply": "\n".join(lines), "status": "success", "tier": "green"}

        if not matches:
            return {"reply": f"❌ Beneficiary '{ben_name}' not found", "status": "error", "tier": "yellow"}
            
        intent["params"]["beneficiary_name"] = matches[0]["nickname"]
        intent["params"]["to_account_id"] = matches[0]["id"]

        tier = check_tier("transfer", amount)
        if tier == Tier.RED:
            return _create_otp_challenge(user_id, "transfer", intent["params"], intent)

        return {"reply": f"⚠️ Transfer ฿{int(amount):,} to {matches[0]['nickname']} ({matches[0]['phone']})?\nConfirm? [y/n]",
                "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True, "intent": intent}

    # ─── ดักจับบัตร (Cancel/Block) ───
    if action == "cancel_card" and not params.get("card_id"):
        return _execute_action(action, params, user_id)
    if action in ["block_card", "unblock_card"] and not params.get("card_number"):
        return _execute_action(action, params, user_id)

    # ─── ส่งต่อให้ Permission ───
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
        return {"reply": "No pending suggestion.", "status": "error", "tier": "green"}
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
# OTP FLOW
# ═══════════════════════════════════════════

def _create_otp_challenge(user_id: int, action: str, params: Dict, intent: Dict) -> Dict[str, Any]:
    clear_expired_otps()
    otp = f"{random.randint(100000, 999999)}"
    _pending_otps[user_id] = {
        "otp": otp, "intent": intent, "attempts": 0,
        "expires_at": time.time() + OTP_TTL_SECONDS,
    }
    summary = _summarize_action(action, params)
    return {"reply": (f"🔴 HIGH-RISK ACTION\n{summary}\n\n"
                      f"📱 OTP sent to your phone.\n"
                      f"🔑 Demo OTP: {otp}\n\n"
                      f"Please enter the 6-digit OTP:"),
            "status": "pending_mfa", "tier": "red", "requires_mfa": True, "intent": intent}

def verify_otp(user_id: int, otp: str) -> Dict[str, Any]:
    if user_id not in _pending_otps:
        return {"reply": "❌ No pending OTP.", "status": "error", "tier": "red"}
    pending = _pending_otps[user_id]

    if time.time() > pending["expires_at"]:
        del _pending_otps[user_id]
        return {"reply": "⌛ OTP expired. Please start the action again.", "status": "error", "tier": "red"}

    if otp.strip() != pending["otp"]:
        pending["attempts"] += 1
        remaining = MAX_OTP_ATTEMPTS - pending["attempts"]
        if remaining <= 0:
            del _pending_otps[user_id]
            return {"reply": "🔒 Too many failed attempts. Please start again.", "status": "error", "tier": "red"}
        return {"reply": f"❌ Invalid OTP. {remaining} attempts remaining.", "status": "error", "tier": "red"}

    intent = pending["intent"]
    del _pending_otps[user_id]
    action = intent.get("action")
    params = intent.get("params", {})

    if action == "transfer":
        result = _execute_transfer(params, user_id, verified=True)
    elif action in ["block_card", "unblock_card", "cancel_card", "cancel_subscription"]:
        result = confirm_action(intent, user_id)
    else:
        result = _execute_action(action, params, user_id)

    result["reply"] = "✅ OTP verified!\n\n" + result["reply"]
    return result

# ═══════════════════════════════════════════
# CONFIRMATION EXECUTOR
# ═══════════════════════════════════════════

def confirm_action(intent: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    action = intent.get("action")
    params = intent.get("params", {})

    if action == "transfer":
        return _execute_transfer(params, user_id, verified=True)

    if action == "split_bill":
        return {"reply": f"✅ Split ฿{int(params.get('amount', 0)):,} successfully!", "status": "success", "tier": "yellow"}

    if action == "schedule_transfer":
        return {"reply": f"✅ Scheduled ฿{int(params.get('amount', 0)):,} to {params.get('beneficiary_name')} on {params.get('date')} at {params.get('time')}.", "status": "success", "tier": "yellow"}

    if action == "cancel_subscription":
        sub_id = params.get("subscription_id")
        
        if sub_id and not params.get("merchant_name"):
            subs = get_subscriptions(user_id)
            if subs["status"] == "success":
                target = next((s for s in subs["data"] if s["id"] == sub_id), None)
                if target:
                    params["merchant_name"] = target["merchant_name"]

        merchant = params.get("merchant_name") or params.get("service")
        
        result = cancel_subscription(
            subscription_id=sub_id,
            merchant_name=merchant,
        )
        if result["status"] == "success":
            return {"reply": f"✅ Cancelled {result['data']['merchant_name']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    if action == "block_card":
        result = block_card(params.get("card_number"), user_id=user_id)
        if result["status"] == "success":
            return {"reply": f"✅ Card blocked\n💳 {result['data']['card_number']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    if action == "unblock_card":
        result = unblock_card(params.get("card_number"), user_id=user_id)
        if result["status"] == "success":
            return {"reply": f"✅ Card unblocked\n💳 {result['data']['card_number']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    if action == "cancel_card":
        card_id = params.get("card_id")
        if not card_id:
            return {"reply": "❌ No card specified", "status": "error", "tier": "yellow"}
        result = cancel_card(card_id)
        if result["status"] == "success":
            return {"reply": f"✅ Card cancelled\n💳 {result['data']['card_number']}",
                    "status": "success", "tier": "yellow", "data": result["data"]}
        return _error_response(result)

    return {"reply": "❌ Cannot perform this action", "status": "error", "tier": "yellow"}

# ═══════════════════════════════════════════
# READ-ONLY / DISPATCH EXECUTOR
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
                return {"reply": "💰 Your accounts:", "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_transactions":
            limit = params.get("limit", 10)
            result = get_transactions(account_id=1, limit=limit)
            if result["status"] == "success":
                return {"reply": "📊 Recent transactions:", "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_cards":
            result = get_cards(user_id)
            if result["status"] == "success":
                return {"reply": "💳 Your cards:", "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_subscriptions":
            result = get_subscriptions(user_id)
            if result["status"] == "success":
                return {"reply": "🔄 Your subscriptions:", "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_beneficiaries":
            result = get_beneficiaries(user_id)
            if result["status"] == "success":
                return {"reply": "👥 Your contacts:", "status": "success", "tier": "green", "data": result["data"]}
            return _error_response(result)

        if action == "get_user":
            result = get_user(user_id)
            if result["status"] == "success":
                data = result["data"]
                return {"reply": f"👤 Your profile:\n  • Name: {data['full_name']}\n  • Phone: {data['phone']}\n  • Email: {data['email']}",
                        "status": "success", "tier": "green", "data": data}
            return _error_response(result)

        # ⭐ ADDED SAVINGS GOAL DB LOGIC HERE ⭐
        if action == "set_savings_goal":
            from ..db.session import SessionLocal
            from ..db.models import SavingsGoal
            db = SessionLocal()
            try:
                db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).update({"is_active": False})
                new_goal = SavingsGoal(
                    user_id=user_id,
                    target_amount=params.get("amount", 0),
                    priority_ranking=params.get("priorities", "food,transport")
                )
                db.add(new_goal)
                db.commit()
                return {"reply": f"✅ Savings goal of ฿{int(params.get('amount', 0)):,} set!\nTop priorities: {params.get('priorities').replace(',', ', ').title()}", "status": "success", "tier": "green"}
            except Exception as e:
                db.rollback()
                return {"reply": f"❌ Database error: {str(e)}", "status": "error", "tier": "green"}
            finally:
                db.close()

        if action == "get_savings_analysis":
            result = get_savings_analysis(user_id)
            if result["status"] == "success":
                d = result["data"]
                status_emoji = "🟢" if d["on_track"] else "🔴"
                reply = (f"🎯 **Savings Goal:** ฿{d['target']:,.0f}\n"
                         f"💵 **Income:** ฿{d['income']:,.0f} | **Spent:** ฿{d['spent']:,.0f}\n"
                         f"{status_emoji} **Projected Savings:** ฿{d['actual_savings']:,.0f}\n\n"
                         f"📊 **Category Breakdown:**\n{d['breakdown']}\n\n"
                         f"💡 *Tip: If you are over budget on a high priority, say 'Shift 500 from entertainment to food'.*")
                return {"reply": reply, "status": "success", "tier": "green"}
            return _error_response(result)

        if action == "adjust_budget":
            result = adjust_category_budget(
                user_id, 
                params.get("from_category"), 
                params.get("to_category"), 
                params.get("amount")
            )
            if result["status"] == "success":
                return {"reply": f"✅ {result['data']['message']}", "status": "success", "tier": "green"}
            return _error_response(result)

        if action == "transfer":
            return _execute_transfer(params, user_id, verified=False)
            
        if action in ["split_bill", "schedule_transfer"]:
            return confirm_action({"action": action, "params": params}, user_id)

        if action == "cancel_subscription":
            return _execute_cancel_subscription(params, user_id)

        if action == "block_card":
            return _execute_block_card(params, user_id)

        if action == "unblock_card":
            return _execute_unblock_card(params, user_id)

        if action == "cancel_card":
            return _execute_cancel_card(params, user_id)

        if action == "report_card_lost":
            return {"reply": "✅ Card reported as lost.", "status": "success", "tier": "red"}

        return {"reply": f"Sorry, action '{action}' is not supported yet", "status": "unsupported", "tier": "green"}

    except Exception as e:
        return {"reply": f"❌ Error: {str(e)}", "status": "error", "tier": "green"}

# ═══════════════════════════════════════════
# ACTION-SPECIFIC EXECUTORS
# ═══════════════════════════════════════════

def _execute_transfer(params: Dict, user_id: int, verified: bool = False) -> Dict[str, Any]:
    beneficiary_name = (
        params.get("beneficiary_name") or 
        params.get("recipient") or 
        params.get("to") or 
        params.get("name") or 
        ""
    )
    amount = params.get("amount", 0)
    to_account_id = params.get("to_account_id", 3)

    if not beneficiary_name or not amount:
        return {"reply": "⚠️ Please specify recipient and amount\nExample: Transfer 500 to Mom",
                "status": "error", "tier": "yellow"}

    ben_result = find_beneficiary(user_id, beneficiary_name)
    if ben_result["status"] != "success":
        return {"reply": f"❌ Beneficiary '{beneficiary_name}' not found", "status": "error", "tier": "yellow"}
    ben = ben_result["data"]

    if verified:
        result = transfer(
            from_account_id=1, to_account_id=to_account_id,
            amount=amount, note=beneficiary_name, category="transfer",
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
            "params": {"beneficiary_name": beneficiary_name, "amount": amount, "to_account_id": to_account_id},
        })

    return {"reply": f"⚠️ Transfer ฿{int(amount):,} to {ben['nickname']} ({ben['full_name']})\nConfirm? [y/n]",
            "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
            "intent": {"action": "transfer", "params": {"beneficiary_name": beneficiary_name, "amount": amount, "to_account_id": to_account_id}}}

def _execute_cancel_subscription(params: Dict, user_id: int) -> Dict[str, Any]:
    merchant = params.get("merchant_name") or params.get("service") or ""

    if not merchant:
        subs_result = get_subscriptions(user_id)
        if subs_result["status"] != "success":
            return _error_response(subs_result)
            
        subs = subs_result["data"]
        if not subs:
            return {"reply": "❌ You have no active subscriptions.", "status": "error", "tier": "yellow"}

        lines = ["🔄 Which subscription do you want to cancel?\n"]
        for s in subs:
            lines.append(f"  [{s['id']}] {s['merchant_name']} (฿{int(s['amount']):,}/month)")
        lines.append("\nType the name or ID to cancel (e.g., 'Cancel Netflix' or 'Cancel 1')")
        
        return {"reply": "\n".join(lines), "status": "success", "tier": "green"}

    subs_result = get_subscriptions(user_id)
    if subs_result["status"] != "success":
        return _error_response(subs_result)

    target = None
    for sub in subs_result["data"]:
        if merchant.lower() in sub["merchant_name"].lower() or str(sub["id"]) == str(merchant):
            target = sub
            break

    if not target:
        return {"reply": f"❌ Subscription '{merchant}' not found", "status": "error", "tier": "yellow"}

    return {
        "reply": f"⚠️ Cancel {target['merchant_name']} (฿{int(target['amount']):,}/month)\nConfirm? [y/n]",
        "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
        "intent": {"action": "cancel_subscription",
                   "params": {"subscription_id": target["id"], "merchant_name": target["merchant_name"]}},
    }

def _execute_block_card(params: Dict, user_id: int) -> Dict[str, Any]:
    card_number = params.get("card_number")
    if not card_number:
        return {"reply": "💳 Please enter the 16-digit card number you want to block.\nExample: Block card 4111-1111-1111-1111",
                "status": "success", "tier": "green"}
    return {"reply": f"⚠️ Block card {card_number}?\nConfirm? [y/n]",
            "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
            "intent": {"action": "block_card", "params": {"card_number": card_number}}}

def _execute_unblock_card(params: Dict, user_id: int) -> Dict[str, Any]:
    card_number = params.get("card_number")
    if not card_number:
        return {"reply": "💳 Please enter the 16-digit card number you want to unblock.\nExample: Unblock card 4111-1111-1111-1111",
                "status": "success", "tier": "green"}
    return {"reply": f"⚠️ Unblock card {card_number}?\nConfirm? [y/n]",
            "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
            "intent": {"action": "unblock_card", "params": {"card_number": card_number}}}

def _execute_cancel_card(params: Dict, user_id: int) -> Dict[str, Any]:
    cards_result = get_cards(user_id)
    if cards_result["status"] != "success":
        return _error_response(cards_result)

    cards = cards_result["data"]
    if not cards:
        return {"reply": "❌ No cards found", "status": "error", "tier": "yellow"}

    card_id = params.get("card_id")
    if card_id:
        target = next((c for c in cards if c["id"] == card_id), None)
        if not target:
            return {"reply": f"❌ Card #{card_id} not found", "status": "error", "tier": "yellow"}
        return {"reply": f"⚠️ Cancel card {target['card_number']} ({target['card_type']})?\nConfirm? [y/n]",
                "status": "pending_confirmation", "tier": "yellow", "requires_confirmation": True,
                "intent": {"action": "cancel_card", "params": {"card_id": target["id"]}}}

    active_cards = [c for c in cards if c["status"] == "active"]
    if not active_cards:
        return {"reply": "❌ No active cards to cancel", "status": "error", "tier": "yellow"}

    lines = ["💳 Which card do you want to cancel?\n"]
    for c in active_cards:
        lines.append(f"  [{c['id']}] {c['card_number']} ({c['card_type']})")
    lines.append("\nType the card ID (e.g., 'cancel card 1')")

    return {"reply": "\n".join(lines), "status": "success", "tier": "green"}