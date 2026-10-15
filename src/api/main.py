# src/api/main.py
# FastAPI — REST API for Banking AI Agent

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any

from ..agent.loop import process_message, confirm_action, verify_otp
from ..db.session import init_db


# ═══════════════════════════════════════════
# LIFESPAN
# ═══════════════════════════════════════════

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


# ═══════════════════════════════════════════
# APP
# ═══════════════════════════════════════════

app = FastAPI(
    title="Banking AI Agent API",
    description="AI-powered banking assistant",
    version="1.0.0",
    lifespan=lifespan
)


# ═══════════════════════════════════════════
# CORS
# ═══════════════════════════════════════════

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════

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


# ═══════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════

@app.get("/")
async def root():
    return HTMLResponse(content=get_chat_html())


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "Banking AI Agent"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        from ..agent.loop import has_pending_suggestion, handle_suggestion
        
        if has_pending_suggestion(request.user_id):
            answer = request.message.strip().lower()
            if answer in ["yes", "y", "no", "n", "ใช่", "ไม่"]:
                result = handle_suggestion(request.user_id, answer)
                
                # ถ้า yes → retry ด้วยข้อความใหม่
                if result.get("retry_message"):
                    retry_msg = result["retry_message"]
                    result = process_message(retry_msg, request.user_id)
                    result["reply"] = f"✅ Interpreting as '{retry_msg}'\n\n" + result["reply"]
                
                return ChatResponse(**result)
        
        # ─── Normal process ───
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
        print(f"🔍 DEBUG: OTP='{request.otp}'")
        response = verify_otp(request.user_id, request.otp)
        print(f"🔍 DEBUG: response={response}")
        return ChatResponse(**response)
    except Exception as e:
        import traceback
        print(f"❌ ERROR: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════
# WEB CHAT HTML
# ═══════════════════════════════════════════

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
            padding: 1.25rem 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .header h1 { font-size: 1.25rem; font-weight: 600; }
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 1.25rem;
            background: #f7f8fc;
        }
        .message {
            margin-bottom: 0.875rem;
            display: flex;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { justify-content: flex-end; }
        .message.ai { justify-content: flex-start; }
        .bubble {
            max-width: 75%;
            padding: 0.75rem 1rem;
            border-radius: 16px;
            font-size: 0.9375rem;
            line-height: 1.5;
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
            padding: 1rem 1.25rem;
            background: white;
            border-top: 1px solid #eee;
            display: flex;
            gap: 0.5rem;
        }
        input[type="text"] {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1.5px solid #e0e0e0;
            border-radius: 24px;
            font-size: 0.9375rem;
            outline: none;
            transition: border-color 0.2s;
        }
        input[type="text"]:focus { border-color: #667eea; }
        button {
            padding: 0.75rem 1.25rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 24px;
            font-size: 0.9375rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s;
        }
        button:hover { transform: scale(1.03); }
        button:active { transform: scale(0.98); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .typing {
            display: inline-block;
            color: #999;
            font-size: 0.875rem;
            padding: 0.5rem 1rem;
        }
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span style="font-size: 1.75rem;">🏦</span>
            <h1>Banking AI Agent</h1>
        </div>
        <div class="chat-area" id="chat">
            <div class="message ai">
                <div class="bubble">Hello! 👋 I'm your AI banking assistant.

Try:
• "Check balance"
• "Show transactions"
• "Transfer 500 to Mom" (Yellow: confirm)
• "Transfer 5,000 to Mom" (Red: OTP)</div>
            </div>
        </div>
        <div class="input-area">
            <input type="text" id="input" placeholder="Type a message..." autofocus>
            <button id="send" onclick="send()">Send</button>
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

        function addMessage(text, sender) {
            const div = document.createElement('div');
            div.className = `message ${sender}`;
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.textContent = text || '(no response)';
            div.appendChild(bubble);
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function showTyping() {
            const div = document.createElement('div');
            div.className = 'message ai';
            div.id = 'typing';
            div.innerHTML = '<div class="bubble"><span class="typing">AI is thinking</span></div>';
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function hideTyping() {
            const el = document.getElementById('typing');
            if (el) el.remove();
        }

        async function send() {
            const text = input.value.trim();
            if (!text) return;

            addMessage(text, 'user');
            input.value = '';
            sendBtn.disabled = true;

            // ─── Handle OTP input ───
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
                        addMessage(data.reply, 'ai');
                        // ถ้า OTP ถูกต้อง → ไม่ pending อีก
                        if (!data.requires_mfa) {
                            pendingMFA = false;
                        }
                    }
                } catch (e) {
                    addMessage('❌ Error: ' + e.message, 'ai');
                    pendingMFA = false;
                }
                sendBtn.disabled = false;
                input.focus();
                return;
            }

            // ─── Handle y/n confirmation ───
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
                        addMessage(data.reply, 'ai');
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

            // ─── Send to chat API ───
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, user_id: 1})
                });
                const data = await res.json();
                hideTyping();
                
                if (!res.ok) {
                    addMessage('❌ ' + (data.detail || 'Error'), 'ai');
                } else {
                    addMessage(data.reply, 'ai');
                }

                // ─── Set pending state ───
                if (data.requires_mfa) {
                    pendingMFA = true;
                    pendingIntent = null;
                } else if (data.requires_confirmation && data.intent) {
                    pendingIntent = data.intent;
                    pendingMFA = false;
                } else {
                    pendingIntent = null;
                    pendingMFA = false;
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


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)