# src/intent/parser.py
# Intent Parser — แปลภาษาคน → คำสั่ง

import json
import os
import re
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


SYSTEM_PROMPT = """You are an intent parser for a banking AI agent.

Your job: convert user messages (in Thai or English) into a JSON command.

Available actions:
- get_balance: ดูยอดเงิน
- get_accounts: ดูบัญชีทั้งหมด
- get_transactions: ดูธุรกรรม
- get_cards: ดูบัตร
- get_subscriptions: ดู subscription
- get_beneficiaries: ดูผู้รับโอน
- transfer: โอนเงิน
- cancel_subscription: ยกเลิก subscription
- report_card_lost: แจ้งบัตรหาย
- get_user: ดูข้อมูลผู้ใช้
- help: ช่วยเหลือ
- unknown: ไม่เข้าใจ

Output format (JSON only):
{
    "action": "<action_name>",
    "params": {"key": "value"},
    "confidence": 0.0-1.0
}

Examples:
User: "ดูยอดเงิน"
Output: {"action": "get_balance", "params": {}, "confidence": 0.95}

User: "โอนให้แม่ 500"
Output: {"action": "transfer", "params": {"beneficiary_name": "แม่", "amount": 500}, "confidence": 0.9}

User: "ยกเลิก Netflix"
Output: {"action": "cancel_subscription", "params": {"merchant_name": "Netflix"}, "confidence": 0.9}

User: "บัตรหาย"
Output: {"action": "report_card_lost", "params": {}, "confidence": 0.85}

User: "มีอะไรหักเงินบ้าง"
Output: {"action": "get_subscriptions", "params": {}, "confidence": 0.9}
"""


def parse_with_mock(text: str) -> Dict[str, Any]:
    """Mock parser — if-else ไม่ต้องใช้ API key"""
    text_lower = text.lower().strip()
    
    amount_match = re.search(r'(\d+(?:,\d+)?(?:\.\d+)?)', text)
    amount = None
    if amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
    
    if any(k in text_lower for k in ["ยอดเงิน", "บาลาน", "balance", "เหลือเท่าไหร่"]):
        return {"action": "get_balance", "params": {}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["บัญชี", "account"]):
        return {"action": "get_accounts", "params": {}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["ธุรกรรม", "รายการ", "transaction", "ประวัติ", "ใช้จ่าย"]):
        return {"action": "get_transactions", "params": {"limit": 5}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["บัตร", "card"]):
        if "หาย" not in text_lower:
            return {"action": "get_cards", "params": {}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["subscription", "หักเงิน", "ตัดเงิน", "รายเดือน", "สมาชิก"]):
        return {"action": "get_subscriptions", "params": {}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["ผู้รับโอน", "beneficiary", "รายชื่อ"]):
        return {"action": "get_beneficiaries", "params": {}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["ยกเลิก", "cancel"]):
        merchants = ["netflix", "spotify", "icloud", "youtube", "disney"]
        for m in merchants:
            if m in text_lower:
                return {
                    "action": "cancel_subscription",
                    "params": {"merchant_name": m.capitalize()},
                    "confidence": 0.85
                }
        return {"action": "cancel_subscription", "params": {}, "confidence": 0.7}
    
    if any(k in text_lower for k in ["บัตรหาย", "lost"]):
        return {"action": "report_card_lost", "params": {}, "confidence": 0.9}
    
    if any(k in text_lower for k in ["โอน", "transfer", "ส่งเงิน"]):
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
    
    return {"action": "unknown", "params": {"original": text}, "confidence": 0.0}


def parse_with_openai(text: str) -> Dict[str, Any]:
    """ใช้ OpenAI GPT"""
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        return {"action": "unknown", "params": {"error": str(e)}, "confidence": 0.0}


def parse_with_deepseek(text: str) -> Dict[str, Any]:
    """ใช้ DeepSeek"""
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        return result
    except Exception as e:
        return {"action": "unknown", "params": {"error": str(e)}, "confidence": 0.0}


def parse_intent(text: str) -> Dict[str, Any]:
    """แปลภาษาคน → คำสั่ง"""
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
    """อธิบาย intent"""
    action = intent.get("action", "unknown")
    params = intent.get("params", {})
    confidence = intent.get("confidence", 0.0)
    
    desc = f"Action: {action}"
    if params:
        desc += f" | Params: {params}"
    desc += f" | Confidence: {confidence:.2f}"
    
    return desc