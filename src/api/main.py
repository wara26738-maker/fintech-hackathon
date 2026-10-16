# src/api/main.py
# FastAPI — REST API for Banking AI Agent

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
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.post("/api/confirm", response_model=ChatResponse)
async def confirm(request: ConfirmRequest):
    try:
        response = confirm_action(request.intent, request.user_id)
        return ChatResponse(**response)
    except Exception as e:
        import traceback
        print(f"❌ ERROR: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify-otp", response_model=ChatResponse)
async def verify_otp_endpoint(request: VerifyOTPRequest):
    try:
        response = verify_otp(request.user_id, request.otp)
        return ChatResponse(**response)
    except Exception as e:
        import traceback
        print(f"❌ ERROR: {e}\n{traceback.format_exc()}")
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
            max-width: 500px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 90vh;
            max-height: 700px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.625rem 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.375rem;
        }
        .header h1 { font-size: 0.9375rem; font-weight: 600; }
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 0.375rem;
            background: #f7f8fc;
        }
        .message {
            margin-bottom: 0.3125rem;
            display: flex;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { 
            justify-content: flex-end;
            align-items: flex-start;
            gap: 0.375rem;
        }
        .message.ai { 
            justify-content: flex-start;
            align-items: flex-start;
            gap: 0.375rem;
        }
        .ai-avatar {
            width: 1.5rem;
            height: 1.5rem;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            flex-shrink: 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
            line-height: 1;
        }
        .user-avatar {
            width: 1.5rem;
            height: 1.5rem;
            border-radius: 50%;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            flex-shrink: 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
            line-height: 1;
        }
        .bubble {
            max-width: 85%;
            padding: 0.3125rem 0.5rem;
            border-radius: 10px;
            font-size: 0.8125rem;
            line-height: 1.2;
            white-space: pre-wrap;
            word-wrap: break-word;
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
        .input-area {
            padding: 0.4375rem 0.625rem;
            background: white;
            border-top: 1px solid #eee;
            display: flex;
            gap: 0.3125rem;
        }
        input[type="text"] {
            flex: 1;
            padding: 0.4375rem 0.625rem;
            border: 1.5px solid #e0e0e0;
            border-radius: 20px;
            font-size: 0.8125rem;
            outline: none;
            transition: border-color 0.2s;
        }
        input[type="text"]:focus { border-color: #667eea; }
        button.primary {
            padding: 0.4375rem 0.75rem;
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
        .confirm-buttons {
            display: flex;
            gap: 0.375rem;
            margin-top: 0.375rem;
        }
        .confirm-btn {
            padding: 0.3125rem 0.625rem;
            border: none;
            border-radius: 6px;
            font-size: 0.6875rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
            flex: 1;
        }
        .confirm-yes {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }
        .confirm-yes:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 8px rgba(16,185,129,0.3);
        }
        .confirm-no {
            background: #f3f4f6;
            color: #6b7280;
            border: 1px solid #e5e7eb;
        }
        .confirm-no:hover {
            background: #e5e7eb;
        }
        
        /* ─── Welcome ─── */
        .welcome-title {
            font-size: 0.8125rem;
            font-weight: 600;
            color: #333;
            margin: 0;
            padding: 0;
            line-height: 1.15;
        }
        .welcome-subtitle {
            font-size: 0.6875rem;
            color: #666;
            margin: 0;
            padding: 0;
            line-height: 1.15;
        }
        .feature-group {
            margin: 0;
            padding: 0;
            line-height: 1;
        }
        .feature-label {
            display: block;
            font-size: 0.5625rem;
            font-weight: 700;
            color: #667eea;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            line-height: 1;
            margin: 0.1875rem 0 0.0625rem 0;
            padding: 0;
        }
        .quick-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.125rem;
            margin: 0;
            padding: 0;
            line-height: 1;
        }
        .quick-btn {
            padding: 0.1875rem 0.375rem;
            background: #f0f2ff;
            color: #667eea;
            border: 1px solid #e0e3ff;
            border-radius: 8px;
            font-size: 0.625rem;
            font-weight: 500;
            cursor: pointer;
            white-space: nowrap;
            line-height: 1.2;
        }
        .quick-btn:hover {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: transparent;
        }
        .welcome-tip {
            margin: 0.25rem 0 0 0;
            padding: 0.25rem 0 0 0;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 0.5625rem;
            font-style: italic;
            line-height: 1.2;
        }
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
                <div class="bubble" style="max-width: 100%; padding: 0.25rem 0.5rem; line-height: 1.15;">
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
                    
                    <div class="feature-group">
                        <span class="feature-label">👤 Profile</span>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="quickSend('My profile')">👤 Me</button>
                            <button class="quick-btn" onclick="quickSend('help')">❓ Help</button>
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

        function addMessage(text, sender, showConfirmButtons = false) {
            const div = document.createElement('div');
            div.className = `message ${sender}`;
            
            // AI avatar (left)
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
            
            // ปุ่ม Yes/No
            if (showConfirmButtons) {
                const btnDiv = document.createElement('div');
                btnDiv.className = 'confirm-buttons';
                
                const yesBtn = document.createElement('button');
                yesBtn.className = 'confirm-btn confirm-yes';
                yesBtn.textContent = '✅ Yes';
                yesBtn.onclick = () => {
                    btnDiv.remove();
                    input.value = 'y';
                    send();
                };
                
                const noBtn = document.createElement('button');
                noBtn.className = 'confirm-btn confirm-no';
                noBtn.textContent = '❌ No';
                noBtn.onclick = () => {
                    btnDiv.remove();
                    input.value = 'n';
                    send();
                };
                
                btnDiv.appendChild(yesBtn);
                btnDiv.appendChild(noBtn);
                bubble.appendChild(btnDiv);
            }
            
            div.appendChild(bubble);
            
            // ☀️ User avatar (right) — ต้อง append หลัง bubble
            if (sender === 'user') {
                const avatar = document.createElement('div');
                avatar.className = 'user-avatar';
                avatar.textContent = '🧔🏻‍♂️';
                div.appendChild(avatar);
                console.log('User avatar added:', avatar);
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
                        addMessage(data.reply, 'ai');
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
                    addMessage(res.ok ? data.reply : '❌ ' + (data.detail || 'Error'), 'ai');
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
                    addMessage(res.ok ? data.reply : '❌ ' + (data.detail || 'Error'), 'ai');
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)