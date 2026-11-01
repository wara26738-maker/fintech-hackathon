# src/api/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any

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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏦 Banking AI Agent</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1rem;
        }
        .container {
            width: 100%; max-width: 520px; background: white; border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden;
            display: flex; flex-direction: column; height: 90vh; max-height: 750px; position: relative;
        }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.75rem 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .header h1 { font-size: 1rem; font-weight: 600; }
        .chat-area { flex: 1; overflow-y: auto; padding: 0.5rem; background: #f7f8fc; }
        
        .message { margin-bottom: 0.75rem; display: flex; animation: slideUp 0.3s ease-out; }
        @keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        
        .message.user { justify-content: flex-end; align-items: flex-start; gap: 0.5rem; }
        .message.ai { justify-content: flex-start; align-items: flex-start; gap: 0.5rem; }
        
        .ai-avatar, .user-avatar {
            width: 2rem; height: 2rem; border-radius: 50%; display: flex; align-items: center; justify-content: center;
            font-size: 1rem; flex-shrink: 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); line-height: 1;
        }
        .ai-avatar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .user-avatar { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }

        .bubble {
            max-width: 85%; padding: 0.75rem 1rem; border-radius: 16px; font-size: 0.875rem;
            line-height: 1.5; word-wrap: break-word; white-space: normal;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            width: fit-content; 
        }
        .user .bubble { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border-bottom-right-radius: 4px; 
        }
        .ai .bubble { 
            background: white; color: #333; 
            border-bottom-left-radius: 4px; 
            border: 1px solid #f0f0f0;
        }
        
        .ai .bubble b { color: #14264f; font-weight: 700; }

        /* ⭐ UI: Total Balance Card */
        .balance-card {
            background: #fbf9f6; border-radius: 20px; padding: 20px; margin-top: 4px;
            display: flex; justify-content: space-between; align-items: stretch;
            box-shadow: 0 4px 15px rgba(20,38,79,.06); width: 100%; min-width: 300px; border: 1px solid #ece8e2;
        }
        .balance-left { display: flex; flex-direction: column; justify-content: center; gap: 6px; }
        .balance-label { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #14264f; }
        .balance-amount { font-size: 28px; font-weight: 800; color: #14264f; letter-spacing: -0.5px; margin: 4px 0; }
        .balance-delta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #7c8190; margin-top: 4px; }
        .balance-delta b { display: flex; align-items: center; gap: 3px; color: #2f8f5b; font-weight: 600; background: #e6f1ea; border-radius: 8px; padding: 4px 8px; }
        .balance-right { position: relative; width: 120px; display: flex; align-items: flex-end; justify-content: flex-end; }
        .balance-chevron { position: absolute; top: 0; right: 0; color: #7c8190; }

        /* ⭐ UI: Chart Card */
        .chart-card {
            background: white; border-radius: 16px; padding: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-top: 4px; width: 100%; min-width: 300px;
        }
        .chart-title { font-size: 14px; font-weight: 700; color: #14264f; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }
        .chart-container { position: relative; height: 180px; width: 100%; margin-bottom: 12px; }
        .chart-text { font-size: 12px; color: #555; line-height: 1.5; white-space: normal; }

        /* ⭐ UI: Action Card (Confirmations) */
        .action-card {
            background: #fffbeb; border: 1px solid #fcd34d; border-radius: 16px; padding: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); width: 100%; min-width: 280px;
        }
        .action-title { font-size: 14px; font-weight: 800; color: #d97706; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
        .action-desc { font-size: 14px; color: #333; margin-bottom: 16px; line-height: 1.5; }
        .action-desc b { color: #b45309; }
        .action-buttons { display: flex; gap: 8px; }
        .action-btn { flex: 1; padding: 8px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; border: none; transition: 0.2s; }
        .action-yes { background: #10b981; color: white; }
        .action-yes:hover { background: #059669; }
        .action-no { background: white; border: 1px solid #d1d5db; color: #6b7280; }
        .action-no:hover { background: #f3f4f6; }

        /* ⭐ UI: Success Card */
        .success-card {
            background: white; border-radius: 20px; border: 2px solid #10b981;
            padding: 20px; box-shadow: 0 8px 25px rgba(16, 185, 129, 0.15);
            width: 100%; min-width: 300px;
        }
        .success-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
        .success-title { font-size: 16px; font-weight: 800; color: #14264f; }
        .success-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; color: #555; }
        .success-row b { color: #14264f; font-size: 15px; }
        .success-divider { border-top: 1px dashed #ccc; margin: 16px 0; }
        .success-footer { font-size: 13px; color: #333; text-align: center; }
        
        /* ⭐ ปุ่ม Check Portfolio ใน Success Card */
        .btn-check-portfolio {
            width: 100%; padding: 10px; margin-top: 16px;
            background: #10b981; color: white; border: none; border-radius: 12px;
            font-size: 14px; font-weight: 700; cursor: pointer;
            transition: all 0.2s; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);
        }
        .btn-check-portfolio:hover { background: #059669; transform: translateY(-2px); }

        /* ⭐ UI: E-Bill & Receipt */
        .receipt-card, .ebill-card {
            background: white; border-radius: 16px; padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px dashed #ccc;
            margin-top: 4px; width: 100%; min-width: 300px; position: relative;
        }
        .ebill-card { border: 1px solid #f0f0f0; box-shadow: 0 8px 25px rgba(0,0,0,0.08); border-radius: 20px; padding: 24px; }
        .receipt-header { font-size: 16px; font-weight: 800; color: #14264f; text-align: center; margin-bottom: 16px; letter-spacing: 1px; }
        .receipt-row { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 8px; color: #555; }
        .receipt-row b { color: #14264f; font-size: 15px; }
        .receipt-divider { border-top: 1px dashed #ccc; margin: 12px 0; }
        .receipt-footer { font-size: 13px; color: #7c8190; text-align: center; font-weight: 500; }
        .receipt-list { font-size: 13px; color: #444; margin-top: 8px; padding-left: 4px; }
        
        .ebill-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #ddd; padding-bottom: 12px; margin-bottom: 16px; }
        .ebill-title { font-size: 14px; font-weight: 700; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .ebill-status { background: #dcfce7; color: #16a34a; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; }
        .ebill-amount { font-size: 32px; font-weight: 800; color: #14264f; text-align: center; margin-bottom: 20px; letter-spacing: -1px; }
        .ebill-row { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 13px; color: #555; }
        .ebill-row span:last-child { font-weight: 600; color: #14264f; text-align: right; }
        .ebill-footer { border-top: 1px dashed #ddd; padding-top: 16px; margin-top: 16px; text-align: center; font-size: 11px; color: #999; }
        .ebill-barcode { height: 24px; width: 70%; margin: 10px auto 0; background: repeating-linear-gradient(90deg, #14264f, #14264f 2px, transparent 2px, transparent 4px, #14264f 4px, #14264f 5px, transparent 5px, transparent 9px); opacity: 0.6; border-radius: 2px; }

        /* ⭐ UI: AI Portfolio Card */
        .portfolio-card {
            background: linear-gradient(135deg, #14264f 0%, #1c3363 100%);
            color: white; border-radius: 20px; padding: 20px;
            box-shadow: 0 10px 30px rgba(20,38,79,0.4); width: 100%; min-width: 300px;
        }
        .portfolio-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .portfolio-title { font-size: 14px; font-weight: 700; color: #d3d9e8; text-transform: uppercase; letter-spacing: 1px; }
        .portfolio-list { display: flex; flex-direction: column; gap: 10px; }
        .portfolio-item { display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 12px; }
        .portfolio-item-left { display: flex; flex-direction: column; }
        .portfolio-item-symbol { font-size: 14px; font-weight: 700; }
        .portfolio-item-name { font-size: 11px; color: #9ca3af; }
        .portfolio-item-right { text-align: right; }
        .portfolio-item-value { font-size: 14px; font-weight: 700; }
        .portfolio-item-pnl { font-size: 11px; font-weight: 600; color: #9ca3af; }

        .data-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-size: 0.75rem; white-space: normal; }
        .data-table th { text-align: left; padding: 0.375rem 0.25rem; border-bottom: 1px solid #eee; color: #666; font-weight: 600; font-size: 0.6875rem; text-transform: uppercase; }
        .data-table th.right { text-align: right; }
        .data-table td { padding: 0.5rem 0.25rem; border-bottom: 1px solid #f9f9f9; }
        .data-table td.right { text-align: right; font-weight: 600; }
        .data-table tr:last-child td { border-bottom: none; }
        
        .tx-category { display: inline-block; padding: 0.125rem 0.375rem; background: #f0f2ff; color: #667eea; border-radius: 4px; font-size: 0.625rem; font-weight: 500; }
        .status-badge { display: inline-block; padding: 0.125rem 0.375rem; border-radius: 4px; font-size: 0.625rem; font-weight: 500; }
        .status-active { background: #dcfce7; color: #16a34a; }
        .status-blocked { background: #fee2e2; color: #dc2626; }
        .status-expired { background: #f3f4f6; color: #6b7280; }

        .input-area { padding: 0.75rem 1rem; background: white; border-top: 1px solid #eee; display: flex; gap: 0.5rem; }
        input[type="text"] { flex: 1; padding: 0.6rem 0.8rem; border: 1.5px solid #e0e0e0; border-radius: 20px; font-size: 0.8125rem; outline: none; transition: border-color 0.2s; }
        input[type="text"]:focus { border-color: #667eea; }
        button.primary { padding: 0.6rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 20px; font-size: 0.8125rem; font-weight: 600; cursor: pointer; transition: transform 0.15s; }
        button.primary:hover { transform: scale(1.03); }
        button.primary:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .typing { color: #999; font-size: 0.75rem; }
        .typing::after { content: '...'; animation: dots 1.5s steps(4, end) infinite; }
        @keyframes dots { 0%, 20% { content: ''; } 40% { content: '.'; } 60% { content: '..'; } 80%, 100% { content: '...'; } }

        .welcome-title { font-size: 0.875rem; font-weight: 700; color: #333; margin-bottom: 0.25rem; }
        .welcome-subtitle { font-size: 0.75rem; color: #666; margin-bottom: 0.75rem; }
        .feature-group { margin-bottom: 0.75rem; }
        .feature-label { display: block; font-size: 0.625rem; font-weight: 700; color: #667eea; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.25rem; }
        .quick-actions { display: flex; flex-wrap: wrap; gap: 0.3rem; }
        .quick-btn { padding: 0.3rem 0.5rem; background: #f0f2ff; color: #667eea; border: 1px solid #e0e3ff; border-radius: 8px; font-size: 0.6875rem; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all 0.2s; }
        .quick-btn:hover { background: #667eea; color: white; }
        .quick-btn.active { background: #667eea; color: white; }
        .welcome-tip { margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #eee; color: #888; font-size: 0.625rem; font-style: italic; }

        /* Modal CSS */
        .modal-overlay {
            display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; padding: 1rem;
        }
        .modal-content {
            background: white; padding: 1.5rem; border-radius: 20px; width: 100%; max-width: 350px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .modal-content h2 { font-size: 1.1rem; margin-bottom: 1rem; color: #333; }
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; font-size: 0.75rem; color: #666; margin-bottom: 0.3rem; font-weight: 600; }
        .form-group input, .form-group select {
            width: 100%; padding: 0.6rem; border: 1.5px solid #e0e0e0; border-radius: 8px; font-size: 0.85rem; outline: none; transition: border-color 0.2s;
        }
        .form-group input:focus, .form-group select:focus { border-color: #667eea; }
        .modal-buttons { display: flex; gap: 0.5rem; margin-top: 1.5rem; }
        .modal-buttons button { flex: 1; padding: 0.6rem; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: transform 0.1s; }
        .modal-buttons button:active { transform: scale(0.98); }
        .btn-cancel { background: #f3f4f6; color: #6b7280; }
        .btn-submit { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span style="font-size: 1.125rem;">🏦</span>
            <h1>Banking AI Agent</h1>
        </div>
        <div class="chat-area" id="chat">
            <div class="message ai">
                <div class="ai-avatar">🤖</div>
                <div class="bubble">
                    <div class="welcome-title">👋 Hello! I'm your AI banking assistant.</div>
                    <div class="welcome-subtitle">Click any button to try:</div>
                    <div class="feature-group">
                        <span class="feature-label">💸 Smart Transfers</span>
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
        <div class="input-area">
            <input type="text" id="input" placeholder="Type a message..." autofocus>
            <button class="primary" id="send" onclick="send()">Send</button>
        </div>

        <!-- Modals -->
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
                    <input type="text" id="transfer-recipient" placeholder="Or type a name..." style="margin-top: 0.5rem;">
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
                    <input type="number" id="rec-amount" value="1000" min="1" style="margin-top: 0.5rem;">
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
                <p style="font-size: 0.8125rem; color: #666; margin-bottom: 1rem;">How would you like to split the bill?</p>
                <div class="quick-actions" style="flex-direction: column; gap: 0.5rem;">
                    <button class="quick-btn" style="padding: 0.75rem; font-size: 0.875rem;" onclick="openSplitDetailsModal('equal')">⚖️ Equal Share</button>
                    <button class="quick-btn" style="padding: 0.75rem; font-size: 0.875rem;" onclick="openSplitDetailsModal('percentage')">📊 Percentage</button>
                </div>
                <div class="modal-buttons" style="margin-top: 1rem;">
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
                    <input type="number" id="split-amount" value="1500" min="1" style="margin-top: 0.5rem;">
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
                <p style="font-size: 0.75rem; color: #666; margin-bottom: 1rem;">AI will analyze real financial data to build a portfolio.</p>
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
                <p style="font-size: 0.8125rem; color: #666; margin-bottom: 1rem;">Select the card you want to block:</p>
                <div class="quick-actions" style="flex-direction: column; gap: 0.5rem;" id="block-card-list">
                    <button class="quick-btn" style="padding: 0.75rem; font-size: 0.875rem; justify-content: flex-start;" onclick="submitBlockCard('4111-1111-1111-1111', 'Debit Card (****1111)')">💳 Debit Card (****1111)</button>
                    <button class="quick-btn" style="padding: 0.75rem; font-size: 0.875rem; justify-content: flex-start;" onclick="submitBlockCard('5555-5555-5555-5555', 'Credit Card (****5555)')">💳 Credit Card (****5555)</button>
                </div>
                <div class="modal-buttons" style="margin-top: 1rem;">
                    <button class="btn-cancel" onclick="closeModal('block-card-modal')">Cancel</button>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="cancel-card-modal">
            <div class="modal-content">
                <h2>❌ Cancel a Card</h2>
                <p style="font-size: 0.8125rem; color: #666; margin-bottom: 1rem;">Warning: This action is permanent. Select the card to cancel:</p>
                <div class="quick-actions" style="flex-direction: column; gap: 0.5rem;" id="cancel-card-list">
                    <button class="quick-btn" style="padding: 0.75rem; font-size: 0.875rem; justify-content: flex-start;" onclick="submitCancelCard(1, 'Debit Card (****1111)')">💳 Debit Card (****1111)</button>
                    <button class="quick-btn" style="padding: 0.75rem; font-size: 0.875rem; justify-content: flex-start;" onclick="submitCancelCard(2, 'Credit Card (****5555)')">💳 Credit Card (****5555)</button>
                </div>
                <div class="modal-buttons" style="margin-top: 1rem;">
                    <button class="btn-cancel" onclick="closeModal('cancel-card-modal')">Cancel</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');
        let pendingIntent = null;
        let pendingMFA = false;
        let selectedSplitContacts = [];

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') send();
        });

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
        function submitBlockCard(cardNumber, label) {
            closeModal('block-card-modal');
            quickSend(`Block card ${cardNumber}`);
        }

        function openCancelCardModal() { document.getElementById('cancel-card-modal').style.display = 'flex'; }
        function submitCancelCard(cardId, label) {
            closeModal('cancel-card-modal');
            quickSend(`Cancel card ${cardId}`);
        }

        // ═══════════════════════════════════════════
        // PARSERS & CHARTS
        // ═══════════════════════════════════════════
        
        function parseInvestmentText(text) {
            const assets = [];
            const lines = text.split('\\n'); // ⭐ แก้ไขการตัดบรรทัด
            let currentAsset = null;
            for (let line of lines) {
                if (line.trim().startsWith('• **')) {
                    const match = line.match(/• \*\*(.*?)\*\* \((.*?)\)/);
                    if (match) {
                        currentAsset = { name: match[2], symbol: match[1], alloc: 0 };
                        assets.push(currentAsset);
                    }
                } else if (line.includes('Alloc:') && currentAsset) {
                    const match = line.match(/Alloc:\s*([\d.]+)%/);
                    if (match) currentAsset.alloc = parseFloat(match[1]);
                }
            }
            return assets;
        }

        function parseSubText(text) {
            const subs = [];
            const lines = text.split('\\n'); // ⭐ แก้ไขการตัดบรรทัด
            for (let line of lines) {
                const match = line.match(/• \*\*(.*?)\*\* \(฿(\d+)\/mo\)/);
                if (match) {
                    subs.push({ name: match[1], cost: parseFloat(match[2]) });
                }
            }
            return subs;
        }

        function initChart(canvasId, labels, data, colors) {
            const ctx = document.getElementById(canvasId).getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors,
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { boxWidth: 10, font: { size: 10, family: 'sans-serif' } }
                        }
                    }
                }
            });
        }

        // ⭐ ฟังก์ชันสร้างใบเสร็จ Split Bill
        function renderReceiptCard(text) {
            const amountMatch = text.match(/฿([\d,]+)/);
            const amount = amountMatch ? amountMatch[1] : "0";
            const noteMatch = text.match(/for (.*?)\./);
            const note = noteMatch ? noteMatch[1] : "Bill";
            const friendsMatch = text.match(/Split with: (.*)/);
            const friends = friendsMatch ? friendsMatch[1] : "";

            if (text.includes("Each owes:")) {
                const eachOwesMatch = text.match(/Each owes: ฿([\d,.]+)/);
                const eachOwes = eachOwesMatch ? eachOwesMatch[1] : "0";
                return `
                <div class="receipt-card">
                    <div class="receipt-header">🧾 Split Bill Receipt</div>
                    <div class="receipt-row"><span>Note:</span> <b>${note}</b></div>
                    <div class="receipt-row"><span>Total Amount:</span> <b>฿${amount}</b></div>
                    <div class="receipt-divider"></div>
                    <div class="receipt-row"><span>Each owes:</span> <b>฿${eachOwes}</b></div>
                    <div class="receipt-footer" style="margin-top: 12px;">Split with: ${friends}</div>
                </div>`;
            } else if (text.includes("Friend 1:")) {
                const regex = /- Friend \d+: (\d+)% \(฿([\d,.]+)\)/g;
                let match;
                const percentages = [];
                const labels = [];
                const data = [];
                let i = 1;
                while ((match = regex.exec(text)) !== null) {
                    percentages.push(`Friend ${i}: ${match[1]}% (฿${match[2]})`);
                    labels.push(`Friend ${i}`);
                    data.push(parseFloat(match[1]));
                    i++;
                }
                const totalPct = data.reduce((a,b)=>a+b, 0);
                if (totalPct < 100) {
                    data.push(100 - totalPct);
                    labels.push("You");
                }

                const chartId = 'chart-receipt-' + Date.now();
                setTimeout(() => {
                    initChart(chartId, labels, data, ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe']);
                }, 100);

                return `
                <div class="receipt-card">
                    <div class="receipt-header">🧾 Split Bill (Percentage)</div>
                    <div class="receipt-row"><span>Note:</span> <b>${note}</b></div>
                    <div class="receipt-row"><span>Total Amount:</span> <b>฿${amount}</b></div>
                    <div class="chart-container" style="height: 140px; margin: 10px 0;"><canvas id="${chartId}"></canvas></div>
                    <div class="receipt-list">${percentages.map(p => `<div>${p}</div>`).join('')}</div>
                    <div class="receipt-divider"></div>
                    <div class="receipt-footer">Split with: ${friends}</div>
                </div>`;
            }
            return text; // Fallback
        }

        // ⭐ ฟังก์ชันสร้าง E-Bill (Transfer)
        function renderTransferBill(text) {
            const amountMatch = text.match(/Transferred ฿([\d,]+)/);
            const amount = amountMatch ? amountMatch[1] : "0";
            const toMatch = text.match(/to (.*?)\\n/);
            const to = toMatch ? toMatch[1] : "Recipient";
            const balMatch = text.match(/New balance: ฿([\d,]+)/);
            const newBalance = balMatch ? balMatch[1] : "0";
            
            let extraText = "";
            const alertMatch = text.match(/(🚨.*)/s);
            if (alertMatch) {
                extraText = `<div style="margin-top: 15px; font-size: 11px; color: #d97706; background: #fffbeb; padding: 10px; border-radius: 8px;">${alertMatch[1].replace(/\\n/g, '<br>')}</div>`;
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

        // ⭐ ฟังก์ชันสร้าง Action Card (Confirm)
        function renderActionCard(text) {
            let actionText = text.split("Confirm?")[0].trim().replace(/\\n/g, '<br>');
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

        // ⭐ ฟังก์ชันสร้าง Success Card
        function renderSuccessCard(text) {
            const amtMatch = text.match(/Successfully invested ฿([\d,.]+)/);
            const balMatch = text.match(/New balance: ฿([\d,.]+)/);
            const symbolsMatch = text.match(/portfolio \((.*?)\)/);

            const amount = amtMatch ? amtMatch[1] : "0";
            const balance = balMatch ? balMatch[1] : "0";
            const symbols = symbolsMatch ? symbolsMatch[1] : "";

            return `
            <div class="success-card">
                <div class="success-header">
                    <span style="font-size: 24px;">🎉</span>
                    <div class="success-title">Investment Successful!</div>
                </div>
                <div class="success-row"><span>Invested Amount</span> <b>฿${amount}</b></div>
                <div class="success-row"><span>New Cash Balance</span> <b>฿${balance}</b></div>
                <div class="success-divider"></div>
                <div class="success-footer">
                    <div style="font-weight: 600; color: #14264f; margin-bottom: 4px;">Assets Added:</div>
                    <div style="font-size: 13px; color: #666;">${symbols}</div>
                    
                    <button class="btn-check-portfolio" onclick="input.value='Show portfolio'; send();">
                        💼 View My Portfolio
                    </button>
                </div>
            </div>`;
        }

        // ⭐ ฟังก์ชันสร้าง AI Portfolio Tracker (กรองข้อมูลขยะ)
        function renderPortfolioCard() {
            const portfolio = JSON.parse(localStorage.getItem('ai_portfolio') || '[]');
            
            if (portfolio.length === 0) {
                return `<div class="bubble" style="background:white; padding:16px;">You don't have any AI portfolio yet. Try saying "invest 10000 risk Medium goal Long-term growth"!</div>`;
            }

            // Group by symbol
            const grouped = {};
            portfolio.forEach(p => {
                // ⭐ กรองข้อมูลที่ผิดพลาด (NaN หรือ undefined) ออก
                if(!p || !p.symbol || p.symbol === 'undefined' || isNaN(p.shares) || isNaN(p.cost)) return; 
                
                if(!grouped[p.symbol]) grouped[p.symbol] = { ...p, totalShares: 0, totalCost: 0 };
                grouped[p.symbol].totalShares += p.shares;
                grouped[p.symbol].totalCost += p.cost;
            });

            const keys = Object.keys(grouped);
            if (keys.length === 0) {
                return `<div class="bubble" style="background:white; padding:16px;">Your portfolio is empty or has corrupted data. Please clear localStorage and try again.</div>`;
            }

            let listHtml = keys.map(sym => {
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
                <div class="portfolio-list">
                    ${listHtml}
                </div>
            </div>`;
        }

        function renderBalanceCard(balance, currency="THB") {
            return `
            <div class="balance-card">
                <div class="balance-left">
                    <div class="balance-label">Total balance 
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#7c8190" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>
                    </div>
                    <div class="balance-amount">฿${parseFloat(balance).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                    <div class="balance-delta">
                        <b><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#2f8f5b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17L17 7M8 7h9v9"/></svg>+3.2%</b>
                        vs. last month
                    </div>
                </div>
                <div class="balance-right">
                    <svg class="balance-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>
                    <svg width="100" height="45" viewBox="0 0 130 56" fill="none">
                        <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8d9bc2" stop-opacity=".22"/><stop offset="1" stop-color="#8d9bc2" stop-opacity="0"/></linearGradient></defs>
                        <path d="M2 52C14 48 20 36 32 34s20 10 34 6 22-18 34-16 18-4 28-10V56H2z" fill="url(#g)"/>
                        <path d="M2 52C14 48 20 36 32 34s20 10 34 6 22-18 34-16 18-4 28-10" stroke="#aab4d0" stroke-width="1.6" stroke-linecap="round"/>
                    </svg>
                </div>
            </div>`;
        }

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
            let html = `<table class="data-table"><thead><tr><th>Name</th><th>Amount</th></tr></thead><tbody>`;
            data.forEach(s => { html += `<tr><td>${s.merchant_name}</td><td>฿${s.amount}</td></tr>`; });
            return html + `</tbody></table>`;
        }
        function renderContactsTable(data) {
            if (!data || !Array.isArray(data) || data.length === 0) return '';
            let html = `<table class="data-table"><thead><tr><th>Name</th><th class="right">Tel</th></tr></thead><tbody>`;
            data.forEach(b => { html += `<tr><td>${b.full_name} (${b.nickname})</td><td class="right">${b.phone || '-'}</td></tr>`; });
            return html + `</tbody></table>`;
        }

        // ═══════════════════════════════════════════
        // ADD MESSAGE (Detect Charts & Cards)
        // ═══════════════════════════════════════════
        function addMessage(text, sender, showConfirmButtons = false, data = null) {
            const div = document.createElement('div');
            div.className = `message ${sender}`;
            if (sender === 'ai') {
                const avatar = document.createElement('div');
                avatar.className = 'ai-avatar'; avatar.textContent = '🤖';
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
            const isPortfolio = data === 'PORTFOLIO';

            // ⭐ 1. Balance Card
            if (isBalanceData) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.border = 'none';
                const cardDiv = document.createElement('div');
                cardDiv.innerHTML = renderBalanceCard(data.balance, data.currency);
                bubble.appendChild(cardDiv);
            } 
            // ⭐ 2. Portfolio Card
            else if (isPortfolio) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderPortfolioCard();
            }
            // ⭐ 3. Action Card (Confirm)
            else if (isConfirmAction) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderActionCard(text);
            }
            // ⭐ 4. Investment Chart (Analysis)
            else if (isInvestment) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                const assets = parseInvestmentText(text);
                const cardId = 'chart-inv-' + Date.now();
                
                let formattedText = text.replace(/🤖 \*\*AI Investment Analysis.*\\n/, '')
                    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\*(.*?)\*/g, '<i>$1</i>')
                    .split('\\n').join('<br>');

                bubble.innerHTML = `
                    <div class="chart-card">
                        <div class="chart-title">🤖 AI Investment Analysis</div>
                        <div class="chart-container"><canvas id="${cardId}"></canvas></div>
                        <div class="chart-text">${formattedText}</div>
                    </div>
                `;
                setTimeout(() => initChart(cardId, assets.map(a => a.name), assets.map(a => a.alloc), ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe']), 100);
            }
            // ⭐ 5. Investment Success (บันทึกลง Portfolio)
            else if (isInvestmentSuccess) {
                const lastAnalysis = JSON.parse(localStorage.getItem('last_investment') || '[]');
                if (lastAnalysis.length > 0) {
                    let portfolio = JSON.parse(localStorage.getItem('ai_portfolio') || '[]');
                    portfolio.push(...lastAnalysis);
                    localStorage.setItem('ai_portfolio', JSON.stringify(portfolio));
                }

                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderSuccessCard(text);
            }
            // ⭐ 6. Subscription Dashboard Chart
            else if (isSubDashboard) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                const subs = parseSubText(text);
                const cardId = 'chart-sub-' + Date.now();
                
                let formattedText = text.replace(/📊 \*\*Subscription Dashboard\*\*\\n/, '')
                    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\*(.*?)\*/g, '<i>$1</i>')
                    .split('\\n').join('<br>');

                bubble.innerHTML = `
                    <div class="chart-card">
                        <div class="chart-title">📊 Subscription Breakdown</div>
                        <div class="chart-container"><canvas id="${cardId}"></canvas></div>
                        <div class="chart-text">${formattedText}</div>
                    </div>
                `;
                setTimeout(() => initChart(cardId, subs.map(s => s.name), subs.map(s => s.cost), ['#f093fb', '#f5576c', '#4facfe', '#43e97b', '#fa709a']), 100);
            }
            // ⭐ 7. Receipt Card (Split Bill)
            else if (isReceipt) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderReceiptCard(text);
            }
            // ⭐ 8. Transfer E-Bill
            else if (isTransferBill) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderTransferBill(text);
            }
            // ⭐ 9. Text & Tables ปกติ
            else {
                if (text) {
                    const textNode = document.createElement('div');
                    let formattedText = text
                        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
                        .replace(/\*(.*?)\*/g, '<i>$1</i>')
                        .split('\\n').join('<br>');
                    textNode.innerHTML = formattedText;
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

            // ⭐ 10. โชว์ปุ่ม Yes/No แบบดั้งเดิม (ถ้ามี)
            if (showConfirmButtons && !isConfirmAction) {
                const btnDiv = document.createElement('div');
                btnDiv.className = 'confirm-buttons';
                btnDiv.style.display = 'flex'; btnDiv.style.gap = '0.5rem'; btnDiv.style.marginTop = '0.5rem';
                const yesBtn = document.createElement('button');
                yesBtn.className = 'confirm-btn confirm-yes'; yesBtn.textContent = '✅ Yes';
                yesBtn.style.background = '#10b981'; yesBtn.style.color = 'white'; yesBtn.style.border = 'none'; yesBtn.style.padding = '0.4rem'; yesBtn.style.borderRadius = '6px'; yesBtn.style.flex = '1'; yesBtn.style.cursor = 'pointer';
                yesBtn.onclick = () => { btnDiv.remove(); input.value = 'y'; send(); };
                const noBtn = document.createElement('button');
                noBtn.className = 'confirm-btn confirm-no'; noBtn.textContent = '❌ No';
                noBtn.style.background = '#f3f4f6'; noBtn.style.color = '#6b7280'; noBtn.style.border = '1px solid #e5e7eb'; noBtn.style.padding = '0.4rem'; noBtn.style.borderRadius = '6px'; noBtn.style.flex = '1'; noBtn.style.cursor = 'pointer';
                noBtn.onclick = () => { btnDiv.remove(); input.value = 'n'; send(); };
                btnDiv.appendChild(yesBtn); btnDiv.appendChild(noBtn);
                bubble.appendChild(btnDiv);
            }

            // ⭐ 11. Save last_investment for parsing (แก้ไขบั๊กการตัดบรรทัด)
            if (isInvestment) {
                const lines = text.split('\\n'); 
                let currentObj = null;
                const purchases = [];
                for(let line of lines) {
                    if (line.trim().startsWith('• **')) {
                        const m = line.match(/• \*\*(.*?)\*\* \((.*?)\) - ฿([\d,.]+)/);
                        if(m) {
                            currentObj = { symbol: m[1].trim(), name: m[2].trim(), price: parseFloat(m[3].replace(/,/g,'')) };
                        }
                    } else if (line.includes('Alloc:') && currentObj) {
                        const m = line.match(/Alloc:\s*([\d.]+)%\s*\(฿([\d,.]+)\)\s*->\s*([\d.]+)\s*shares/);
                        if(m) {
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
                avatar.className = 'user-avatar'; avatar.textContent = '🧔🏻‍♂️';
                div.appendChild(avatar);
            }
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function showTyping() {
            const div = document.createElement('div');
            div.className = 'message ai'; div.id = 'typing';
            const avatar = document.createElement('div');
            avatar.className = 'ai-avatar'; avatar.textContent = '🤖';
            div.appendChild(avatar);
            const bubble = document.createElement('div');
            bubble.className = 'bubble'; bubble.innerHTML = '<span class="typing">Thinking</span>';
            div.appendChild(bubble);
            chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
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

            // ⭐ Intercept Portfolio Command (สำหรับ Demo)
            if (text.toLowerCase() === 'show portfolio' || text.toLowerCase() === 'ai portfolio') {
                showTyping();
                setTimeout(() => {
                    hideTyping();
                    addMessage("", 'ai', false, 'PORTFOLIO');
                    sendBtn.disabled = false;
                    input.focus();
                }, 800);
                return;
            }

            if (pendingMFA) {
                try {
                    const res = await fetch('/api/verify-otp', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: 1, otp: text})
                    });
                    const data = await res.json();
                    
                    if (!res.ok) {
                        addMessage('❌ ' + (data.detail || 'Error'), 'ai');
                    } else {
                        if (data.status === "error") {
                            addMessage(data.reply, 'ai');
                        } else {
                            addMessage(data.reply, 'ai', false, data.data);
                            if (!data.requires_mfa) pendingMFA = false; 
                        }
                    }
                } catch (e) { addMessage('❌ Error: ' + e.message, 'ai'); pendingMFA = false; }
                sendBtn.disabled = false; input.focus(); return;
            }

            if (pendingIntent && (text.toLowerCase() === 'y' || text.toLowerCase() === 'yes')) {
                try {
                    const res = await fetch('/api/confirm', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({intent: pendingIntent, user_id: 1})
                    });
                    const data = await res.json();
                    if (!res.ok) addMessage('❌ ' + (data.detail || 'Error'), 'ai');
                    else addMessage(data.reply, 'ai', false, data.data);
                    pendingIntent = null;
                } catch (e) { addMessage('❌ Error: ' + e.message, 'ai'); }
                sendBtn.disabled = false; return;
            } else if (pendingIntent && (text.toLowerCase() === 'n' || text.toLowerCase() === 'no')) {
                addMessage('❌ Cancelled', 'ai');
                pendingIntent = null; sendBtn.disabled = false; return;
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
                    pendingMFA = true; pendingIntent = null;
                    addMessage(data.reply, 'ai');
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