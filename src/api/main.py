# src/api/main.py
import os
from contextlib import asynccontextmanager
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any

# ⭐ SAFE uvloop: prevents crash if not installed on Linux/Mac
if sys.platform != "win32":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
from ..agent.loop import process_message, confirm_action, verify_otp, handle_suggestion, has_pending_suggestion
from ..db.session import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Banking AI Agent API starting...")
    init_db()
    from ..db.session import SessionLocal
    from ..db.models import User
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            print("📦 Seeding database...")
            from ..db.seed import seed_data
            seed_data()
            print("✅ Seed complete")
        else:
            print(f"✅ Database has {db.query(User).count()} users")
    except Exception as e:
        print(f"❌ Seed error: {e}")
    finally:
        db.close()
    print("✅ API ready")
    yield
    print("👋 API shutting down...")

app = FastAPI(title="Banking AI Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    user_id: int = 1
    session_id: Optional[str] = None
class ConfirmRequest(BaseModel):
    intent: Dict[str, Any]
    user_id: int = 1
class VerifyOTPRequest(BaseModel):
    user_id: int = 1
    otp: str
class ChatResponse(BaseModel):
    reply: str
    status: str
    tier: Optional[str] = None
    requires_confirmation: bool = False
    requires_mfa: bool = False
    data: Optional[Any] = None
    intent: Optional[Dict[str, Any]] = None
    retry_message: Optional[str] = None

@app.get("/")
async def root():
    return HTMLResponse(content=get_chat_html())

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0", "service": "Banking AI Agent"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        if has_pending_suggestion(request.user_id):
            answer = request.message.strip().lower()
            if answer in ["yes", "y", "no", "n", "ใช่", "ไม่"]:
                result = handle_suggestion(request.user_id, answer)
                if result.get("retry_message"):
                    retry_msg = result["retry_message"]
                    result = process_message(retry_msg, request.user_id)
                    result["reply"] = f"✅ Interpreting as '{retry_msg}'\n\n" + result["reply"]
                return ChatResponse(**result)
        
        print(f"🔍 DEBUG: message='{request.message}'")
        response = process_message(request.message, request.user_id)
        print(f"🔍 DEBUG: response={response}")
        return ChatResponse(**response)
    except Exception as e:
        import traceback
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        print(f"❌ TRACEBACK:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@app.post("/api/confirm", response_model=ChatResponse)
async def confirm(request: ConfirmRequest):
    try:
        response = confirm_action(request.intent, request.user_id)
        return ChatResponse(**response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/verify-otp", response_model=ChatResponse)
async def verify_otp_endpoint(request: VerifyOTPRequest):
    try:
        response = verify_otp(request.user_id, request.otp)
        return ChatResponse(**response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_chat_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <title>🏦 Banking AI Agent</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --navy: #14264f;
            --navy-2: #1b3264;
            --cream: #f7f4ee;
            --beige: #f0e7d6;
            --beige-2: #fbf8f2;
            --muted: #7c8190;
            --green: #2f8f5b;
            --green-bg: #e6f1ea;
            --line: #ece7df;
            --purple: #667eea;
            --purple-2: #764ba2;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #e8e4dc; color: var(--navy);
            display: flex; justify-content: center; overflow: hidden;
        }
        button { font-family: inherit; }

        .app {
            width: 100%; max-width: 430px; height: 100dvh;
            background: var(--cream); position: relative; overflow: hidden;
            display: flex; flex-direction: column;
            box-shadow: 0 0 40px rgba(20,38,79,.12);
        }

        /* ============ HOME DASHBOARD ============ */
        .dashboard {
            flex: 1; overflow-y: auto; padding: 24px 18px 18px;
            scrollbar-width: none;
        }
        .dashboard::-webkit-scrollbar { display: none; }

        .top {
            display: flex; justify-content: space-between;
            align-items: flex-start; margin-bottom: 22px;
        }
        .eyebrow { font-size: 11px; font-weight: 800; letter-spacing: 2.2px; color: var(--navy); margin-bottom: 8px; }
        .top h1 { font-size: 32px; line-height: 1.04; letter-spacing: -1.2px; font-weight: 900; color: var(--navy); }
        .avatar-btn {
            width: 52px; height: 52px; border-radius: 50%;
            background: var(--navy); border: none; color: white;
            display: grid; place-items: center; cursor: pointer;
            box-shadow: 0 8px 18px rgba(20,38,79,.2); flex-shrink: 0;
        }

        .ai-hero {
            background: linear-gradient(145deg, var(--navy) 0%, var(--navy-2) 100%);
            border-radius: 26px; padding: 20px; color: white;
            position: relative; overflow: hidden; margin-bottom: 24px;
            box-shadow: 0 14px 30px rgba(20,38,79,.22);
        }
        .ai-hero::after {
            content: ""; position: absolute; width: 160px; height: 160px;
            border: 1px solid rgba(255,255,255,.18); border-radius: 50%;
            right: -55px; bottom: -65px;
        }
        .hero-top { display: flex; align-items: center; gap: 12px; position: relative; z-index: 1; margin-bottom: 16px; }
        .ai-logo {
            width: 40px; height: 40px; border-radius: 50%;
            background: var(--cream); color: var(--navy);
            display: grid; place-items: center; font-size: 20px; flex-shrink: 0;
        }
        .hero-top h2 { font-size: 17px; font-weight: 800; letter-spacing: -.2px; }
        .hero-top p { font-size: 12px; color: #c7d0e6; margin-top: 3px; }
        .sparkle { position: absolute; right: 4px; top: 0; font-size: 34px; color: #f6efe3; opacity: .95; }
        .insight {
            background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.12);
            border-radius: 16px; padding: 16px; font-size: 14px; line-height: 1.55;
            color: #eef1f8; margin-bottom: 16px; position: relative; z-index: 1;
        }
        .ask-btn {
            width: 100%; border: none; border-radius: 18px;
            background: var(--beige-2); color: var(--navy);
            padding: 16px 18px; font-size: 16px; font-weight: 700;
            display: flex; align-items: center; justify-content: center;
            gap: 10px; cursor: pointer; position: relative; z-index: 1;
            transition: transform .15s ease;
        }
        .ask-btn:active { transform: scale(.98); }

        .section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .section-head h3 { font-size: 20px; font-weight: 900; letter-spacing: -.5px; }
        .see-all {
            border: none; background: transparent; color: var(--navy);
            font-size: 13px; font-weight: 700; cursor: pointer;
            display: flex; align-items: center; gap: 4px;
        }

        .quick-grid {
            display: grid; grid-template-columns: repeat(3, 1fr);
            gap: 10px; margin-bottom: 22px;
        }
        .quick-card {
            background: #fffdf9; border: 1px solid #f1ece4;
            border-radius: 20px; min-height: 106px;
            padding: 14px 8px 12px;
            display: flex; flex-direction: column;
            align-items: center; justify-content: center; gap: 10px;
            cursor: pointer; color: var(--navy);
            box-shadow: 0 4px 14px rgba(20,38,79,.035);
            transition: transform .15s ease;
        }
        .quick-card:active { transform: scale(.97); }
        .icon-circle {
            width: 46px; height: 46px; border-radius: 50%;
            background: var(--beige); display: grid; place-items: center; color: var(--navy);
        }
        .quick-card span:last-child { font-size: 13px; font-weight: 700; color: var(--navy); }

        .balance-card {
            background: #fffdf9; border: 1px solid #f1ece4;
            border-radius: 24px; padding: 18px; margin-bottom: 22px;
            cursor: pointer; box-shadow: 0 6px 20px rgba(20,38,79,.05);
        }
        .balance-head {
            display: flex; justify-content: space-between; align-items: center;
            color: var(--navy); font-size: 15px; font-weight: 700; margin-bottom: 8px;
        }
        .balance-label { display: flex; align-items: center; gap: 7px; }
        .balance-amount { font-size: 32px; font-weight: 900; letter-spacing: -1.2px; margin: 3px 0 10px; color: var(--navy); }
        .balance-bottom { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; }
        .delta { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--muted); }
        .delta b {
            color: var(--green); background: var(--green-bg); border-radius: 8px;
            padding: 5px 8px; font-size: 12px; display: inline-flex;
            align-items: center; gap: 3px; font-weight: 800;
        }

        .tx-list { display: flex; flex-direction: column; }
        .tx { display: flex; align-items: center; gap: 13px; padding: 14px 0; border-bottom: 1px solid #e9e4dc; }
        .tx:last-child { border-bottom: none; }
        .tx-icon {
            width: 46px; height: 46px; border-radius: 50%;
            background: var(--beige); color: var(--navy);
            display: grid; place-items: center; flex-shrink: 0;
        }
        .tx-info { flex: 1; min-width: 0; }
        .tx-info b { display: block; font-size: 16px; font-weight: 800; color: var(--navy); margin-bottom: 3px; }
        .tx-info small { color: var(--muted); font-size: 12px; }
        .tx-amount { font-size: 16px; font-weight: 800; color: var(--navy); white-space: nowrap; }

        /* ============ BOTTOM NAV ============ */
        .bottom-nav {
            height: 78px; flex-shrink: 0;
            background: rgba(247,244,238,.96); border-top: 1px solid #e9e4dc;
            display: grid; grid-template-columns: repeat(5, 1fr);
            align-items: center; padding: 7px 6px 9px;
            position: relative; z-index: 20; backdrop-filter: blur(12px);
        }
        .nav-item {
            border: none; background: transparent; color: #8f96a6;
            display: flex; flex-direction: column; align-items: center;
            justify-content: center; gap: 4px;
            font-size: 11px; font-weight: 700; cursor: pointer; min-height: 56px;
        }
        .nav-item.active { color: var(--navy); }
        .nav-ai { position: relative; }
        .ai-orb {
            width: 58px; height: 58px; border-radius: 50%;
            background: var(--beige); display: grid; place-items: center;
            margin-top: -30px; color: var(--navy); font-size: 28px;
            box-shadow: 0 8px 20px rgba(20,38,79,.12);
        }
        .nav-ai span { margin-top: -2px; }

        /* ============ CHAT SCREEN ============ */
        .chat-screen {
            position: absolute; inset: 0; z-index: 50;
            background: var(--cream); display: none; flex-direction: column;
        }
        .chat-screen.open { display: flex; }

        .chat-header {
            height: 72px; flex-shrink: 0;
            display: flex; align-items: center; gap: 12px;
            padding: 0 16px; background: var(--cream);
            border-bottom: 1px solid var(--line);
        }
        .back-btn {
            width: 40px; height: 40px; border-radius: 50%;
            border: none; background: #fffdf9; color: var(--navy);
            display: grid; place-items: center; cursor: pointer; font-size: 20px;
        }
        .chat-header-info { flex: 1; }
        .chat-header-info b { font-size: 16px; color: var(--navy); }
        .chat-header-info small { display: block; font-size: 11px; color: var(--muted); margin-top: 2px; }

        .chat-area {
            flex: 1; overflow-y: auto; padding: 14px 12px;
            background: #f7f4ee;
        }
        .message {
            display: flex; align-items: flex-start; gap: 8px;
            margin-bottom: 14px; animation: slideUp .25s ease-out;
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { justify-content: flex-end; }
        .ai-avatar, .user-avatar {
            width: 34px; height: 34px; border-radius: 50%;
            display: grid; place-items: center; font-size: 16px; flex-shrink: 0;
        }
        .ai-avatar { background: var(--navy); color: white; }
        .user-avatar { background: #f0c9a7; color: var(--navy); }
        .bubble {
            max-width: 82%; padding: 12px 14px; border-radius: 18px;
            font-size: 14px; line-height: 1.5; word-wrap: break-word;
        }
        .ai .bubble {
            background: #fffdf9; color: #303849;
            border: 1px solid #efe9df; border-bottom-left-radius: 5px;
        }
        .user .bubble {
            background: var(--navy); color: white; border-bottom-right-radius: 5px;
        }
        .ai .bubble b { color: var(--navy); }

        /* Welcome Quick Actions */
        .welcome-title { font-size: 14px; font-weight: 700; color: var(--navy); margin-bottom: 4px; }
        .welcome-subtitle { font-size: 12px; color: #666; margin-bottom: 12px; }
        .feature-group { margin-bottom: 12px; }
        .feature-label {
            display: block; font-size: 10px; font-weight: 800;
            color: var(--purple); text-transform: uppercase;
            letter-spacing: .6px; margin-bottom: 6px;
        }
        .quick-actions { display: flex; flex-wrap: wrap; gap: 6px; }
        .quick-btn {
            padding: 6px 10px; background: #f0f2ff; color: var(--purple);
            border: 1px solid #e0e3ff; border-radius: 10px;
            font-size: 11.5px; font-weight: 700;
            cursor: pointer; white-space: nowrap; transition: all .2s;
        }
        .quick-btn:hover, .quick-btn.active { background: var(--purple); color: white; border-color: var(--purple); }
        .welcome-tip {
            margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;
            color: #888; font-size: 11px; font-style: italic;
        }

        .chat-input-area {
            flex-shrink: 0; padding: 10px 12px 14px;
            background: var(--cream); border-top: 1px solid var(--line);
            display: flex; gap: 8px;
        }
        .chat-input-area input {
            flex: 1; min-width: 0;
            border: 1.5px solid #ddd6ca; background: #fffdf9;
            border-radius: 22px; padding: 12px 14px;
            font-size: 14px; outline: none; color: var(--navy);
        }
        .chat-input-area input:focus { border-color: var(--navy); }
        .chat-input-area button {
            border: none; border-radius: 22px;
            background: var(--navy); color: white;
            font-weight: 800; font-size: 14px; padding: 0 18px; cursor: pointer;
        }
        .chat-input-area button:disabled { opacity: .5; cursor: not-allowed; }

        .typing { color: var(--muted); font-size: 13px; }
        .typing::after { content: '...'; animation: dots 1.2s steps(4, end) infinite; }
        @keyframes dots {
            0%, 20% { content: ''; }
            40% { content: '.'; }
            60% { content: '..'; }
            80%, 100% { content: '...'; }
        }

        /* Data tables */
        .data-table {
            width: 100%; border-collapse: collapse;
            margin-top: 8px; font-size: 12px;
        }
        .data-table th {
            text-align: left; padding: 6px 4px;
            border-bottom: 1px solid #eee7dc; color: var(--muted);
            font-size: 10px; text-transform: uppercase;
        }
        .data-table th.right { text-align: right; }
        .data-table td { padding: 8px 4px; border-bottom: 1px solid #f4efe7; }
        .data-table td.right { text-align: right; font-weight: 700; }
        .data-table tr:last-child td { border-bottom: none; }
        .tx-category {
            display: inline-block; padding: 2px 6px;
            background: #f0f2ff; color: var(--purple);
            border-radius: 4px; font-size: 10px; font-weight: 600;
        }
        .status-badge {
            display: inline-block; padding: 2px 6px; border-radius: 4px;
            font-size: 10px; font-weight: 700;
        }
        .status-active { background: #dcfce7; color: #16a34a; }
        .status-blocked { background: #fee2e2; color: #dc2626; }
        .status-expired { background: #f3f4f6; color: #6b7280; }

        /* ===== AI Cards (จากโค้ดเดิม) ===== */
        .balance-visual-card {
            background: #fbf9f6; border-radius: 20px; padding: 20px;
            display: flex; justify-content: space-between; align-items: stretch;
            box-shadow: 0 4px 15px rgba(20,38,79,.06);
            width: 100%; min-width: 300px; border: 1px solid #ece8e2;
        }
        .bv-left { display: flex; flex-direction: column; justify-content: center; gap: 6px; }
        .bv-label { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--navy); }
        .bv-amount { font-size: 28px; font-weight: 800; color: var(--navy); letter-spacing: -.5px; margin: 4px 0; }
        .bv-delta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #7c8190; margin-top: 4px; }
        .bv-delta b {
            display: flex; align-items: center; gap: 3px;
            color: #2f8f5b; font-weight: 600;
            background: #e6f1ea; border-radius: 8px; padding: 4px 8px;
        }

        .chart-card {
            background: white; border-radius: 16px; padding: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,.05);
            width: 100%; min-width: 300px;
        }
        .chart-title {
            font-size: 14px; font-weight: 700; color: var(--navy);
            margin-bottom: 12px; display: flex; align-items: center; gap: 6px;
        }
        .chart-container { position: relative; height: 180px; width: 100%; margin-bottom: 12px; }
        .chart-text { font-size: 12px; color: #555; line-height: 1.5; white-space: normal; }

        .action-card {
            background: #fffbeb; border: 1px solid #fcd34d;
            border-radius: 16px; padding: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,.05);
            width: 100%; min-width: 280px;
        }
        .action-title {
            font-size: 14px; font-weight: 800; color: #d97706;
            margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
        }
        .action-desc { font-size: 14px; color: #333; margin-bottom: 16px; line-height: 1.5; }
        .action-desc b { color: #b45309; }
        .action-buttons { display: flex; gap: 8px; }
        .action-btn {
            flex: 1; padding: 8px; border-radius: 8px;
            font-weight: 700; font-size: 13px;
            cursor: pointer; border: none; transition: .2s;
        }
        .action-yes { background: #10b981; color: white; }
        .action-yes:hover { background: #059669; }
        .action-no { background: white; border: 1px solid #d1d5db; color: #6b7280; }
        .action-no:hover { background: #f3f4f6; }

        .success-card {
            background: white; border-radius: 20px; border: 2px solid #10b981;
            padding: 20px; box-shadow: 0 8px 25px rgba(16,185,129,.15);
            width: 100%; min-width: 300px;
        }
        .success-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
        .success-title { font-size: 16px; font-weight: 800; color: var(--navy); }
        .success-row {
            display: flex; justify-content: space-between;
            margin-bottom: 10px; font-size: 14px; color: #555;
        }
        .success-row b { color: var(--navy); font-size: 15px; }
        .success-divider { border-top: 1px dashed #ccc; margin: 16px 0; }
        .success-footer { font-size: 13px; color: #333; text-align: center; }
        .btn-check-portfolio {
            width: 100%; padding: 10px; margin-top: 16px;
            background: #10b981; color: white; border: none; border-radius: 12px;
            font-size: 14px; font-weight: 700; cursor: pointer;
            transition: all .2s;
        }
        .btn-check-portfolio:hover { background: #059669; }

        .receipt-card, .ebill-card {
            background: white; border-radius: 16px; padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,.05); border: 1px dashed #ccc;
            width: 100%; min-width: 300px; position: relative;
        }
        .ebill-card { border: 1px solid #f0f0f0; box-shadow: 0 8px 25px rgba(0,0,0,.08); border-radius: 20px; padding: 24px; }
        .receipt-header { font-size: 16px; font-weight: 800; color: var(--navy); text-align: center; margin-bottom: 16px; letter-spacing: 1px; }
        .receipt-row { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 8px; color: #555; }
        .receipt-row b { color: var(--navy); font-size: 15px; }
        .receipt-divider { border-top: 1px dashed #ccc; margin: 12px 0; }
        .receipt-footer { font-size: 13px; color: var(--muted); text-align: center; font-weight: 500; }
        .receipt-list { font-size: 13px; color: #444; margin-top: 8px; padding-left: 4px; }
        .ebill-header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px dashed #ddd; padding-bottom: 12px; margin-bottom: 16px;
        }
        .ebill-title { font-size: 14px; font-weight: 700; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .ebill-status { background: #dcfce7; color: #16a34a; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; }
        .ebill-amount { font-size: 32px; font-weight: 800; color: var(--navy); text-align: center; margin-bottom: 20px; letter-spacing: -1px; }
        .ebill-row { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 13px; color: #555; }
        .ebill-row span:last-child { font-weight: 600; color: var(--navy); text-align: right; }
        .ebill-footer {
            border-top: 1px dashed #ddd; padding-top: 16px; margin-top: 16px;
            text-align: center; font-size: 11px; color: #999;
        }
        .ebill-barcode {
            height: 24px; width: 70%; margin: 10px auto 0;
            background: repeating-linear-gradient(90deg, #14264f, #14264f 2px, transparent 2px, transparent 4px, #14264f 4px, #14264f 5px, transparent 5px, transparent 9px);
            opacity: .6; border-radius: 2px;
        }

        .portfolio-card {
            background: linear-gradient(135deg, #14264f 0%, #1c3363 100%);
            color: white; border-radius: 20px; padding: 20px;
            box-shadow: 0 10px 30px rgba(20,38,79,.4);
            width: 100%; min-width: 300px;
        }
        .portfolio-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .portfolio-title { font-size: 14px; font-weight: 700; color: #d3d9e8; text-transform: uppercase; letter-spacing: 1px; }
        .portfolio-list { display: flex; flex-direction: column; gap: 10px; }
        .portfolio-item {
            display: flex; justify-content: space-between; align-items: center;
            background: rgba(255,255,255,.05); padding: 10px; border-radius: 12px;
        }
        .portfolio-item-left { display: flex; flex-direction: column; }
        .portfolio-item-symbol { font-size: 14px; font-weight: 700; }
        .portfolio-item-name { font-size: 11px; color: #9ca3af; }
        .portfolio-item-right { text-align: right; }
        .portfolio-item-value { font-size: 14px; font-weight: 700; }
        .portfolio-item-pnl { font-size: 11px; font-weight: 600; color: #9ca3af; }

        .confirm-buttons { display: flex; gap: 8px; margin-top: 10px; }
        .confirm-btn {
            flex: 1; border: none; padding: 9px 10px;
            border-radius: 10px; font-weight: 800; cursor: pointer;
        }
        .confirm-yes { background: #10b981; color: white; }
        .confirm-no { background: #f0ede7; color: #6b7280; }

        /* Modal */
        .modal-overlay {
            display: none; position: absolute; inset: 0;
            background: rgba(0,0,0,.5); z-index: 1000;
            align-items: center; justify-content: center; padding: 1rem;
        }
        .modal-content {
            background: white; padding: 1.5rem; border-radius: 20px;
            width: 100%; max-width: 350px;
            box-shadow: 0 10px 30px rgba(0,0,0,.2);
        }
        .modal-content h2 { font-size: 1.1rem; margin-bottom: 1rem; color: var(--navy); }
        .form-group { margin-bottom: 1rem; }
        .form-group label {
            display: block; font-size: 12px; color: #666;
            margin-bottom: 6px; font-weight: 700;
        }
        .form-group input, .form-group select {
            width: 100%; padding: 10px; border: 1.5px solid #e0e0e0;
            border-radius: 8px; font-size: 14px; outline: none;
            transition: border-color .2s;
        }
        .form-group input:focus, .form-group select:focus { border-color: var(--purple); }
        .modal-buttons { display: flex; gap: 8px; margin-top: 16px; }
        .modal-buttons button {
            flex: 1; padding: 10px; border: none;
            border-radius: 8px; font-weight: 700; cursor: pointer;
        }
        .btn-cancel { background: #f3f4f6; color: #6b7280; }
        .btn-submit { background: var(--navy); color: white; }

        @media (max-width: 360px) {
            .top h1 { font-size: 28px; }
            .quick-card { min-height: 98px; }
            .balance-amount { font-size: 28px; }
        }
                /* ===== OTP Modal ===== */
        .otp-modal-content { text-align: center; max-width: 360px; }
        .otp-icon-wrap {
            width: 64px; height: 64px; margin: 0 auto 14px;
            border-radius: 50%; background: #eef1f8;
            display: grid; place-items: center; font-size: 30px;
        }
        .otp-modal-content h2 {
            font-size: 1.2rem; margin-bottom: 6px; color: var(--navy);
            text-align: center; font-weight: 800;
        }
        .otp-subtitle {
            font-size: 13px; color: #666; margin-bottom: 20px; line-height: 1.5;
        }
        .otp-inputs {
            display: flex; gap: 6px; justify-content: center; margin-bottom: 14px;
        }
        .otp-inputs input {
            width: 44px; height: 54px; text-align: center;
            font-size: 22px; font-weight: 800;
            border: 2px solid #e0e0e0; border-radius: 12px;
            outline: none; color: var(--navy);
            transition: all .2s; background: white;
        }
        .otp-inputs input:focus {
            border-color: var(--navy); box-shadow: 0 0 0 3px rgba(20,38,79,.1);
        }
        .otp-inputs input.filled { border-color: var(--navy); background: #f8f6f0; }
        .otp-hint {
            font-size: 12px; color: #666; margin-bottom: 12px;
            padding: 10px; background: #f8f6f0; border-radius: 10px; line-height: 1.4;
        }
        .otp-hint b { color: var(--navy); font-weight: 800; }
        .otp-error {
            color: #dc2626; font-size: 12.5px; font-weight: 600;
            margin-bottom: 10px; min-height: 18px; line-height: 1.3;
        }
        .otp-resend { font-size: 12px; color: #888; margin-bottom: 14px; }
        .otp-resend a {
            color: var(--navy); font-weight: 700; cursor: pointer;
            text-decoration: underline;
        }

        /* ===== Toast ===== */
        .toast {
            position: absolute; top: 16px; left: 50%;
            transform: translateX(-50%) translateY(-120px);
            background: var(--navy); color: white;
            padding: 12px 18px; border-radius: 14px;
            font-size: 13px; font-weight: 600;
            box-shadow: 0 10px 30px rgba(20,38,79,.3);
            z-index: 2000;
            transition: transform .35s cubic-bezier(.34,1.56,.64,1), opacity .2s;
            max-width: 90%; text-align: center;
            display: flex; align-items: center; gap: 8px;
            opacity: 0; pointer-events: none;
        }
        .toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }

        @media (max-width: 380px) {
            .otp-inputs { gap: 5px; }
            .otp-inputs input { width: 38px; height: 48px; font-size: 18px; }
        }
                /* ===== Push Notification Banner ===== */
        .push-notification {
            position: absolute;
            top: 10px; left: 10px; right: 10px;
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-radius: 18px;
            padding: 14px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15), 0 1px 3px rgba(0,0,0,0.05);
            display: flex; gap: 12px; align-items: flex-start;
            transform: translateY(-150%);
            transition: transform 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            z-index: 3000;
        }
        .push-notification.show { transform: translateY(0); }
        .pn-icon {
            width: 38px; height: 38px; border-radius: 10px;
            background: var(--navy); color: white;
            display: grid; place-items: center; font-size: 20px; flex-shrink: 0;
        }
        .pn-content { flex: 1; min-width: 0; }
        .pn-header {
            display: flex; justify-content: space-between;
            font-size: 11px; color: #666; text-transform: uppercase;
            font-weight: 700; margin-bottom: 3px; letter-spacing: 0.5px;
        }
        .pn-title { font-size: 14px; font-weight: 800; color: var(--navy); margin-bottom: 2px; }
        .pn-body { font-size: 13px; color: #333; line-height: 1.4; }
        .pn-body b { font-size: 16px; color: var(--navy); letter-spacing: 1.5px; }
    </style>
</head>
<body>
<div class="app">
    <!-- Notification Banner -->
    <div id="push-notification" class="push-notification"></div>

    <!-- ============ HOME DASHBOARD ============ -->
    <main id="dashboardScreen" class="dashboard">
        <header class="top">
            <div>
                <div class="eyebrow">GOOD EVENING</div>
                <h1>Your money,<br>simplified.</h1>
            </div>
            <button class="avatar-btn" type="button" aria-label="Profile">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="8" r="4"></circle>
                    <path d="M4 21a8 8 0 0 1 16 0"></path>
                </svg>
            </button>
        </header>

        <section class="ai-hero">
            <div class="hero-top">
                <div class="ai-logo">✦</div>
                <div>
                    <h2>Your AI money assistant</h2>
                    <p>Smarter insights. Better decisions.</p>
                </div>
                <div class="sparkle">✦</div>
            </div>
            <div class="insight">
                You spent 12% less on dining this week compared to last week.
                Want to see where you could save more?
            </div>
            <button class="ask-btn" type="button" onclick="openChat()">
                Ask AI anything <span>→</span>
            </button>
        </section>

        <section>
            <div class="section-head">
                <h3>Quick actions</h3>
                <button class="see-all" type="button" onclick="openChat('Show all quick actions')">See all →</button>
            </div>
            <div class="quick-grid">
                <button class="quick-card" type="button" onclick="openChat(); setTimeout(openTransferModal, 200);">
                    <span class="icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M7 7h11l-3-3"></path><path d="M17 17H6l3 3"></path>
                        </svg>
                    </span>
                    <span>Transfers</span>
                </button>
                <button class="quick-card" type="button" onclick="openChat('Show my budget')">
                    <span class="icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M4 19V9"></path><path d="M10 19V5"></path><path d="M16 19v-7"></path><path d="M22 19H2"></path>
                        </svg>
                    </span>
                    <span>Budget</span>
                </button>
                <button class="quick-card" type="button" onclick="openChat('invest 10000 risk Medium goal Long-term growth')">
                    <span class="icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 17l6-6 4 4 8-8"></path><path d="M14 7h7v7"></path>
                        </svg>
                    </span>
                    <span>Investments</span>
                </button>
                <button class="quick-card" type="button" onclick="openChat('Show cards')">
                    <span class="icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 10h18"></path>
                        </svg>
                    </span>
                    <span>Cards</span>
                </button>
                <button class="quick-card" type="button" onclick="openChat('Show subscription dashboard')">
                    <span class="icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="4" y="5" width="16" height="16" rx="2"></rect><path d="M8 3v4"></path><path d="M16 3v4"></path><path d="M4 11h16"></path>
                        </svg>
                    </span>
                    <span>Subscriptions</span>
                </button>
                <button class="quick-card" type="button" onclick="openChat('Show transactions')">
                    <span class="icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M6 3h9l4 4v14H6z"></path><path d="M14 3v5h5"></path><path d="M9 13h6"></path><path d="M9 17h6"></path>
                        </svg>
                    </span>
                    <span>Bills</span>
                </button>
            </div>
        </section>

        <section class="balance-card" onclick="openChat('Check balance')">
            <div class="balance-head">
                <span class="balance-label">
                    Total balance
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                </span>
                <span>›</span>
            </div>
            <div class="balance-amount">$12,580.00</div>
            <div class="balance-bottom">
                <div class="delta">
                    <b>↗ +3.2%</b>
                    <span>vs. last month</span>
                </div>
                <svg width="118" height="52" viewBox="0 0 130 56" fill="none">
                    <defs>
                        <linearGradient id="miniGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0" stop-color="#8d9bc2" stop-opacity=".22"/>
                            <stop offset="1" stop-color="#8d9bc2" stop-opacity="0"/>
                        </linearGradient>
                    </defs>
                    <path d="M2 52C14 48 20 36 32 34s20 10 34 6 22-18 34-16 18-4 28-10V56H2z" fill="url(#miniGrad)"/>
                    <path d="M2 52C14 48 20 36 32 34s20 10 34 6 22-18 34-16 18-4 28-10" stroke="#aab4d0" stroke-width="1.8" stroke-linecap="round"/>
                </svg>
            </div>
        </section>

        <section>
            <div class="section-head">
                <h3>Recent transactions</h3>
                <button class="see-all" type="button" onclick="openChat('Show transactions')">See all →</button>
            </div>
            <div class="tx-list">
                <div class="tx">
                    <div class="tx-icon">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M7 3v18"></path><path d="M7 7h9a4 4 0 0 1 0 8H7"></path>
                        </svg>
                    </div>
                    <div class="tx-info">
                        <b>Dining</b>
                        <small>Oct 24, 2025</small>
                    </div>
                    <div class="tx-amount">- $12.50</div>
                </div>
                <div class="tx">
                    <div class="tx-icon">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M6 8h12l-1 13H7L6 8z"></path><path d="M9 8a3 3 0 0 1 6 0"></path>
                        </svg>
                    </div>
                    <div class="tx-info">
                        <b>Shopping</b>
                        <small>Oct 23, 2025</small>
                    </div>
                    <div class="tx-amount">- $68.90</div>
                </div>
                <div class="tx">
                    <div class="tx-icon">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M7 7h11l-3-3"></path><path d="M17 17H6l3 3"></path>
                        </svg>
                    </div>
                    <div class="tx-info">
                        <b>Transfer to Savings</b>
                        <small>Oct 22, 2025</small>
                    </div>
                    <div class="tx-amount">- $200.00</div>
                </div>
            </div>
        </section>
    </main>

    <!-- ============ CHAT SCREEN ============ -->
    <section id="chatScreen" class="chat-screen">
        <header class="chat-header">
            <button class="back-btn" type="button" onclick="closeChat()">←</button>
            <div class="chat-header-info">
                <b>AI Assistant</b>
                <small>Banking AI Agent</small>
            </div>
            <div class="ai-logo" style="width:38px;height:38px;background:var(--navy);color:white;">✦</div>
        </header>

        <div id="chat" class="chat-area">
            <div class="message ai">
                <div class="ai-avatar">🤖</div>
                <div class="bubble">
                    <div class="welcome-title">👋 Hello! I'm your AI banking assistant.</div>
                    <div class="welcome-subtitle">Click any button to try:</div>

                    <div class="feature-group" style="background: #f0fdf4; padding: 10px; border-radius: 12px; border: 1px solid #bbf7d0; margin-bottom: 12px;">
                        <span class="feature-label" style="color: #166534;">⚡ Automated Action</span>
                        <div class="quick-actions">
                            <button class="quick-btn" style="background:#22c55e; color:white; border:none; box-shadow:0 4px 10px rgba(34,197,94,.3);" onclick="quickSend('end of month reset')">🔄 End-of-Month Reset</button>

                        </div>
                    </div>

                    <div class="feature-group">
                        <span class="feature-label">💸 Money Movement</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="openTransferModal()">✉️ Transfer</button>
                            <button class="quick-btn" onclick="openRecurringModal()">🔄 Recurring</button>
                            <button class="quick-btn" onclick="openSplitMethodModal()">🍕 Split Bill</button>
                        </div>
                    </div>

                    <div class="feature-group">
                        <span class="feature-label">💰 Finance & Wealth</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('Check balance')">💵 Balance</button>
                            <button class="quick-btn" onclick="quickSend('Show transactions')">📊 Txns</button>
                            <button class="quick-btn" onclick="openSavingsModal()">🎯 Setup Goal</button>
                            <button class="quick-btn" onclick="quickSend('Show my budget')">📈 Check Goal</button>
                            <button class="quick-btn" onclick="openInvestModal()">📈 Smart Invest</button>
                            <button class="quick-btn" onclick="quickSend('Show portfolio')">💼 Portfolio</button>
                        </div>
                    </div>

                    <div class="feature-group">
                        <span class="feature-label">🔄 Subs & Cards</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('Show subscription dashboard')">📈 Usage Dashboard</button>
                            <button class="quick-btn" onclick="quickSend('What am I paying for')">📺 List</button>
                            <button class="quick-btn" onclick="quickSend('Show cards')">💳 Cards</button>
                            <button class="quick-btn" onclick="openBlockCardModal()">🔒 Block Card</button>
                            <button class="quick-btn" onclick="openCancelCardModal()">❌ Cancel Card</button>
                        </div>
                    </div>

                    <div class="welcome-tip">
                        💡 I understand natural language — try any way!
                    </div>
                </div>
            </div>
        </div>

        <div class="chat-input-area">
            <input id="input" type="text" placeholder="Type a message..." autocomplete="off">
            <button id="send" type="button" onclick="send()">Send</button>
        </div>
    </section>

    <!-- ============ MODALS ============ -->
    <div class="modal-overlay" id="transfer-modal">
        <div class="modal-content">
            <h2>✉️ Transfer Money</h2>
            <div class="form-group">
                <label>Select Recipient</label>
                <div class="quick-actions" id="transfer-contacts">
                    <button class="quick-btn" onclick="selectRecipient('Mom', this)">👩 Mom</button>
                    <button class="quick-btn" onclick="selectRecipient('Sarah Work', this)">👩‍💼 Sarah Work</button>
                    <button class="quick-btn" onclick="selectRecipient('Sarah Sister', this)">👧 Sarah Sister</button>
                </div>
                <input type="text" id="transfer-recipient" placeholder="Or type a name..." style="margin-top: 8px;">
            </div>
            <div class="form-group">
                <label>Amount (THB)</label>
                <input type="number" id="transfer-amount" value="500" min="1">
            </div>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeModal('transfer-modal')">Cancel</button>
                <button class="btn-submit" onclick="submitTransfer()">Transfer</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="recurring-modal">
        <div class="modal-content">
            <h2>🔄 Recurring Payment</h2>
            <div class="form-group">
                <label>Select Amount (THB)</label>
                <div class="quick-actions">
                    <button class="quick-btn" onclick="setRecurringAmount(500)">฿500</button>
                    <button class="quick-btn" onclick="setRecurringAmount(1000)">฿1,000</button>
                    <button class="quick-btn" onclick="setRecurringAmount(5000)">฿5,000</button>
                </div>
                <input type="number" id="rec-amount" value="1000" min="1" style="margin-top: 8px;">
            </div>
            <div class="form-group">
                <label>Recipient Name</label>
                <input type="text" id="rec-recipient" value="Mom">
            </div>
            <div class="form-group">
                <label>Start Date</label>
                <input type="date" id="rec-date">
            </div>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeModal('recurring-modal')">Cancel</button>
                <button class="btn-submit" onclick="submitRecurring()">Schedule</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="split-method-modal">
        <div class="modal-content">
            <h2>🍕 Split Bill</h2>
            <p style="font-size:13px; color:#666; margin-bottom:16px;">How would you like to split the bill?</p>
            <div class="quick-actions" style="flex-direction: column; gap:8px;">
                <button class="quick-btn" style="padding:12px; font-size:14px; justify-content:center;" onclick="openSplitDetailsModal('equal')">⚖️ Equal Share</button>
                <button class="quick-btn" style="padding:12px; font-size:14px; justify-content:center;" onclick="openSplitDetailsModal('percentage')">📊 Percentage</button>
            </div>
            <div class="modal-buttons" style="margin-top:16px;">
                <button class="btn-cancel" onclick="closeModal('split-method-modal')">Cancel</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="split-details-modal">
        <div class="modal-content">
            <h2 id="split-details-title">🍕 Equal Split</h2>
            <input type="hidden" id="split-type-hidden" value="equal">
            <div class="form-group">
                <label>Total Amount (THB)</label>
                <div class="quick-actions">
                    <button class="quick-btn" onclick="setSplitAmount(500)">฿500</button>
                    <button class="quick-btn" onclick="setSplitAmount(1500)">฿1,500</button>
                    <button class="quick-btn" onclick="setSplitAmount(3000)">฿3,000</button>
                </div>
                <input type="number" id="split-amount" value="1500" min="1" style="margin-top: 8px;">
            </div>
            <div class="form-group">
                <label>Select Friends</label>
                <div class="quick-actions" id="split-contacts">
                    <button class="quick-btn" onclick="toggleSplitContact('Mom', this)">👩 Mom</button>
                    <button class="quick-btn" onclick="toggleSplitContact('Sarah Work', this)">👩‍💼 Sarah Work</button>
                    <button class="quick-btn" onclick="toggleSplitContact('Sarah Sister', this)">👧 Sarah Sister</button>
                </div>
            </div>
            <div class="form-group" id="pct-group" style="display: none;">
                <label>Percentages (comma separated, e.g. 60,40)</label>
                <input type="text" id="split-percentages" placeholder="e.g. 60,40">
            </div>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeModal('split-details-modal')">Back</button>
                <button class="btn-submit" onclick="submitSplitBill()">Split Bill</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="savingsModal">
        <div class="modal-content">
            <h2>🎯 Setup Savings Goal</h2>
            <div class="form-group">
                <label>Target Amount (THB)</label>
                <input type="number" id="goalAmount" placeholder="e.g. 10000">
            </div>
            <div class="form-group">
                <label>Top Priority 1</label>
                <select id="prio1">
                    <option value="food">Food</option>
                    <option value="housing">Housing</option>
                    <option value="transportation">Transport</option>
                    <option value="entertainment">Entertainment</option>
                </select>
            </div>
            <div class="form-group">
                <label>Top Priority 2</label>
                <select id="prio2">
                    <option value="housing">Housing</option>
                    <option value="food">Food</option>
                    <option value="transportation">Transport</option>
                    <option value="entertainment">Entertainment</option>
                </select>
            </div>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeModal('savingsModal')">Cancel</button>
                <button class="btn-submit" onclick="submitSavingsGoal()">Set Goal</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="invest-modal">
        <div class="modal-content">
            <h2>📈 AI Smart Investment</h2>
            <p style="font-size:12px; color:#666; margin-bottom:16px;">AI will analyze real financial data to build a portfolio.</p>
            <div class="form-group">
                <label>Investment Budget (THB)</label>
                <input type="number" id="inv-budget" value="10000" min="100">
            </div>
            <div class="form-group">
                <label>Risk Level</label>
                <select id="inv-risk">
                    <option value="Low">Low (Conservative)</option>
                    <option value="Medium" selected>Medium (Balanced)</option>
                    <option value="High">High (Aggressive)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Your Goal</label>
                <input type="text" id="inv-goal" placeholder="e.g. Long-term growth" value="Long-term growth">
            </div>
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeModal('invest-modal')">Cancel</button>
                <button class="btn-submit" onclick="submitInvestment()">Analyze</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="block-card-modal">
        <div class="modal-content">
            <h2>🔒 Block a Card</h2>
            <p style="font-size:13px; color:#666; margin-bottom:16px;">Select the card you want to block:</p>
            <div class="quick-actions" style="flex-direction: column; gap:8px;" id="block-card-list">
                <button class="quick-btn" style="padding:12px; font-size:14px; justify-content:flex-start;" onclick="submitBlockCard('4111-1111-1111-1111', 'Debit Card (****1111)')">💳 Debit Card (****1111)</button>
                <button class="quick-btn" style="padding:12px; font-size:14px; justify-content:flex-start;" onclick="submitBlockCard('5555-5555-5555-5555', 'Credit Card (****5555)')">💳 Credit Card (****5555)</button>
            </div>
            <div class="modal-buttons" style="margin-top:16px;">
                <button class="btn-cancel" onclick="closeModal('block-card-modal')">Cancel</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="cancel-card-modal">
        <div class="modal-content">
            <h2>❌ Cancel a Card</h2>
            <p style="font-size:13px; color:#666; margin-bottom:16px;">Warning: This action is permanent. Select the card to cancel:</p>
            <div class="quick-actions" style="flex-direction: column; gap:8px;" id="cancel-card-list">
                <button class="quick-btn" style="padding:12px; font-size:14px; justify-content:flex-start;" onclick="submitCancelCard(1, 'Debit Card (****1111)')">💳 Debit Card (****1111)</button>
                <button class="quick-btn" style="padding:12px; font-size:14px; justify-content:flex-start;" onclick="submitCancelCard(2, 'Credit Card (****5555)')">💳 Credit Card (****5555)</button>
            </div>
            <div class="modal-buttons" style="margin-top:16px;">
                <button class="btn-cancel" onclick="closeModal('cancel-card-modal')">Cancel</button>
            </div>
        </div>
    </div>

    <!-- OTP Modal -->
    <div class="modal-overlay" id="otp-modal">
        <div class="modal-content otp-modal-content">
            <div class="otp-icon-wrap">🔐</div>
            <h2>Verification Required</h2>
            <p class="otp-subtitle">Enter the 6-digit code sent to your phone</p>
            <div class="otp-inputs">
                <input type="text" maxlength="1" inputmode="numeric" id="otp-1" autocomplete="one-time-code">
                <input type="text" maxlength="1" inputmode="numeric" id="otp-2">
                <input type="text" maxlength="1" inputmode="numeric" id="otp-3">
                <input type="text" maxlength="1" inputmode="numeric" id="otp-4">
                <input type="text" maxlength="1" inputmode="numeric" id="otp-5">
                <input type="text" maxlength="1" inputmode="numeric" id="otp-6">
            </div>
            <div class="otp-hint">💡 Demo code: <b>123456</b></div>
            <div class="otp-error" id="otp-error"></div>
            <div class="otp-resend">
                Didn't receive the code? <a onclick="resendOTP()">Resend</a>
            </div>
            <div class="modal-buttons" style="margin-top: 0;">
                <button class="btn-cancel" onclick="cancelOTP()">Cancel</button>
                <button class="btn-submit" id="otp-submit" onclick="submitOTP()">Verify</button>
            </div>
        </div>
    </div>

    <!-- ============ BOTTOM NAV ============ -->
    <nav class="bottom-nav">
        <button class="nav-item active" id="nav-home" type="button" onclick="showDashboard()">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 11l9-8 9 8"></path><path d="M5 10v10h14V10"></path>
            </svg>
            Home
        </button>
        <button class="nav-item" id="nav-accounts" type="button" onclick="openChat('Show accounts')">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 10h18"></path>
            </svg>
            Accounts
        </button>
        <button class="nav-item nav-ai" id="nav-ai" type="button" onclick="openChat()">
            <div class="ai-orb">✦</div>
            <span>AI</span>
        </button>
        <button class="nav-item" id="nav-insights" type="button" onclick="openChat('Show insights')">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 19V9"></path><path d="M10 19V5"></path><path d="M16 19v-7"></path><path d="M22 19H2"></path>
            </svg>
            Insights
        </button>
        <button class="nav-item" id="nav-more" type="button" onclick="openChat('Show more')">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="5" cy="12" r="1"></circle><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle>
            </svg>
            More
        </button>
    </nav>
</div>

<script>
    const dashboardScreen = document.getElementById('dashboardScreen');
    const chatScreen = document.getElementById('chatScreen');
    const chat = document.getElementById('chat');
    const input = document.getElementById('input');
    const sendBtn = document.getElementById('send');

    let pendingIntent = null;
    let pendingMFA = false;
    let selectedSplitContacts = [];

    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') send();
    });

    function setActiveNav(id) {
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        const el = document.getElementById(id);
        if (el) el.classList.add('active');
    }
    function showDashboard() {
        dashboardScreen.style.display = 'block';
        chatScreen.classList.remove('open');
        setActiveNav('nav-home');
    }
    function openChat(prompt) {
        dashboardScreen.style.display = 'none';
        chatScreen.classList.add('open');
        setActiveNav('nav-ai');
        setTimeout(() => {
            if (prompt) { input.value = prompt; send(); }
            else { input.focus(); }
        }, 80);
    }
    function closeChat() { showDashboard(); }

    // ===== Modals =====
    function openTransferModal() { document.getElementById('transfer-modal').style.display = 'flex'; }
    function openRecurringModal() {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        document.getElementById('rec-date').value = tomorrow.toISOString().split('T')[0];
        document.getElementById('recurring-modal').style.display = 'flex';
    }
    function openSplitMethodModal() { document.getElementById('split-method-modal').style.display = 'flex'; }
    function openSplitDetailsModal(type) {
        document.getElementById('split-method-modal').style.display = 'none';
        document.getElementById('split-details-modal').style.display = 'flex';
        document.getElementById('split-type-hidden').value = type;
        document.getElementById('split-details-title').innerText = type === 'equal' ? '🍕 Equal Split' : '📊 Percentage Split';
        document.getElementById('pct-group').style.display = type === 'percentage' ? 'block' : 'none';
        selectedSplitContacts = [];
        document.querySelectorAll('#split-contacts .quick-btn').forEach(btn => btn.classList.remove('active'));
    }
    function closeModal(modalId) { document.getElementById(modalId).style.display = 'none'; }
    function selectRecipient(name, btn) {
        document.getElementById('transfer-recipient').value = name;
        document.querySelectorAll('#transfer-contacts .quick-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    function setRecurringAmount(amount) { document.getElementById('rec-amount').value = amount; }
    function setSplitAmount(amount) { document.getElementById('split-amount').value = amount; }
    function toggleSplitContact(name, btn) {
        if (selectedSplitContacts.includes(name)) {
            selectedSplitContacts = selectedSplitContacts.filter(c => c !== name);
            btn.classList.remove('active');
        } else {
            selectedSplitContacts.push(name);
            btn.classList.add('active');
        }
    }
    function submitTransfer() {
        const recipient = document.getElementById('transfer-recipient').value;
        const amount = document.getElementById('transfer-amount').value;
        if (!recipient || !amount) { alert("Please fill all fields"); return; }
        closeModal('transfer-modal');
        quickSend(`Transfer ${amount} to ${recipient}`);
    }
    function submitRecurring() {
        const amount = document.getElementById('rec-amount').value;
        const recipient = document.getElementById('rec-recipient').value;
        const date = document.getElementById('rec-date').value;
        if (!amount || !recipient || !date) { alert("Please fill all fields"); return; }
        closeModal('recurring-modal');
        quickSend(`Schedule ${amount} to ${recipient} on ${date} at 09:00`);
    }
    function submitSplitBill() {
        const amount = document.getElementById('split-amount').value;
        const type = document.getElementById('split-type-hidden').value;
        const pcts = document.getElementById('split-percentages').value.trim();
        if (!amount) { alert("Please enter an amount"); return; }
        if (selectedSplitContacts.length === 0) { alert("Please select at least one friend"); return; }
        closeModal('split-details-modal');
        const contactsStr = selectedSplitContacts.join(', ');
        if (type === 'percentage') {
            if (!pcts) { alert("Please enter percentages (e.g. 60,40)"); return; }
            quickSend(`Split ${amount} with ${contactsStr} using percentage ${pcts}`);
        } else {
            quickSend(`Split ${amount} with ${contactsStr} using equal`);
        }
    }
    function openSavingsModal() { document.getElementById('savingsModal').style.display = 'flex'; }
    function submitSavingsGoal() {
        const amount = document.getElementById('goalAmount').value;
        const p1 = document.getElementById('prio1').value;
        const p2 = document.getElementById('prio2').value;
        if (!amount || amount <= 0) { alert("Please enter a valid amount"); return; }
        closeModal('savingsModal');
        quickSend(`set savings goal ${amount} priorities ${p1},${p2}`);
    }
    function openInvestModal() { document.getElementById('invest-modal').style.display = 'flex'; }
    function submitInvestment() {
        const budget = document.getElementById('inv-budget').value;
        const risk = document.getElementById('inv-risk').value;
        const goal = document.getElementById('inv-goal').value;
        if (!budget || !goal) { alert("Please fill all fields"); return; }
        closeModal('invest-modal');
        quickSend(`invest ${budget} risk ${risk} goal ${goal}`);
    }
    function openBlockCardModal() { document.getElementById('block-card-modal').style.display = 'flex'; }
    function submitBlockCard(cardNumber) {
        closeModal('block-card-modal');
        quickSend(`Block card ${cardNumber}`);
    }
    function openCancelCardModal() { document.getElementById('cancel-card-modal').style.display = 'flex'; }
    function submitCancelCard(cardId) {
        closeModal('cancel-card-modal');
        quickSend(`Cancel card ${cardId}`);
    }

        // ===== OTP Modal =====
    let otpModalOpen = false;

    function showToast(msg) {
        let toast = document.getElementById('toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast';
            toast.className = 'toast';
            document.querySelector('.app').appendChild(toast);
        }
        toast.innerHTML = msg;
        toast.classList.remove('show');
        void toast.offsetWidth;
        toast.classList.add('show');
        clearTimeout(toast._t);
        toast._t = setTimeout(() => toast.classList.remove('show'), 3200);
    }

    function showPushNotification(otpCode) {
        const pn = document.getElementById('push-notification');
        pn.innerHTML = `
            <div class="pn-icon">🏦</div>
            <div class="pn-content">
                <div class="pn-header">
                    <span>Banking AI</span>
                    <span>now</span>
                </div>
                <div class="pn-title">Verification Code</div>
                <div class="pn-body">Your OTP is <b>${otpCode}</b>. Do not share this code.</div>
            </div>
        `;
        // Reset animation
        pn.classList.remove('show');
        void pn.offsetWidth;
        pn.classList.add('show');

        // ซ่อนหลัง 4 วินาที
        if (pn._timeout) clearTimeout(pn._timeout);
        pn._timeout = setTimeout(() => {
            pn.classList.remove('show');
        }, 4000);
    }

    function showOTPModal(otpCode = null) {
    if (!chatScreen.classList.contains('open')) {
        dashboardScreen.style.display = 'none';
        chatScreen.classList.add('open');
        setActiveNav('nav-ai');
    }
    otpModalOpen = true;
    pendingMFA = true;
    document.getElementById('otp-modal').style.display = 'flex';
    document.getElementById('input').disabled = true;
    document.getElementById('send').disabled = true;
    document.getElementById('otp-error').textContent = '';
    
    // อัปเดต Demo code ใน Modal ให้ตรงกับที่ได้รับ (ถ้ามี)
    const hintEl = document.querySelector('.otp-hint');
    if (otpCode && hintEl) {
        hintEl.innerHTML = `💡 Demo code: <b>${otpCode}</b>`;
    }

    for (let i = 1; i <= 6; i++) {
        const el = document.getElementById('otp-' + i);
        el.value = '';
        el.classList.remove('filled');
    }
    setTimeout(() => document.getElementById('otp-1').focus(), 350);
}

    function hideOTPModal() {
        otpModalOpen = false;
        document.getElementById('otp-modal').style.display = 'none';
        document.getElementById('input').disabled = false;
        document.getElementById('send').disabled = false;
    }

    function setupOTPInputs() {
        for (let i = 1; i <= 6; i++) {
            const el = document.getElementById('otp-' + i);
            el.addEventListener('input', (e) => {
                const val = e.target.value.replace(/\D/g, '').slice(-1);
                e.target.value = val;
                el.classList.toggle('filled', !!val);
                if (val && i < 6) document.getElementById('otp-' + (i + 1)).focus();
                const allFilled = [...Array(6)].every((_, idx) => document.getElementById('otp-' + (idx+1)).value);
                if (allFilled) setTimeout(submitOTP, 150);
            });
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && i > 1) {
                    document.getElementById('otp-' + (i - 1)).focus();
                } else if (e.key === 'Enter') {
                    submitOTP();
                }
            });
            el.addEventListener('paste', (e) => {
                e.preventDefault();
                const paste = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
                for (let j = 0; j < 6; j++) {
                    const box = document.getElementById('otp-' + (j + 1));
                    box.value = paste[j] || '';
                    box.classList.toggle('filled', !!paste[j]);
                }
                if (paste.length >= 1) {
                    document.getElementById('otp-' + Math.min(paste.length + 1, 6)).focus();
                }
            });
        }
    }

    function cancelOTP() {
        hideOTPModal();
        pendingMFA = false;
        addMessage('❌ Verification cancelled', 'ai');
    }

    function resendOTP() {
        showToast('📱 New code sent!');
        for (let i = 1; i <= 6; i++) {
            const el = document.getElementById('otp-' + i);
            el.value = '';
            el.classList.remove('filled');
        }
        document.getElementById('otp-error').textContent = '';
        document.getElementById('otp-1').focus();
    }

    async function submitOTP() {
        const otp = [...Array(6)].map((_, i) => document.getElementById('otp-' + (i+1)).value).join('');
        const errEl = document.getElementById('otp-error');
        if (otp.length !== 6) { errEl.textContent = 'Please enter all 6 digits'; return; }

        const btn = document.getElementById('otp-submit');
        btn.disabled = true;
        btn.textContent = 'Verifying...';
        errEl.textContent = '';

        try {
            const res = await fetch('/api/verify-otp', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: 1, otp: otp})
            });
            const data = await res.json();

            if (!res.ok) {
                errEl.textContent = data.detail || 'Verification failed';
                btn.disabled = false; btn.textContent = 'Verify';
                return;
            }
            if (data.status === 'error') {
                errEl.textContent = data.reply || 'Invalid code. Please try again.';
                btn.disabled = false; btn.textContent = 'Verify';
                for (let i = 1; i <= 6; i++) {
                    const el = document.getElementById('otp-' + i);
                    el.value = ''; el.classList.remove('filled');
                }
                document.getElementById('otp-1').focus();
                return;
            }
            // Success
            hideOTPModal();
            pendingMFA = false;
            addMessage('🔐 ' + otp.replace(/./g, '•'), 'user');
            addMessage(data.reply, 'ai', false, data.data);
            showToast('✅ Verified successfully');
        } catch (e) {
            errEl.textContent = 'Error: ' + e.message;
            showToast('❌ Network error');
        }
        btn.disabled = false;
        btn.textContent = 'Verify';
    }

    // init on load
    setupOTPInputs();

    // ===== Parsers & Charts =====
    function parseInvestmentText(text) {
        const assets = [];
        const lines = text.split('\\n');
        let currentAsset = null;
        for (let line of lines) {
            if (line.trim().startsWith('• **')) {
                const match = line.match(/• \\*\\*(.*?)\\*\\* \\((.*?)\\)/);
                if (match) { currentAsset = { name: match[2], symbol: match[1], alloc: 0 }; assets.push(currentAsset); }
            } else if (line.includes('Alloc:') && currentAsset) {
                const match = line.match(/Alloc:\\s*([\\d.]+)%/);
                if (match) currentAsset.alloc = parseFloat(match[1]);
            }
        }
        return assets;
    }
    function parseSubText(text) {
        const subs = [];
        const lines = text.split('\\n');
        for (let line of lines) {
            const match = line.match(/• \\*\\*(.*?)\\*\\* \\(฿(\\d+)\\/mo\\)/);
            if (match) subs.push({ name: match[1], cost: parseFloat(match[2]) });
        }
        return subs;
    }
    function initChart(canvasId, labels, data, colors) {
        const el = document.getElementById(canvasId);
        if (!el) return;
        const ctx = el.getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 4 }] },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '70%',
                plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10, family: 'sans-serif' } } } }
            }
        });
    }

    function escapeHtml(str) {
        return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    function formatText(text) {
        return escapeHtml(text)
            .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
            .replace(/\\*(.*?)\\*/g, '<i>$1</i>')
            .replace(/\\\\n/g, '<br>')
            .replace(/\\n/g, '<br>');
    }

    // ===== Data tables =====
    function renderTransactionsTable(data) {
        if (!data || !Array.isArray(data) || data.length === 0) return '';
        let html = `<table class="data-table"><thead><tr><th>Amount</th><th>Category</th><th class="right">Recipient</th></tr></thead><tbody>`;
        data.forEach(tx => {
            html += `<tr><td>฿${Math.floor(tx.amount).toLocaleString()}</td><td><span class="tx-category">${(tx.category||'transfer').charAt(0).toUpperCase()+(tx.category||'transfer').slice(1)}</span></td><td class="right">${tx.note || '-'}</td></tr>`;
        });
        return html + `</tbody></table>`;
    }
    function renderCardsTable(data) {
        if (!data || !Array.isArray(data) || data.length === 0) return '';
        let html = `<table class="data-table"><thead><tr><th>Name</th><th>Card Number</th><th class="right">Status</th></tr></thead><tbody>`;
        data.forEach(c => {
            const statusClass = c.status === 'active' ? 'status-active' : (c.status === 'blocked' ? 'status-blocked' : 'status-expired');
            html += `<tr><td>${c.card_type || '-'}</td><td>${c.card_number || '-'}</td><td class="right"><span class="status-badge ${statusClass}">${c.status}</span></td></tr>`;
        });
        return html + `</tbody></table>`;
    }
    function renderSubscriptionsTable(data) {
        if (!data || !Array.isArray(data) || data.length === 0) return '';
        let html = `<table class="data-table"><thead><tr><th>Name</th><th class="right">Amount</th></tr></thead><tbody>`;
        data.forEach(s => { html += `<tr><td>${s.merchant_name}</td><td class="right">฿${s.amount}</td></tr>`; });
        return html + `</tbody></table>`;
    }
    function renderContactsTable(data) {
        if (!data || !Array.isArray(data) || data.length === 0) return '';
        let html = `<table class="data-table"><thead><tr><th>Name</th><th class="right">Tel</th></tr></thead><tbody>`;
        data.forEach(b => { html += `<tr><td>${b.full_name} (${b.nickname})</td><td class="right">${b.phone || '-'}</td></tr>`; });
        return html + `</tbody></table>`;
    }

    // ===== Special Cards =====
    function renderBalanceCard(balance, currency="THB") {
        return `
        <div class="balance-visual-card">
            <div class="bv-left">
                <div class="bv-label">Total balance</div>
                <div class="bv-amount">฿${parseFloat(balance).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                <div class="bv-delta"><b>↗ +3.2%</b> vs. last month</div>
            </div>
        </div>`;
    }

    function renderActionCard(text) {
        const actionText = text.split("Confirm?")[0].trim().replace(/\\n/g, '<br>');
        return `
        <div class="action-card">
            <div class="action-title">⚠️ Action Required</div>
            <div class="action-desc">${actionText}</div>
            <div class="action-buttons">
                <button class="action-btn action-yes" onclick="this.innerHTML='✅ Confirmed'; this.disabled=true; input.value='y'; send();">✅ Confirm</button>
                <button class="action-btn action-no" onclick="this.innerHTML='❌ Cancelled'; this.disabled=true; input.value='n'; send();">❌ Cancel</button>
            </div>
        </div>`;
    }

    function renderSuccessCard(text) {
        const amtMatch = text.match(/Successfully invested ฿([\\d,.]+)/);
        const balMatch = text.match(/New balance: ฿([\\d,.]+)/);
        const symbolsMatch = text.match(/portfolio \\((.*?)\\)/);
        const amount = amtMatch ? amtMatch[1] : "0";
        const balance = balMatch ? balMatch[1] : "0";
        const symbols = symbolsMatch ? symbolsMatch[1] : "";
        return `
        <div class="success-card">
            <div class="success-header">
                <span style="font-size:24px;">🎉</span>
                <div class="success-title">Investment Successful!</div>
            </div>
            <div class="success-row"><span>Invested Amount</span> <b>฿${amount}</b></div>
            <div class="success-row"><span>New Cash Balance</span> <b>฿${balance}</b></div>
            <div class="success-divider"></div>
            <div class="success-footer">
                <div style="font-weight:600; color:var(--navy); margin-bottom:4px;">Assets Added:</div>
                <div style="font-size:13px; color:#666;">${symbols}</div>
                <button class="btn-check-portfolio" onclick="quickSend('Show portfolio')">💼 View My Portfolio</button>
            </div>
        </div>`;
    }

    function renderPortfolioCard() {
        const portfolio = JSON.parse(localStorage.getItem('ai_portfolio') || '[]');
        if (portfolio.length === 0) {
            return `<div style="background:white; padding:16px; border-radius:14px; color:#333;">You don't have any AI portfolio yet. Try saying "invest 10000 risk Medium goal Long-term growth"!</div>`;
        }
        const grouped = {};
        portfolio.forEach(p => {
            if(!p || !p.symbol || p.symbol === 'undefined' || isNaN(p.shares) || isNaN(p.cost)) return;
            if(!grouped[p.symbol]) grouped[p.symbol] = { ...p, totalShares: 0, totalCost: 0 };
            grouped[p.symbol].totalShares += p.shares;
            grouped[p.symbol].totalCost += p.cost;
        });
        const keys = Object.keys(grouped);
        if (keys.length === 0) {
            return `<div style="background:white; padding:16px; border-radius:14px; color:#333;">Your portfolio is empty or corrupted. Please clear localStorage and try again.</div>`;
        }
        const listHtml = keys.map(sym => {
            const p = grouped[sym];
            return `
            <div class="portfolio-item">
                <div class="portfolio-item-left">
                    <div class="portfolio-item-symbol">${p.symbol}</div>
                    <div class="portfolio-item-name">${p.name}</div>
                </div>
                <div class="portfolio-item-right">
                    <div class="portfolio-item-value">฿${p.totalCost.toLocaleString('en-US', {minimumFractionDigits: 2})}</div>
                    <div class="portfolio-item-pnl">${p.totalShares} shares @ ฿${p.price}</div>
                </div>
            </div>`;
        }).join('');
        return `
        <div class="portfolio-card">
            <div class="portfolio-header">
                <div class="portfolio-title">💼 Tracked Portfolio</div>
            </div>
            <div class="portfolio-list">${listHtml}</div>
        </div>`;
    }

    function renderReceiptCard(text) {
        const amountMatch = text.match(/฿([\\d,]+)/);
        const amount = amountMatch ? amountMatch[1] : "0";
        const noteMatch = text.match(/for (.*?)\\./);
        const note = noteMatch ? noteMatch[1] : "Bill";
        const friendsMatch = text.match(/Split with: (.*)/);
        const friends = friendsMatch ? friendsMatch[1] : "";

        if (text.includes("Each owes:")) {
            const eachOwesMatch = text.match(/Each owes: ฿([\\d,.]+)/);
            const eachOwes = eachOwesMatch ? eachOwesMatch[1] : "0";
            return `
            <div class="receipt-card">
                <div class="receipt-header">🧾 Split Bill Receipt</div>
                <div class="receipt-row"><span>Note:</span> <b>${note}</b></div>
                <div class="receipt-row"><span>Total Amount:</span> <b>฿${amount}</b></div>
                <div class="receipt-divider"></div>
                <div class="receipt-row"><span>Each owes:</span> <b>฿${eachOwes}</b></div>
                <div class="receipt-footer" style="margin-top:12px;">Split with: ${friends}</div>
            </div>`;
        } else if (text.includes("Friend 1:")) {
            const regex = /- Friend \\d+: (\\d+)% \\(฿([\\d,.]+)\\)/g;
            let match;
            const percentages = [];
            let i = 1;
            while ((match = regex.exec(text)) !== null) {
                percentages.push(`Friend ${i}: ${match[1]}% (฿${match[2]})`);
                i++;
            }
            return `
            <div class="receipt-card">
                <div class="receipt-header">🧾 Split Bill (Percentage)</div>
                <div class="receipt-row"><span>Note:</span> <b>${note}</b></div>
                <div class="receipt-row"><span>Total Amount:</span> <b>฿${amount}</b></div>
                <div class="receipt-list">${percentages.map(p => `<div>${p}</div>`).join('')}</div>
                <div class="receipt-divider"></div>
                <div class="receipt-footer">Split with: ${friends}</div>
            </div>`;
        }
        return formatText(text);
    }

    function renderTransferBill(text) {
        const amountMatch = text.match(/Transferred ฿([\\d,]+)/);
        const amount = amountMatch ? amountMatch[1] : "0";
        const toMatch = text.match(/to (.*?)\\n/);
        const to = toMatch ? toMatch[1] : "Recipient";
        const balMatch = text.match(/New balance: ฿([\\d,]+)/);
        const newBalance = balMatch ? balMatch[1] : "0";
        let extraText = "";
        const alertMatch = text.match(/(🚨.*)/s);
        if (alertMatch) {
            extraText = `<div style="margin-top:15px; font-size:11px; color:#d97706; background:#fffbeb; padding:10px; border-radius:8px;">${alertMatch[1].replace(/\\n/g, '<br>')}</div>`;
        }
        const now = new Date();
        const dateStr = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
        const timeStr = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        return `
        <div class="ebill-card">
            <div class="ebill-header">
                <div class="ebill-title">🧾 Transfer e-Bill</div>
                <div class="ebill-status">✅ Completed</div>
            </div>
            <div class="ebill-amount">฿${amount}.00</div>
            <div class="ebill-row"><span>To</span> <span>${to}</span></div>
            <div class="ebill-row"><span>From</span> <span>Savings Account</span></div>
            <div class="ebill-row"><span>Date</span> <span>${dateStr} ${timeStr}</span></div>
            <div class="ebill-row"><span>New Balance</span> <span>฿${newBalance}.00</span></div>
            ${extraText}
            <div class="ebill-footer">
                Thank you for using Banking AI
                <div class="ebill-barcode"></div>
            </div>
        </div>`;
    }

    function renderOrchestrationCard(text) {
        let bodyText = text.replace("🔄 **End-of-Month Financial Reset**", "").replace("⚠️ Proceed to execute this full financial reset? [y/n]", "").trim();
        let formattedText = bodyText
            .replace(/1️⃣ \\*\\*(.*?)\\*\\*/g, '<div style="margin-top:12px; font-weight:700; color:var(--navy);">1️⃣ $1</div>')
            .replace(/2️⃣ \\*\\*(.*?)\\*\\*/g, '<div style="margin-top:12px; font-weight:700; color:var(--navy);">2️⃣ $1</div>')
            .replace(/3️⃣ \\*\\*(.*?)\\*\\*/g, '<div style="margin-top:12px; font-weight:700; color:var(--navy);">3️⃣ $1</div>')
            .replace(/4️⃣ \\*\\*(.*?)\\*\\*/g, '<div style="margin-top:12px; font-weight:700; color:var(--navy);">4️⃣ $1</div>')
            .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
            .replace(/\\n/g, '<br>');
        return `
        <div class="action-card" style="background:white; border:2px solid #22c55e;">
            <div class="action-title" style="color:#166534; font-size:16px;">🔄 Automated Financial Reset</div>
            <div class="action-desc" style="font-size:13px;">${formattedText}</div>
            <div class="action-buttons" style="margin-top:16px;">
                <button class="action-btn" style="background:#22c55e; color:white;" onclick="this.innerHTML='✅ Executing...'; this.disabled=true; input.value='y'; send();">✅ Execute All</button>
                <button class="action-btn action-no" onclick="this.innerHTML='❌ Cancelled'; this.disabled=true; input.value='n'; send();">❌ Cancel</button>
            </div>
        </div>`;
    }

    // ===== addMessage (detect special cards) =====
    function addMessage(text, sender, showConfirmButtons = false, data = null) {
        const div = document.createElement('div');
        div.className = 'message ' + sender;

        if (sender === 'ai') {
            const avatar = document.createElement('div');
            avatar.className = 'ai-avatar';
            avatar.textContent = '🤖';
            div.appendChild(avatar);
        }

        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        const isBalanceData = data && data.balance !== undefined && sender === 'ai';
        const isInvestment = text && text.includes("AI Investment Analysis") && sender === 'ai';
        const isInvestmentSuccess = text && text.includes("Investment Successful") && sender === 'ai';
        const isSubDashboard = text && text.includes("Subscription Dashboard") && sender === 'ai';
        const isReceipt = text && text.includes("Created split bill") && sender === 'ai';
        const isTransferBill = text && text.includes("✅ Transferred ฿") && text.includes("New balance") && sender === 'ai';
        const isConfirmAction = text && text.includes("Confirm? [y/n]") && sender === 'ai';
        const isCrossScenario = text && text.includes("End-of-Month Financial Reset") && sender === 'ai';
        const isPortfolio = data === 'PORTFOLIO';

        if (isCrossScenario) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            bubble.innerHTML = renderOrchestrationCard(text);
        }
        else if (isBalanceData) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.border = 'none';
            bubble.innerHTML = renderBalanceCard(data.balance, data.currency);
        }
        else if (isPortfolio) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            bubble.innerHTML = renderPortfolioCard();
        }
        else if (isConfirmAction) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            bubble.innerHTML = renderActionCard(text);
        }
        else if (isInvestment) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            const assets = parseInvestmentText(text);
            const cardId = 'chart-inv-' + Date.now();
            let formattedText = text.replace(/🤖 \\*\\*AI Investment Analysis.*\\n/, '')
                .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
                .replace(/\\*(.*?)\\*/g, '<i>$1</i>')
                .split('\\n').join('<br>');
            bubble.innerHTML = `
                <div class="chart-card">
                    <div class="chart-title">🤖 AI Investment Analysis</div>
                    <div class="chart-container"><canvas id="${cardId}"></canvas></div>
                    <div class="chart-text">${formattedText}</div>
                </div>`;
            setTimeout(() => initChart(cardId, assets.map(a => a.name), assets.map(a => a.alloc),
                ['#667eea','#764ba2','#f093fb','#f5576c','#4facfe']), 100);
        }
        else if (isInvestmentSuccess) {
            const lastAnalysis = JSON.parse(localStorage.getItem('last_investment') || '[]');
            if (lastAnalysis.length > 0) {
                let portfolio = JSON.parse(localStorage.getItem('ai_portfolio') || '[]');
                portfolio.push(...lastAnalysis);
                localStorage.setItem('ai_portfolio', JSON.stringify(portfolio));
            }
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            bubble.innerHTML = renderSuccessCard(text);
        }
        else if (isSubDashboard) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            const subs = parseSubText(text);
            const cardId = 'chart-sub-' + Date.now();
            let formattedText = text.replace(/📊 \\*\\*Subscription Dashboard\\*\\*\\n/, '')
                .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
                .replace(/\\*(.*?)\\*/g, '<i>$1</i>')
                .split('\\n').join('<br>');
            bubble.innerHTML = `
                <div class="chart-card">
                    <div class="chart-title">📊 Subscription Breakdown</div>
                    <div class="chart-container"><canvas id="${cardId}"></canvas></div>
                    <div class="chart-text">${formattedText}</div>
                </div>`;
            setTimeout(() => initChart(cardId, subs.map(s => s.name), subs.map(s => s.cost),
                ['#f093fb','#f5576c','#4facfe','#43e97b','#fa709a']), 100);
        }
        else if (isReceipt) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            bubble.innerHTML = renderReceiptCard(text);
        }
        else if (isTransferBill) {
            bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none';
            bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
            bubble.innerHTML = renderTransferBill(text);
        }
        else {
            if (text) {
                const textNode = document.createElement('div');
                textNode.innerHTML = formatText(text);
                bubble.appendChild(textNode);
            }
            if (data && Array.isArray(data) && data.length > 0 && sender === 'ai') {
                let tableHtml = '';
                if (data[0].card_number !== undefined) tableHtml = renderCardsTable(data);
                else if (data[0].merchant_name !== undefined) tableHtml = renderSubscriptionsTable(data);
                else if (data[0].phone !== undefined && data[0].nickname !== undefined) tableHtml = renderContactsTable(data);
                else if (data[0].amount !== undefined) tableHtml = renderTransactionsTable(data);
                if (tableHtml) {
                    const tableDiv = document.createElement('div');
                    tableDiv.innerHTML = tableHtml;
                    bubble.appendChild(tableDiv);
                }
            }
        }

        if (showConfirmButtons && !isConfirmAction && !isCrossScenario) {
            const btnDiv = document.createElement('div');
            btnDiv.className = 'confirm-buttons';
            const yesBtn = document.createElement('button');
            yesBtn.className = 'confirm-btn confirm-yes';
            yesBtn.textContent = '✅ Yes';
            yesBtn.onclick = () => { btnDiv.remove(); input.value = 'y'; send(); };
            const noBtn = document.createElement('button');
            noBtn.className = 'confirm-btn confirm-no';
            noBtn.textContent = '❌ No';
            noBtn.onclick = () => { btnDiv.remove(); input.value = 'n'; send(); };
            btnDiv.appendChild(yesBtn); btnDiv.appendChild(noBtn);
            bubble.appendChild(btnDiv);
        }

        if (isInvestment) {
            const lines = text.split('\\n');
            let currentObj = null;
            const purchases = [];
            for (let line of lines) {
                if (line.trim().startsWith('• **')) {
                    const m = line.match(/• \\*\\*(.*?)\\*\\* \\((.*?)\\) - ฿([\\d,.]+)/);
                    if (m) currentObj = { symbol: m[1].trim(), name: m[2].trim(), price: parseFloat(m[3].replace(/,/g,'')) };
                } else if (line.includes('Alloc:') && currentObj) {
                    const m = line.match(/Alloc:\\s*([\\d.]+)%\\s*\\(฿([\\d,.]+)\\)\\s*->\\s*([\\d.]+)\\s*shares/);
                    if (m) {
                        currentObj.alloc = parseFloat(m[1]);
                        currentObj.cost = parseFloat(m[2].replace(/,/g,''));
                        currentObj.shares = parseFloat(m[3].replace(/,/g,''));
                        purchases.push(currentObj);
                        currentObj = null;
                    }
                }
            }
            localStorage.setItem('last_investment', JSON.stringify(purchases));
        }

        div.appendChild(bubble);
        if (sender === 'user') {
            const avatar = document.createElement('div');
            avatar.className = 'user-avatar';
            avatar.textContent = '🧔🏻‍♂️';
            div.appendChild(avatar);
        }
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'message ai';
        div.id = 'typing';
        const avatar = document.createElement('div');
        avatar.className = 'ai-avatar';
        avatar.textContent = '🤖';
        div.appendChild(avatar);
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.innerHTML = '<span class="typing">Thinking</span>';
        div.appendChild(bubble);
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }
    function hideTyping() {
        const el = document.getElementById('typing');
        if (el) el.remove();
    }
    function quickSend(text) { input.value = text; send(); }

    async function send() {
        const text = input.value.trim();
        if (!text) return;
        addMessage(text, 'user');
        input.value = '';
        sendBtn.disabled = true;

        // Portfolio intercept
        if (text.toLowerCase() === 'show portfolio' || text.toLowerCase() === 'ai portfolio') {
            showTyping();
            setTimeout(() => {
                hideTyping();
                addMessage("", 'ai', false, 'PORTFOLIO');
                sendBtn.disabled = false;
                input.focus();
            }, 600);
            return;
        }

        if (pendingIntent && (text.toLowerCase() === 'y' || text.toLowerCase() === 'yes')) {
            try {
                const res = await fetch('/api/confirm', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({intent: pendingIntent, user_id: 1})
                });
                const data = await res.json();
                if (!res.ok) {
                    addMessage('❌ ' + (data.detail || 'Error'), 'ai');
                } else if (data.requires_mfa) {
                    addMessage(data.reply, 'ai');
                    setTimeout(showOTPModal, 350);
                } else {
                    addMessage(data.reply, 'ai', false, data.data);
                }
                pendingIntent = null;
            } catch (e) { addMessage('❌ Error: ' + e.message, 'ai'); }
            sendBtn.disabled = false; input.focus(); return;
        }
        

        if (pendingIntent && (text.toLowerCase() === 'n' || text.toLowerCase() === 'no')) {
            addMessage('❌ Cancelled', 'ai');
            pendingIntent = null; sendBtn.disabled = false; input.focus(); return;
        }

        showTyping();
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text, user_id: 1})
            });
            const data = await res.json();
            hideTyping();
            if (data.requires_mfa) {
                pendingIntent = null;
                

                const otpMatch = data.reply.match(/(?:Demo OTP|OTP|Code)[^\d]*(\d{6})/i);
                const otpCode = otpMatch ? otpMatch[1] : '123456';

                let cleanReply = (data.reply || '').split('📱')[0].split('OTP sent')[0].trim();
    
                // ⭐ แสดงแค่ชื่อ Action ที่จะทำ (เช่น 🔴 HIGH-RISK ACTION Cancel card)
                addMessage(cleanReply + "\\n\\n🔒 Please verify the OTP in the popup.", 'ai');


                setTimeout(() => {
                    showPushNotification(otpCode);  // ⭐ แสดง Notification ลอยลงมา
                    showOTPModal(otpCode);          // ⭐ เปิด Modal พร้อมกรอก
                }, 300);
            } else if (data.requires_confirmation && data.intent) {
                pendingIntent = data.intent; pendingMFA = false;
                addMessage(data.reply, 'ai', true);
            } else {
                pendingIntent = null; pendingMFA = false;
                addMessage(res.ok ? data.reply : '❌ ' + (data.detail || 'Error'), 'ai', false, data.data);
            }
        } catch (e) {
            hideTyping();
            addMessage('❌ Error: ' + e.message, 'ai');
        }
        sendBtn.disabled = false; input.focus();
    }
</script>
</body>
</html>
"""