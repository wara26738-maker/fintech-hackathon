# src/intent/parser.py
import json
import os
import re
from typing import Dict, Any, Optional
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are an intent parser for a banking AI agent.
Convert user messages (Thai or English) into JSON.
Available actions: get_balance, get_accounts, get_transactions, get_cards, get_subscriptions, get_beneficiaries, transfer, cancel_subscription, block_card, unblock_card, cancel_card, report_card_lost, get_user, help, unknown, get_savings_analysis, adjust_budget, split_bill, schedule_transfer.
Strictly use these parameter keys:
- For transfer: {"beneficiary_name": "mom", "amount": 500}
- For cancel_subscription: {"merchant_name": "Netflix"} OR {"subscription_id": 1}
- For block_card/unblock_card: {"card_number": "4111..."}
- For adjust_budget: {"amount": 500, "from_category": "entertainment", "to_category": "food"}
- For split_bill: {"amount": 1500, "contacts": ["Mom", "Sarah Work"], "split_type": "equal"}
- For schedule_transfer: {"amount": 1000, "beneficiary_name": "Mom", "date": "2026-11-01", "time": "09:00"}

Output JSON: {"action": "...", "params": {...}, "confidence": 0.0-1.0}
"""

KEYWORDS = {
    "transfer": ["transfer", "tranfer", "tranfers", "trnsfer", "tranf", "send money", "send"],
    "balance": ["balance", "balan", "balence", "balanc", "ยอดเงิน", "บาลาน", "ยอด"],
    "transactions": ["transactions", "transaction", "transact", "trans", "ธุรกรรม", "รายการ"],
    "cards": ["cards", "card", "บัตร"],
    "subscriptions": ["subscriptions", "subscription", "subs", "sub", "สมาชิก"],
    "beneficiaries": ["beneficiaries", "beneficiary", "contacts", "contact", "ผู้รับโอน", "รายชื่อ"],
    "help": ["help", "helps", "ช่วย"],
    "block": ["block", "blok", "บล็อก", "อายัด"],
    "unblock": ["unblock", "unblok", "ปลดบล็อก", "ปลดอายัด"],
    "cancel": ["cancel", "ยกเลิก"],
    "savings": ["savings", "budget", "spending", "goal", "ออม", "งบประมาณ", "รายจ่าย"],
}

def find_similar_word(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    words = re.findall(r'[a-zA-Zก-๙]+', text_lower)
    best_match = None
    best_score = 0.0
    for word in words:
        if len(word) < 3:
            continue
        for canonical, variants in KEYWORDS.items():
            for variant in variants:
                score = SequenceMatcher(None, word, variant).ratio()
                if score > best_score and score >= 0.65:
                    best_score = score
                    best_match = canonical
    return best_match

def parse_with_mock(text: str) -> Dict[str, Any]:
    text_lower = text.lower().strip()

    # ⭐ Catch the Savings Modal setup immediately to prevent AI confusion
    if "set savings goal" in text_lower:
        match = re.search(r'set savings goal\s+(\d+)\s+priorities\s+([a-zA-Z,]+)', text_lower)
        if match:
            return {"action": "set_savings_goal", "params": {"amount": int(match.group(1)), "priorities": match.group(2)}, "confidence": 0.95}

    amount_match = re.search(r'(\d{1,3}(?:,\d{3})+|\d+)', text)
    amount = None
    if amount_match:
        amount = int(amount_match.group(1).replace(',', ''))

    # จับเฉพาะตัวเลข 16 หลัก (มองข้ามขีดกลาง/เว้นวรรค)
    card_match = re.search(r'(\d(?:[-\s]?\d){15})', text)
    # จับ ID บัตร กรณีพิมพ์ "cancel card 1" (ตัวเลข 1 หลัก)
    card_id_match = re.search(r'(?:card|บัตร)\s+(\d+)', text_lower)

    # ⭐ จับ Split Bill จาก Modal: "Split 1500 with Mom, Sarah Work using equal"
    split_match = re.search(r'split\s+(\d+)\s+with\s+(.+?)\s+using\s+(equal|percentage)', text_lower)
    if split_match:
        amt = float(split_match.group(1))
        contacts_str = split_match.group(2)
        split_type = split_match.group(3)
        contacts = [c.strip().capitalize() for c in contacts_str.split(',')]
        return {"action": "split_bill", "params": {"amount": amt, "contacts": contacts, "split_type": split_type}, "confidence": 0.95}

    # ⭐ จับ Schedule จาก Modal: "Schedule 1000 to Mom on 2026-11-01 at 09:00"
    rec_match = re.search(r'schedule\s+(\d+)\s+to\s+([a-zA-Z]+)\s+on\s+(\d{4}-\d{2}-\d{2})\s+at\s+(\d{2}:\d{2})', text_lower)
    if rec_match:
        amt = float(rec_match.group(1))
        recipient = rec_match.group(2).capitalize()
        date_str = rec_match.group(3)
        time_str = rec_match.group(4)
        return {"action": "schedule_transfer", "params": {"amount": amt, "beneficiary_name": recipient, "date": date_str, "time": time_str}, "confidence": 0.95}

    if any(k in text_lower for k in ["ยอดเงิน", "บาลาน", "balance", "เหลือเท่าไหร่", "มีเงินเท่าไหร่", "balan"]):
        return {"action": "get_balance", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["บัญชี", "account"]):
        return {"action": "get_accounts", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["ธุรกรรม", "รายการ", "transaction", "ประวัติ", "ใช้จ่าย"]):
        return {"action": "get_transactions", "params": {"limit": 10}, "confidence": 0.9}

    if any(k in text_lower for k in ["subscription", "subs", "หักเงิน", "ตัดเงิน", "รายเดือน", "สมาชิก", "paying for", "am i paying"]):
        return {"action": "get_subscriptions", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["contact", "contacts", "ผู้รับโอน", "beneficiary", "beneficiaries", "รายชื่อ", "คนที่โอนด้วย"]):
        return {"action": "get_beneficiaries", "params": {}, "confidence": 0.9}

    # ─── Savings & Budget ───
    if "shift" in text_lower and ("budget" in text_lower or "money" in text_lower):
        match = re.search(r'shift\s+(\d+)\s+from\s+(\w+)\s+to\s+(\w+)', text_lower)
        if match:
            return {"action": "adjust_budget", "params": {"amount": int(match.group(1)), "from_category": match.group(2), "to_category": match.group(3)}, "confidence": 0.9}

    if any(k in text_lower for k in ["savings", "budget", "spending", "goal", "ออม", "งบประมาณ", "รายจ่าย"]):
        return {"action": "get_savings_analysis", "params": {}, "confidence": 0.9}

    # ⭐ สำคัญมาก: ต้องเช็ค Cancel Card ก่อน Cancel Subscription เสมอ
    if re.search(r'cancel.*card|card.*cancel|ยกเลิก.*บัตร|บัตร.*ยกเลิก', text_lower):
        params = {}
        if card_match:
            params["card_number"] = card_match.group(1)
        elif card_id_match:
            params["card_id"] = int(card_id_match.group(1))
        return {"action": "cancel_card", "params": params, "confidence": 0.85}

    # ─── Unblock Card ───
    if re.search(r'unblock|unblok|ปลดบล็อก|ปลดอายัด', text_lower):
        params = {}
        if card_match:
            params["card_number"] = card_match.group(1)
        return {"action": "unblock_card", "params": params, "confidence": 0.85}

    # ─── Block Card ───
    if re.search(r'block|blok|บล็อก|อายัด', text_lower):
        params = {}
        if card_match:
            params["card_number"] = card_match.group(1)
        return {"action": "block_card", "params": params, "confidence": 0.85}

    # ─── Cancel Subscription ───
    if any(k in text_lower for k in ["ยกเลิก", "cancel"]):
        sub_id_match = re.search(r'cancel\s+(?:sub(?:scription)?\s+)?(\d+)', text_lower)
        if sub_id_match:
             return {"action": "cancel_subscription", "params": {"subscription_id": int(sub_id_match.group(1))}, "confidence": 0.85}
             
        merchants = ["netflix", "spotify", "icloud", "youtube", "disney"]
        for m in merchants:
            if m in text_lower:
                return {"action": "cancel_subscription", "params": {"merchant_name": m.capitalize()}, "confidence": 0.85}
        return {"action": "cancel_subscription", "params": {}, "confidence": 0.7}

    # ─── Report Card Lost ───
    if any(k in text_lower for k in ["บัตรหาย", "card lost", "lost card", "lost"]):
        return {"action": "report_card_lost", "params": {}, "confidence": 0.9}

    # ─── Cards ───
    if any(k in text_lower for k in ["บัตร", "card"]):
        return {"action": "get_cards", "params": {}, "confidence": 0.9}

    # ─── Transfer ───
    if re.search(r'trans?f|tranfer|tranfers|trnsfer|โอน|ส่งเงิน|โอนเงิน|send money', text_lower):
        beneficiary = None
        for name in ["แม่", "mom", "พ่อ", "dad", "แฟน", "wife"]:
            if name in text_lower:
                beneficiary = name
                break
        params = {}
        if beneficiary:
            params["beneficiary_name"] = beneficiary
        if amount:
            params["amount"] = amount
        return {"action": "transfer", "params": params, "confidence": 0.85}

    if any(k in text_lower for k in ["ข้อมูล", "profile", "user", "ฉัน"]):
        return {"action": "get_user", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["help", "ช่วย", "ทำอะไรได้"]):
        return {"action": "help", "params": {}, "confidence": 0.95}

    suggestion = find_similar_word(text)
    return {"action": "unknown", "params": {"original": text, "suggestion": suggestion}, "confidence": 0.0}


def parse_with_deepseek(text: str) -> Dict[str, Any]:
    # ⭐ INTERCEPT: If it's the Savings Modal command, don't call DeepSeek
    text_lower = text.lower().strip()
    if "set savings goal" in text_lower:
        match = re.search(r'set savings goal\s+(\d+)\s+priorities\s+([a-zA-Z,]+)', text_lower)
        if match:
            return {"action": "set_savings_goal", "params": {"amount": int(match.group(1)), "priorities": match.group(2)}, "confidence": 0.95}

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"🚨 DEEPSEEK ERROR: {e}")
        return {"action": "unknown", "params": {"error": str(e)}, "confidence": 0.0}


def parse_with_openai(text: str) -> Dict[str, Any]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"action": "unknown", "params": {"error": str(e)}, "confidence": 0.0}


def parse_intent(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        return {"action": "unknown", "params": {}, "confidence": 0.0}
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    if provider == "openai":
        return parse_with_openai(text)
    elif provider == "deepseek":
        return parse_with_deepseek(text)
    else:
        return parse_with_mock(text)


def describe_intent(intent: Dict[str, Any]) -> str:
    action = intent.get("action", "unknown")
    params = intent.get("params", {})
    confidence = intent.get("confidence", 0.0)
    desc = f"Action: {action}"
    if params:
        desc += f" | Params: {params}"
    desc += f" | Confidence: {confidence:.2f}"
    return desc