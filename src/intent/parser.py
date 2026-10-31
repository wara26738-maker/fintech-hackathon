# src/intent/parser.py
import json
import os
import re
from typing import Dict, Any, Optional
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

# ⭐ อัปเดต SYSTEM_PROMPT ให้สอน AI คุยเล่น
SYSTEM_PROMPT = """You are a friendly and smart banking AI assistant.
Your job is to help users with banking tasks (transfers, balances, investments) and also chat with them naturally.

Available actions: get_balance, get_accounts, get_transactions, get_cards, get_subscriptions, get_beneficiaries, transfer, cancel_subscription, block_card, unblock_card, cancel_card, report_card_lost, get_user, help, unknown, get_savings_analysis, adjust_budget, split_bill, schedule_transfer, get_subscription_dashboard, smart_invest, chit_chat.

Strictly use these parameter keys:
- For transfer: {"beneficiary_name": "mom", "amount": 500, "category": "food"}
- For smart_invest: {"budget": 1000, "risk": "Low", "goal": "Long-term growth"}
- For split_bill: {"amount": 1500, "contacts": ["Mom"], "split_type": "equal", "percentages": [60, 40]}
- For chit_chat (greetings, jokes, general questions): {"reply": "Your friendly response here"}

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

    # ⭐ 1. ดักจับการคุยเล่นพื้นฐาน (กรณีไม่ได้ใช้ DeepSeek หรือเน็ตหลุด)
    if any(k in text_lower for k in ["hello", "hi", "hey", "สวัสดี", "ดีครับ", "ดีค่ะ", "หวัดดี"]):
        return {"action": "chit_chat", "params": {"reply": "สวัสดีครับ! ผมคือ Banking AI Assistant มีอะไรให้ผมช่วยจัดการเงินไหมครับ? 😊"}, "confidence": 0.9}
    if any(k in text_lower for k in ["thank", "ขอบคุณ", "แต๊งกิ้ว"]):
        return {"action": "chit_chat", "params": {"reply": "ยินดีครับ! ถ้ามีอะไรให้ช่วยอีกบอกได้เลยนะครับ 🙌"}, "confidence": 0.9}
    if any(k in text_lower for k in ["how are you", "เป็นไงบ้าง", "สบายดีไหม", "กินข้าวหรือยัง"]):
        return {"action": "chit_chat", "params": {"reply": "ผมทำงานตลอด 24 ชั่วโมง ไม่มีวันเหนื่อยครับ! แล้วคุณล่ะครับวันนี้เป็นยังไงบ้าง?"}, "confidence": 0.9}

    # ⭐ 2. ดักจับคำสั่งจาก Modal
    if "set savings goal" in text_lower:
        match = re.search(r'set savings goal\s+(\d+)\s+priorities\s+([a-zA-Z,]+)', text_lower)
        if match:
            return {"action": "set_savings_goal", "params": {"amount": int(match.group(1)), "priorities": match.group(2)}, "confidence": 0.95}

    inv_match = re.search(r'invest\s+([\d,]+)\s+risk\s+(low|medium|high)\s+goal\s+(.+)', text_lower)
    if inv_match:
        raw_budget = inv_match.group(1).replace(',', '')
        return {
            "action": "smart_invest", 
            "params": {"budget": float(raw_budget), "risk": inv_match.group(2).capitalize(), "goal": inv_match.group(3).strip().title()}, 
            "confidence": 0.95
        }

    amount_match = re.search(r'(\d{1,3}(?:,\d{3})+|\d+)', text)
    amount = None
    if amount_match:
        amount = int(amount_match.group(1).replace(',', ''))

    card_match = re.search(r'(\d(?:[-\s]?\d){15})', text)
    card_id_match = re.search(r'(?:card|บัตร)\s+(\d+)', text_lower)

    split_match = re.search(r'split\s+(\d+)\s+with\s+(.+?)\s+using\s+(equal|percentage)(?:\s+([\d\s,]+))?', text_lower)
    if split_match:
        amt = float(split_match.group(1))
        contacts_str = split_match.group(2)
        split_type = split_match.group(3)
        pct_str = split_match.group(4)
        contacts = [c.strip().capitalize() for c in contacts_str.split(',')]
        percentages = []
        if split_type == "percentage" and pct_str:
            percentages = [float(p.strip()) for p in pct_str.split(',') if p.strip()]
        return {"action": "split_bill", "params": {"amount": amt, "contacts": contacts, "split_type": split_type, "percentages": percentages}, "confidence": 0.95}

    rec_match = re.search(r'schedule\s+(\d+)\s+to\s+([a-zA-Z]+)\s+on\s+(\d{4}-\d{2}-\d{2})\s+at\s+(\d{2}:\d{2})', text_lower)
    if rec_match:
        return {"action": "schedule_transfer", "params": {"amount": float(rec_match.group(1)), "beneficiary_name": rec_match.group(2).capitalize(), "date": rec_match.group(3), "time": rec_match.group(4)}, "confidence": 0.95}

    if any(k in text_lower for k in ["ยอดเงิน", "บาลาน", "balance", "เหลือเท่าไหร่", "มีเงินเท่าไหร่", "balan"]):
        return {"action": "get_balance", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["บัญชี", "account"]):
        return {"action": "get_accounts", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["ธุรกรรม", "รายการ", "transaction", "ประวัติ", "ใช้จ่าย"]):
        return {"action": "get_transactions", "params": {"limit": 10}, "confidence": 0.9}

    if any(k in text_lower for k in ["dashboard", "direct debit", "usage", "manage subs"]):
        return {"action": "get_subscription_dashboard", "params": {}, "confidence": 0.95}

    if any(k in text_lower for k in ["subscription", "subs", "หักเงิน", "ตัดเงิน", "รายเดือน", "สมาชิก", "paying for", "am i paying"]):
        return {"action": "get_subscriptions", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["contact", "contacts", "ผู้รับโอน", "beneficiary", "beneficiaries", "รายชื่อ", "คนที่โอนด้วย"]):
        return {"action": "get_beneficiaries", "params": {}, "confidence": 0.9}

    if "shift" in text_lower and ("budget" in text_lower or "money" in text_lower):
        match = re.search(r'shift\s+(\d+)\s+from\s+(\w+)\s+to\s+(\w+)', text_lower)
        if match:
            return {"action": "adjust_budget", "params": {"amount": int(match.group(1)), "from_category": match.group(2), "to_category": match.group(3)}, "confidence": 0.9}

    if any(k in text_lower for k in ["savings", "budget", "spending", "goal", "ออม", "งบประมาณ", "รายจ่าย", "show my budget"]):
        return {"action": "get_savings_analysis", "params": {}, "confidence": 0.9}

    if re.search(r'cancel.*card|card.*cancel|ยกเลิก.*บัตร|บัตร.*ยกเลิก', text_lower):
        params = {}
        if card_match: params["card_number"] = card_match.group(1)
        elif card_id_match: params["card_id"] = int(card_id_match.group(1))
        return {"action": "cancel_card", "params": params, "confidence": 0.85}

    if re.search(r'unblock|unblok|ปลดบล็อก|ปลดอายัด', text_lower):
        params = {}
        if card_match: params["card_number"] = card_match.group(1)
        return {"action": "unblock_card", "params": params, "confidence": 0.85}

    if re.search(r'block|blok|บล็อก|อายัด', text_lower):
        params = {}
        if card_match: params["card_number"] = card_match.group(1)
        return {"action": "block_card", "params": params, "confidence": 0.85}

    if any(k in text_lower for k in ["ยกเลิก", "cancel"]):
        sub_id_match = re.search(r'cancel\s+(?:sub(?:scription)?\s+)?(\d+)', text_lower)
        if sub_id_match:
             return {"action": "cancel_subscription", "params": {"subscription_id": int(sub_id_match.group(1))}, "confidence": 0.85}
        merchants = ["netflix", "spotify", "icloud", "youtube", "disney"]
        for m in merchants:
            if m in text_lower:
                return {"action": "cancel_subscription", "params": {"merchant_name": m.capitalize()}, "confidence": 0.85}
        return {"action": "cancel_subscription", "params": {}, "confidence": 0.7}

    if any(k in text_lower for k in ["บัตรหาย", "card lost", "lost card", "lost"]):
        return {"action": "report_card_lost", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["บัตร", "card"]):
        return {"action": "get_cards", "params": {}, "confidence": 0.9}

    if re.search(r'trans?f|tranfer|tranfers|trnsfer|โอน|ส่งเงิน|โอนเงิน|send money', text_lower):
        beneficiary = None
        name_match = re.search(r'(?:to|ให้|ให้กับ)\s+([a-zA-Z\s]+?)(?:\s+\d|$)', text_lower)
        if name_match:
            beneficiary = name_match.group(1).strip().title()
        else:
            for name in ["แม่", "mom", "พ่อ", "dad", "แฟน", "wife"]:
                if name in text_lower:
                    beneficiary = name
                    break
        params = {}
        if beneficiary: params["beneficiary_name"] = beneficiary
        if amount: params["amount"] = amount
        return {"action": "transfer", "params": params, "confidence": 0.85}

    if any(k in text_lower for k in ["ข้อมูล", "profile", "user", "ฉัน"]):
        return {"action": "get_user", "params": {}, "confidence": 0.9}

    if any(k in text_lower for k in ["help", "ช่วย", "ทำอะไรได้"]):
        return {"action": "help", "params": {}, "confidence": 0.95}

    suggestion = find_similar_word(text)
    return {"action": "unknown", "params": {"original": text, "suggestion": suggestion}, "confidence": 0.0}


def parse_with_deepseek(text: str) -> Dict[str, Any]:
    text_lower = text.lower().strip()
    
    # ดักจับคำสั่งจาก Modal ล่วงหน้า
    if "set savings goal" in text_lower:
        match = re.search(r'set savings goal\s+(\d+)\s+priorities\s+([a-zA-Z,]+)', text_lower)
        if match:
            return {"action": "set_savings_goal", "params": {"amount": int(match.group(1)), "priorities": match.group(2)}, "confidence": 0.95}

    inv_match = re.search(r'invest\s+([\d,]+)\s+risk\s+(low|medium|high)\s+goal\s+(.+)', text_lower)
    if inv_match:
        raw_budget = inv_match.group(1).replace(',', '')
        return {"action": "smart_invest", "params": {"budget": float(raw_budget), "risk": inv_match.group(2).capitalize(), "goal": inv_match.group(3).strip().title()}, "confidence": 0.95}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            temperature=0.3, # ⭐ เพิ่มอุณหภูมิขึ้นนิดนึงเพื่อให้ AI ตอบคุยเล่นได้เป็นธรรมชาติ
        )
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"🚨 DEEPSEEK ERROR: {e}")
        return parse_with_mock(text)


def parse_with_openai(text: str) -> Dict[str, Any]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return parse_with_mock(text)


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