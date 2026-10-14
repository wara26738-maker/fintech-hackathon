# src/security/permission.py
# Permission Tiers — Green / Yellow / Red

from enum import Enum
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


# ═══════════════════════════════════════════
# TIER ENUM
# ═══════════════════════════════════════════

class Tier(str, Enum):
    GREEN = "green"      # Auto — ทำได้เลย
    YELLOW = "yellow"    # Confirm — ต้องยืนยัน
    RED = "red"          # MFA — ต้องยืนยันหลายชั้น


# ═══════════════════════════════════════════
# CONFIG (อ่านจาก .env)
# ═══════════════════════════════════════════

YELLOW_MAX_AMOUNT = float(os.getenv("YELLOW_TIER_MAX_AMOUNT", "1000"))
RED_MIN_AMOUNT = float(os.getenv("RED_TIER_MIN_AMOUNT", "1000"))


# ═══════════════════════════════════════════
# ACTION → TIER MAPPING
# ═══════════════════════════════════════════

# Actions ที่เป็น Green (อัตโนมัติ)
GREEN_ACTIONS = {
    "get_balance",
    "get_accounts",
    "get_transactions",
    "get_user",
    "get_cards",
    "get_beneficiaries",
    "get_subscriptions",
    "find_beneficiary",
    "query",
    "help",
}

# Actions ที่เป็น Yellow (ต้องยืนยัน)
YELLOW_ACTIONS = {
    "cancel_subscription",
    "apply_virtual_card",
    "update_note",
}

# Actions ที่เป็น Red (ต้อง MFA)
RED_ACTIONS = {
    "report_card_lost",
    "change_password",
    "subscribe_investment",
    "close_account",
}


# ═══════════════════════════════════════════
# MAIN FUNCTION: CHECK TIER
# ═══════════════════════════════════════════

def check_tier(action: str, amount: float = 0) -> Tier:
    """
    ตรวจสอบ permission tier ของ action
    
    Args:
        action: ชื่อ action (เช่น "transfer", "get_balance")
        amount: จำนวนเงิน (ถ้ามี)
    
    Returns:
        Tier (GREEN / YELLOW / RED)
    """
    # 1. ถ้าเป็น Green action
    if action in GREEN_ACTIONS:
        return Tier.GREEN
    
    # 2. ถ้าเป็น Red action
    if action in RED_ACTIONS:
        return Tier.RED
    
    # 3. ถ้าเป็น Yellow action
    if action in YELLOW_ACTIONS:
        return Tier.YELLOW
    
    # 4. ถ้าเป็น transfer → ขึ้นกับจำนวนเงิน
    if action == "transfer":
        if amount <= YELLOW_MAX_AMOUNT:
            return Tier.YELLOW
        else:
            return Tier.RED
    
    # 5. Default: Yellow (ปลอดภัยไว้ก่อน)
    return Tier.YELLOW


# ═══════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════

def require_confirmation(tier: Tier) -> bool:
    """ต้องยืนยันไหม?"""
    return tier in (Tier.YELLOW, Tier.RED)


def require_mfa(tier: Tier) -> bool:
    """ต้อง MFA ไหม?"""
    return tier == Tier.RED


def is_auto(tier: Tier) -> bool:
    """ทำอัตโนมัติได้ไหม?"""
    return tier == Tier.GREEN


# ═══════════════════════════════════════════
# MAIN API: EVALUATE ACTION
# ═══════════════════════════════════════════

def evaluate_action(action: str, amount: float = 0) -> Dict[str, Any]:
    """
    ประเมิน action + คืนค่าข้อมูลทั้งหมด
    
    Returns:
        {
            "action": str,
            "amount": float,
            "tier": str,
            "auto": bool,
            "requires_confirmation": bool,
            "requires_mfa": bool,
            "message": str
        }
    """
    tier = check_tier(action, amount)
    
    result = {
        "action": action,
        "amount": amount,
        "tier": tier.value,
        "auto": is_auto(tier),
        "requires_confirmation": require_confirmation(tier),
        "requires_mfa": require_mfa(tier),
    }
    
    # สร้างข้อความ
    if tier == Tier.GREEN:
        result["message"] = f"Action '{action}' — automatic"
    elif tier == Tier.YELLOW:
        result["message"] = f"Action '{action}' — requires confirmation"
    else:
        result["message"] = f"Action '{action}' — requires MFA"
    
    return result


# ═══════════════════════════════════════════
# TIER DISPLAY
# ═══════════════════════════════════════════

def tier_emoji(tier: Tier) -> str:
    """Emoji สำหรับ tier"""
    return {
        Tier.GREEN: "🟢",
        Tier.YELLOW: "🟡",
        Tier.RED: "🔴",
    }.get(tier, "⚪")


def tier_label(tier: Tier) -> str:
    """ข้อความอธิบาย tier"""
    return {
        Tier.GREEN: "Auto (automatic)",
        Tier.YELLOW: "Confirm (user confirmation)",
        Tier.RED: "MFA (strong verification)",
    }.get(tier, "Unknown")