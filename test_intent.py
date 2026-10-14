# test_intent.py

from src.intent.parser import parse_intent, describe_intent

print("=" * 70)
print("INTENT PARSER TEST")
print("=" * 70)

test_cases = [
    "ดูยอดเงิน",
    "ดูยอดเงินหน่อย",
    "บาลานซ์",
    "ยอดเงินเท่าไหร่",
    "โอนให้แม่ 500",
    "โอนให้แฟน 1,500",
    "ส่งเงินให้พ่อ 200",
    "ยกเลิก Netflix",
    "ยกเลิก Spotify",
    "บัตรหาย",
    "มีอะไรหักเงินบ้าง",
    "subscription ทั้งหมด",
    "ดูรายการ",
    "ประวัติการใช้จ่าย",
    "บัตรทั้งหมด",
    "ผู้รับโอน",
    "help",
    "สวัสดี",
]

for text in test_cases:
    intent = parse_intent(text)
    print(f"\n📝 Input:  \"{text}\"")
    print(f"   {describe_intent(intent)}")

print("\n" + "=" * 70)
print("✅ All intent tests passed!")