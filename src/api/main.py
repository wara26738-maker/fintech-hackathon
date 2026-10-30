# src/api/main.py
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


app = FastAPI(
    title="Banking AI Agent API",
    description="AI-powered banking assistant",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }
        .container {
            width: 100%;
            max-width: 520px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 90vh;
            max-height: 750px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.75rem 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .header h1 { font-size: 1rem; font-weight: 600; }
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem;
            background: #f7f8fc;
        }
        .message {
            margin-bottom: 0.5rem;
            display: flex;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { justify-content: flex-end; align-items: flex-start; gap: 0.375rem; }
        .message.ai { justify-content: flex-start; align-items: flex-start; gap: 0.375rem; }
        
        .ai-avatar, .user-avatar {
            width: 1.75rem;
            height: 1.75rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            flex-shrink: 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
            line-height: 1;
        }
        .ai-avatar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .user-avatar { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }

        .bubble {
            max-width: 85%;
            padding: 0.5rem 0.75rem;
            border-radius: 12px;
            font-size: 0.8125rem;
            line-height: 1.4;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        .user .bubble {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .ai .bubble {
            background: white;
            color: #333;
            border-bottom-left-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        /* ─── Tables UI ─── */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.5rem;
            font-size: 0.75rem;
            white-space: normal;
        }
        .data-table th {
            text-align: left;
            padding: 0.375rem 0.25rem;
            border-bottom: 1px solid #eee;
            color: #666;
            font-weight: 600;
            font-size: 0.6875rem;
            text-transform: uppercase;
        }
        .data-table th.right { text-align: right; }
        .data-table td {
            padding: 0.5rem 0.25rem;
            border-bottom: 1px solid #f9f9f9;
        }
        .data-table td.right { text-align: right; font-weight: 600; }
        .data-table tr:last-child td { border-bottom: none; }
        
        .tx-category {
            display: inline-block;
            padding: 0.125rem 0.375rem;
            background: #f0f2ff;
            color: #667eea;
            border-radius: 4px;
            font-size: 0.625rem;
            font-weight: 500;
        }
        .status-badge {
            display: inline-block;
            padding: 0.125rem 0.375rem;
            border-radius: 4px;
            font-size: 0.625rem;
            font-weight: 500;
        }
        .status-active { background: #dcfce7; color: #16a34a; }
        .status-blocked { background: #fee2e2; color: #dc2626; }
        .status-expired { background: #f3f4f6; color: #6b7280; }

        .input-area {
            padding: 0.5rem 0.75rem;
            background: white;
            border-top: 1px solid #eee;
            display: flex;
            gap: 0.375rem;
        }
        input[type="text"] {
            flex: 1;
            padding: 0.5rem 0.75rem;
            border: 1.5px solid #e0e0e0;
            border-radius: 20px;
            font-size: 0.8125rem;
            outline: none;
            transition: border-color 0.2s;
        }
        input[type="text"]:focus { border-color: #667eea; }
        button.primary {
            padding: 0.5rem 0.875rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 0.8125rem;
            font-weight: 600;
            cursor: pointer;
        }
        button.primary:hover { transform: scale(1.03); }
        button.primary:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .typing { color: #999; font-size: 0.75rem; }
        .typing::after {
            content: '...';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
            0%, 20% { content: ''; }
            40% { content: '.'; }
            60% { content: '..'; }
            80%, 100% { content: '...'; }
        }

        /* ─── Confirm Buttons ─── */
        .confirm-buttons { display: flex; gap: 0.375rem; margin-top: 0.5rem; }
        .confirm-btn {
            padding: 0.375rem 0.625rem; border: none; border-radius: 6px;
            font-size: 0.6875rem; font-weight: 600; cursor: pointer;
            transition: all 0.15s; flex: 1;
        }
        .confirm-yes { background: #10b981; color: white; }
        .confirm-yes:hover { background: #059669; transform: translateY(-1px); }
        .confirm-no { background: #f3f4f6; color: #6b7280; border: 1px solid #e5e7eb; }
        .confirm-no:hover { background: #e5e7eb; }

        /* ─── Welcome ─── */
        .welcome-title { font-size: 0.8125rem; font-weight: 600; color: #333; margin-bottom: 0.125rem; }
        .welcome-subtitle { font-size: 0.6875rem; color: #666; margin-bottom: 0.5rem; }
        .feature-group { margin-bottom: 0.375rem; }
        .feature-label { display: block; font-size: 0.5625rem; font-weight: 700; color: #667eea; text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 0.1875rem; }
        .quick-actions { display: flex; flex-wrap: wrap; gap: 0.1875rem; }
        .quick-btn {
            padding: 0.1875rem 0.375rem; background: #f0f2ff; color: #667eea;
            border: 1px solid #e0e3ff; border-radius: 8px; font-size: 0.625rem;
            font-weight: 500; cursor: pointer; white-space: nowrap;
        }
        .quick-btn:hover { background: #667eea; color: white; }
        .welcome-tip { margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #eee; color: #666; font-size: 0.5625rem; font-style: italic; }
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
                <div class="bubble" style="max-width: 100%;">
                    <div class="welcome-title">👋 Hello! I'm your AI banking assistant.</div>
                    <div class="welcome-subtitle">Click any button to try:</div>
                    
                    <div class="feature-group">
                        <span class="feature-label">💰 Finance</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('Check balance')">💵 Balance</button>
                            <button class="quick-btn" onclick="quickSend('Show accounts')">📋 Accounts</button>
                            <button class="quick-btn" onclick="quickSend('Show transactions')">📊 Txns</button>
                        </div>
                    </div>
                    
                    <div class="feature-group">
                        <span class="feature-label">💸 Transfer</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('Transfer 500 to Mom')">✉️ 500→Mom</button>
                            <button class="quick-btn" onclick="promptTransfer()">💸 Custom</button>
                            <button class="quick-btn" onclick="quickSend('Show contacts')">👥 Contacts</button>
                        </div>
                    </div>
                    
                    <div class="feature-group">
                        <span class="feature-label">🔄 Subs</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('What am I paying for')">📺 List</button>
                            <button class="quick-btn" onclick="quickSend('Cancel Netflix')">❌ Netflix</button>
                        </div>
                    </div>
                    
                    <div class="feature-group">
                        <span class="feature-label">💳 Cards</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('Show cards')">💳 Show</button>
                            <button class="quick-btn" onclick="quickSend('Block card')">🔒 Block</button>
                            <button class="quick-btn" onclick="quickSend('Report card lost')">🚨 Lost</button>
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
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');
        let pendingIntent = null;
        let pendingMFA = false;

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') send();
        });

        // ─── Render Functions ───
        function renderTransactionsTable(data) {
            if (!data || !Array.isArray(data) || data.length === 0) return '';
            let html = `<table class="data-table">
                <thead><tr><th>Amount</th><th>Category</th><th class="right">Recipient</th></tr></thead><tbody>`;
            data.forEach(tx => {
                const amount = '฿' + Math.floor(tx.amount).toLocaleString();
                const category = (tx.category || 'transfer').charAt(0).toUpperCase() + (tx.category || 'transfer').slice(1);
                const note = tx.note || '-';
                html += `<tr>
                    <td>${amount}</td>
                    <td><span class="tx-category">${category}</span></td>
                    <td class="right">${note}</td>
                </tr>`;
            });
            return html + `</tbody></table>`;
        }

        function renderCardsTable(data) {
            if (!data || !Array.isArray(data) || data.length === 0) return '';
            let html = `<table class="data-table">
                <thead><tr><th>Name</th><th>Card Number</th><th class="right">Status</th></tr></thead><tbody>`;
            data.forEach(c => {
                const statusClass = c.status === 'active' ? 'status-active' : (c.status === 'blocked' ? 'status-blocked' : 'status-expired');
                html += `<tr>
                    <td>${c.card_type || '-'}</td>
                    <td>${c.card_number || '-'}</td>
                    <td class="right"><span class="status-badge ${statusClass}">${c.status}</span></td>
                </tr>`;
            });
            return html + `</tbody></table>`;
        }

        function renderSubscriptionsTable(data) {
            if (!data || !Array.isArray(data) || data.length === 0) return '';
            let html = `<table class="data-table">
                <thead><tr><th>Name</th><th>Amount</th></tr></thead><tbody>`;
            data.forEach(s => {
                html += `<tr>
                    <td>${s.merchant_name}</td>
                    <td>฿${s.amount}</td>
                </tr>`;
            });
            return html + `</tbody></table>`;
        }

        function renderContactsTable(data) {
            if (!data || !Array.isArray(data) || data.length === 0) return '';
            let html = `<table class="data-table">
                <thead><tr><th>Name</th><th class="right">Tel</th></tr></thead><tbody>`;
            data.forEach(b => {
                html += `<tr>
                    <td>${b.full_name} (${b.nickname})</td>
                    <td class="right">${b.phone || '-'}</td>
                </tr>`;
            });
            return html + `</tbody></table>`;
        }

        function addMessage(text, sender, showConfirmButtons = false, data = null) {
            const div = document.createElement('div');
            div.className = `message ${sender}`;
            
            if (sender === 'ai') {
                const avatar = document.createElement('div');
                avatar.className = 'ai-avatar';
                avatar.textContent = '🤖';
                div.appendChild(avatar);
            }
            
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            
            if (text) {
                const textNode = document.createElement('div');
                textNode.textContent = text;
                bubble.appendChild(textNode);
            }

            if (data && Array.isArray(data) && data.length > 0 && sender === 'ai') {
                let tableHtml = '';
                if (data[0].card_number !== undefined) {
                    tableHtml = renderCardsTable(data);
                } else if (data[0].merchant_name !== undefined) {
                    tableHtml = renderSubscriptionsTable(data);
                } else if (data[0].phone !== undefined && data[0].nickname !== undefined) {
                    tableHtml = renderContactsTable(data);
                } else if (data[0].amount !== undefined) {
                    tableHtml = renderTransactionsTable(data);
                }
                if (tableHtml) {
                    const tableDiv = document.createElement('div');
                    tableDiv.innerHTML = tableHtml;
                    bubble.appendChild(tableDiv);
                }
            }
            
            if (showConfirmButtons) {
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
                btnDiv.appendChild(yesBtn);
                btnDiv.appendChild(noBtn);
                bubble.appendChild(btnDiv);
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

        function quickSend(text) {
            input.value = text;
            send();
        }

        function promptTransfer() {
            const amount = prompt("💸 Enter amount (THB):");
            if (!amount || isNaN(amount) || parseInt(amount) <= 0) return;
            const recipient = prompt("👤 Enter recipient (mom/dad/wife):", "mom");
            if (!recipient) return;
            quickSend(`Transfer ${amount} to ${recipient}`);
        }

        async function send() {
            const text = input.value.trim();
            if (!text) return;

            addMessage(text, 'user');
            input.value = '';
            sendBtn.disabled = true;

            if (pendingMFA) {
                try {
                    const res = await fetch('/api/verify-otp', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: 1, otp: text})
                    });
                    const data = await res.json();
                    if (!res.ok) addMessage('❌ ' + (data.detail || 'Error'), 'ai');
                    else {
                        addMessage(data.reply, 'ai', false, data.data);
                        if (!data.requires_mfa) pendingMFA = false;
                    }
                } catch (e) {
                    addMessage('❌ Error: ' + e.message, 'ai');
                    pendingMFA = false;
                }
                sendBtn.disabled = false;
                input.focus();
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
                    } else {
                        addMessage(data.reply, 'ai', false, data.data);
                    }
                    pendingIntent = null;
                } catch (e) {
                    addMessage('❌ Error: ' + e.message, 'ai');
                }
                sendBtn.disabled = false;
                return;
            } else if (pendingIntent && (text.toLowerCase() === 'n' || text.toLowerCase() === 'no')) {
                addMessage('❌ Cancelled', 'ai');
                pendingIntent = null;
                sendBtn.disabled = false;
                return;
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
                    pendingMFA = true;
                    pendingIntent = null;
                    addMessage(data.reply, 'ai');
                } else if (data.requires_confirmation && data.intent) {
                    pendingIntent = data.intent;
                    pendingMFA = false;
                    addMessage(data.reply, 'ai', true);
                } else {
                    pendingIntent = null;
                    pendingMFA = false;
                    addMessage(res.ok ? data.reply : '❌ ' + (data.detail || 'Error'), 'ai', false, data.data);
                }
            } catch (e) {
                hideTyping();
                addMessage('❌ Error: ' + e.message, 'ai');
            }

            sendBtn.disabled = false;
            input.focus();
        }
    </script>
</body>
</html>
"""