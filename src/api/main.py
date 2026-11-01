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
    return HTMLResponse(content=get_app_html())

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


def get_app_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>🏦 Banking AI Agent</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        /* =========================================
           BASE STYLES (จากทั้ง 2 หน้า)
           ========================================= */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh; display: flex; justify-content: center;
            overflow: hidden; /* ป้องกันการเลื่อนหน้าจอหลัก */
        }
        
        /* ⭐ ตัวจัดการสลับหน้าจอ */
        .screen {
            width: 100%; height: 100vh; position: absolute; top: 0; left: 0;
            display: none; overflow-y: auto;
        }
        .screen.active { display: flex; justify-content: center; }

        /* =========================================
           HOME SCREEN STYLES (จากที่คุณให้มา)
           ========================================= */
        :root {
            --bg:#f7f4f0; --navy:#14264f; --navy-2:#1c3363; --cream:#f7efe4; 
            --card:#fbf9f6; --muted:#7c8190; --green:#2f8f5b;
        }
        #home-screen {
            background: #e9e6e1;
            color: var(--navy);
        }
        .phone {
            position:relative; width:100%; max-width:390px; background:var(--bg);
            padding:20px 16px 110px; min-height: 100vh; overflow-y: auto;
        }
        .greet{font-size:11px;letter-spacing:.2em;font-weight:500;margin:0 0 4px}
        .head{display:flex;justify-content:space-between;align-items:flex-start}
        .title{font-size:29px;line-height:1.12;font-weight:700;letter-spacing:-.02em;margin:0}
        .avatar{width:48px;height:48px;border-radius:50%;background:var(--navy-2);display:flex;align-items:center;justify-content:center;margin-top:2px}

        .hero{position:relative;margin-top:14px;border-radius:22px;padding:18px 16px 16px;
            background:linear-gradient(160deg,#1a2f5c 0%,#142852 60%,#1b3466 100%);color:#fff;overflow:hidden; cursor:pointer;}
        .hero-top{display:flex;gap:12px;align-items:center}
        .hero-icon{width:40px;height:40px;border-radius:50%;background:var(--cream);display:flex;align-items:center;justify-content:center;flex:none}
        .hero-title{font-size:16px;font-weight:600;margin:0}
        .hero-sub{font-size:12.5px;color:#d3d9e8;margin:2px 0 0}
        .hero-bubble{position:relative;z-index:1;margin-top:14px;background:rgba(255,255,255,.1);border-radius:14px;padding:14px 16px;font-size:13px;line-height:1.45;color:#e9edf6;width:86%}
        .cta{position:relative;z-index:1;margin-top:12px;width:100%;border:0;border-radius:999px;background:var(--cream);color:var(--navy);
            font-size:14px;font-weight:600;padding:16px 0;display:flex;align-items:center;justify-content:center;gap:10px}
        .deco{position:absolute;right:0;top:0;width:150px;height:100%;pointer-events:none}

        .sec{display:flex;justify-content:space-between;align-items:center;margin:22px 4px 12px}
        .sec h2{font-size:16px;font-weight:700;margin:0}
        .link{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:500;background:none;border:0;padding:0}

        .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
        .tile{background:var(--card);border-radius:18px;padding:14px 4px;display:flex;flex-direction:column;align-items:center;gap:10px;
            box-shadow:0 1px 8px rgba(20,38,79,.05);border:0; cursor:pointer; transition: transform 0.1s;}
        .tile:active { transform: scale(0.95); }
        .tile span{font-size:12px;font-weight:500}
        .circle{width:44px;height:44px;border-radius:50%;background:var(--cream);display:flex;align-items:center;justify-content:center}

        .balance{position:relative;margin-top:16px;background:var(--card);border-radius:18px;padding:16px 18px;display:flex;justify-content:space-between;box-shadow:0 1px 8px rgba(20,38,79,.05)}
        .bal-label{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500}
        .amount{font-size:25px;font-weight:700;letter-spacing:-.01em;margin:6px 0 8px}
        .delta{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
        .delta b{display:flex;align-items:center;gap:3px;color:var(--green);font-weight:500;background:#e6f1ea;border-radius:8px;padding:2px 6px 2px 4px}
        .spark{position:absolute;right:30px;bottom:14px}
        .chev{position:absolute;right:12px;top:18px}

        .tx{list-style:none;margin:0;padding:0 4px}
        .tx li{display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid #ece8e2}
        .tx li:last-child{border-bottom:0}
        .tx .circle{width:40px;height:40px}
        .tx-main{flex:1}
        .tx-name{font-size:13.5px;font-weight:500}
        .tx-date{font-size:11px;color:var(--muted);margin-top:2px}
        .tx-amt{font-size:13.5px;font-weight:500}

        .nav{position:fixed;left:50%;transform:translateX(-50%);bottom:8px;width:calc(100% - 16px);max-width:374px;height:66px;background:var(--card);border-radius:22px;
            display:flex;align-items:center;justify-content:space-around;box-shadow:0 -2px 14px rgba(20,38,79,.06);z-index: 100;}
        .nav button{background:none;border:0;display:flex;flex-direction:column;align-items:center;gap:4px;font-size:10.5px;font-weight:500;color:#8a90a0;padding:0;width:20%;cursor:pointer}
        .nav button.on{color:var(--navy);font-weight:600}
        .ai-wrap{display:flex;flex-direction:column;align-items:center;gap:6px}
        .ai{width:58px;height:58px;border-radius:50%;background:var(--cream);display:flex;align-items:center;justify-content:center;margin-top:-26px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);}
        .home-bar{position:absolute;left:50%;bottom:4px;transform:translateX(-50%);width:34%;height:4px;border-radius:4px;background:var(--navy)}


        /* =========================================
           CHAT SCREEN STYLES (จากของเดิม ไม่แตะต้อง)
           ========================================= */
        #chat-screen {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            align-items: center;
        }
        .chat-container {
            width: 100%; max-width: 520px; background: white; border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden;
            display: flex; flex-direction: column; height: 90vh; max-height: 750px; position: relative;
            margin: 1rem;
        }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.75rem 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .back-btn { background: rgba(255,255,255,0.2); border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer; margin-right: 0.5rem; }
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
        .user .bubble { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-bottom-right-radius: 4px; }
        .ai .bubble { background: white; color: #333; border-bottom-left-radius: 4px; border: 1px solid #f0f0f0; }
        .ai .bubble b { color: #14264f; font-weight: 700; }

        /* UI: Total Balance Card */
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

        /* UI: Chart Card */
        .chart-card {
            background: white; border-radius: 16px; padding: 16px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-top: 4px; width: 100%; min-width: 300px;
        }
        .chart-title { font-size: 14px; font-weight: 700; color: #14264f; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }
        .chart-container { position: relative; height: 180px; width: 100%; margin-bottom: 12px; }
        .chart-text { font-size: 12px; color: #555; line-height: 1.5; white-space: normal; }

        /* UI: Action Card (Confirmations) */
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

        /* UI: Success Card */
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
        
        /* ปุ่ม Check Portfolio ใน Success Card */
        .btn-check-portfolio {
            width: 100%; padding: 10px; margin-top: 16px;
            background: #10b981; color: white; border: none; border-radius: 12px;
            font-size: 14px; font-weight: 700; cursor: pointer;
            transition: all 0.2s; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);
        }
        .btn-check-portfolio:hover { background: #059669; transform: translateY(-2px); }

        /* UI: E-Bill & Receipt */
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

        /* UI: AI Portfolio Card */
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

    <!-- ⭐ SCREEN 1: HOME SCREEN -->
    <div id="home-screen" class="screen active">
        <div class="phone">
            <p class="greet">GOOD EVENING</p>
            <div class="head">
                <h1 class="title">Your money,<br>simplified.</h1>
                <div class="avatar">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff"><circle cx="12" cy="8" r="4.2"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z"/></svg>
                </div>
            </div>

            <div class="hero" onclick="openChat()">
                <svg class="deco" viewBox="0 0 150 240" fill="none">
                    <path d="M150 90c-30 6-58 30-70 80-10 40-30 55-80 70" stroke="rgba(255,255,255,.35)" stroke-width="1"/>
                    <ellipse cx="135" cy="215" rx="85" ry="60" fill="rgba(255,255,255,.07)"/>
                    <g fill="#f7efe4">
                        <path d="M122 14c1 8 7 14 15 15-8 1-14 7-15 15-1-8-7-14-15-15 8-1 14-7 15-15z"/>
                        <path d="M141 62c.4 3 2.6 5 5.5 5.5-3 .4-5 2.6-5.5 5.5-.4-3-2.6-5-5.5-5.5 3-.4 5-2.6 5.5-5.5z" opacity=".8"/>
                    </g>
                </svg>
                <div class="hero-top">
                    <div class="hero-icon">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="#14264f"><path d="M12 1.5c.7 5.6 4.9 9.8 10.5 10.5-5.6.7-9.8 4.9-10.5 10.5C11.3 16.9 7.1 12.7 1.5 12 7.1 11.3 11.3 7.1 12 1.5z"/></svg>
                    </div>
                    <div>
                        <p class="hero-title">Your AI money assistant</p>
                        <p class="hero-sub">Smarter insights. Better decisions.</p>
                    </div>
                </div>
                <div class="hero-bubble">You spent 12% less on dining this week compared to last week. Want to see where you could save more?</div>
                <button class="cta">Ask AI anything
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </button>
            </div>

            <div class="sec">
                <h2>Quick actions</h2>
                <button class="link">See all
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </button>
            </div>
            <div class="grid">
                <button class="tile" onclick="openChat('Transfer 500 to Sarah Work')">
                    <div class="circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h15M15 4l4 4-4 4M20 16H5M9 12l-4 4 4 4"/></svg></div>
                    <span>Transfers</span>
                </button>
                <button class="tile" onclick="openChat('Show my budget')">
                    <div class="circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="#14264f"><rect x="4" y="12" width="4" height="8" rx="1"/><rect x="10" y="4" width="4" height="16" rx="1"/><rect x="16" y="9" width="4" height="11" rx="1"/></svg></div>
                    <span>Budget</span>
                </button>
                <button class="tile" onclick="openChat('invest')">
                    <div class="circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/></svg></div>
                    <span>Investments</span>
                </button>
                <button class="tile" onclick="openChat('Show cards')">
                    <div class="circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 10h18"/></svg></div>
                    <span>Cards</span>
                </button>
                <button class="tile" onclick="openChat('Show subscription dashboard')">
                    <div class="circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4M16 3v4M4 11h16"/></svg></div>
                    <span>Subscriptions</span>
                </button>
                <button class="tile" onclick="openChat('Show transactions')">
                    <div class="circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M14 3v5h5M9 13h6M9 17h6M9 9h2"/></svg></div>
                    <span>Bills</span>
                </button>
            </div>

            <div class="balance">
                <div>
                    <div class="bal-label">Total balance
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7c8190" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>
                    </div>
                    <div class="amount">฿12,580.00</div>
                    <div class="delta">
                        <b><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#2f8f5b" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17L17 7M8 7h9v9"/></svg>+3.2%</b>
                        vs. last month
                    </div>
                </div>
                <svg class="spark" width="130" height="56" viewBox="0 0 130 56" fill="none">
                    <defs>
                        <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0" stop-color="#8d9bc2" stop-opacity=".22"/>
                            <stop offset="1" stop-color="#8d9bc2" stop-opacity="0"/>
                        </linearGradient>
                    </defs>
                    <path d="M2 52C14 48 20 36 32 34s20 10 34 6 22-18 34-16 18-4 28-10V56H2z" fill="url(#g)"/>
                    <path d="M2 52C14 48 20 36 32 34s20 10 34 6 22-18 34-16 18-4 28-10" stroke="#aab4d0" stroke-width="1.6" stroke-linecap="round"/>
                </svg>
                <svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7c8190" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>
            </div>

            <div class="sec">
                <h2>Recent transactions</h2>
                <button class="link" onclick="openChat('Show transactions')">See all
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </button>
            </div>
            <ul class="tx">
                <li>
                    <div class="circle"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3v8M4 3v5a3 3 0 0 0 6 0V3M7 11v10M17 21V3c-2.5 1.5-4 4.5-4 8h4"/></svg></div>
                    <div class="tx-main"><div class="tx-name">Dining</div><div class="tx-date">Oct 24, 2025</div></div>
                    <div class="tx-amt">- ฿12.50</div>
                </li>
                <li>
                    <div class="circle"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8h14l-1 12H6L5 8z"/><path d="M9 11V7a3 3 0 0 1 6 0v4"/></svg></div>
                    <div class="tx-main"><div class="tx-name">Shopping</div><div class="tx-date">Oct 23, 2025</div></div>
                    <div class="tx-amt">- ฿68.90</div>
                </li>
                <li>
                    <div class="circle"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#14264f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h15M15 4l4 4-4 4M20 16H5M9 12l-4 4 4 4"/></svg></div>
                    <div class="tx-main"><div class="tx-name">Transfer to Savings</div><div class="tx-date">Oct 22, 2025</div></div>
                    <div class="tx-amt">- ฿200.00</div>
                </li>
            </ul>

            <nav class="nav">
                <button class="on">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="#14264f"><path d="M12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5L12 3z"/></svg>
                    Home
                </button>
                <button onclick="openChat('Show accounts')">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#a9b0c2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18M16 14.5h2"/></svg>
                    Accounts
                </button>
                <button onclick="openChat()">
                    <div class="ai-wrap">
                        <div class="ai"><svg width="26" height="26" viewBox="0 0 24 24" fill="#14264f"><path d="M12 1.5c.7 5.6 4.9 9.8 10.5 10.5-5.6.7-9.8 4.9-10.5 10.5C11.3 16.9 7.1 12.7 1.5 12 7.1 11.3 11.3 7.1 12 1.5z"/></svg></div>
                        AI
                    </div>
                </button>
                <button onclick="openChat('Show my budget')">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="#a9b0c2"><rect x="4" y="12" width="4" height="8" rx="1"/><rect x="10" y="4" width="4" height="16" rx="1"/><rect x="16" y="9" width="4" height="11" rx="1"/></svg>
                    Insights
                </button>
                <button onclick="openChat('help')">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="#8a90a0"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>
                    More
                </button>
            </nav>
            <div class="home-bar"></div>
        </div>
    </div>

    <!-- ⭐ SCREEN 2: CHAT SCREEN (ของเดิม ไม่แตะ) -->
    <div id="chat-screen" class="screen">
        <div class="chat-container">
            <div class="header">
                <div class="back-btn" onclick="goHome()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
                </div>
                <span style="font-size: 1.125rem;">🏦</span>
                <h1>Banking AI Agent</h1>
            </div>
            <div class="chat-area" id="chat">
                <div class="message ai">
                    <div class="ai-avatar">🤖</div>
                    <div class="bubble">
                        <div class="welcome-title">👋 Hello! I'm your AI banking assistant.</div>
                        <div class="welcome-subtitle">Click any button to try:</div>
                        
                        <div class="feature-group" style="background: #f0fdf4; padding: 10px; border-radius: 12px; border: 1px solid #bbf7d0; margin-bottom: 1rem;">
                            <span class="feature-label" style="color: #166534;">⚡ Automated Action</span>
                            <div class="quick-actions">
                                <button class="quick-btn" style="background: #22c55e; color: white; border: none; padding: 0.5rem 0.8rem; font-size: 0.75rem; border-radius: 20px; box-shadow: 0 4px 10px rgba(34, 197, 94, 0.3);" onclick="quickSend('end of month reset')">🔄 End-of-Month Reset</button>
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
    </div>

    <script>
        // ═══════════════════════════════════════════
        // SCREEN MANAGER
        // ═══════════════════════════════════════════
        function openChat(initialMessage = '') {
            document.getElementById('home-screen').classList.remove('active');
            document.getElementById('chat-screen').classList.add('active');
            
            if (initialMessage) {
                document.getElementById('input').value = initialMessage;
                send();
            } else {
                document.getElementById('input').focus();
            }
        }

        function goHome() {
            document.getElementById('chat-screen').classList.remove('active');
            document.getElementById('home-screen').classList.add('active');
        }

        // ═══════════════════════════════════════════
        // CHAT LOGIC (ของเดิม)
        // ═══════════════════════════════════════════
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
            const lines = text.split('\\n');
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
            const lines = text.split('\\n');
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

            const grouped = {};
            portfolio.forEach(p => {
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

        // ⭐ ฟังก์ชันสร้างการ์ด Cross Scenario
        function renderOrchestrationCard(text) {
            let bodyText = text.replace("🔄 **End-of-Month Financial Reset**", "").replace("⚠️ Proceed to execute this full financial reset? [y/n]", "").trim();
            
            let formattedText = bodyText
                .replace(/1️⃣ \*\*(.*?)\*\*/g, '<div style="margin-top:12px; font-weight:700; color:#14264f;">1️⃣ $1</div>')
                .replace(/2️⃣ \*\*(.*?)\*\*/g, '<div style="margin-top:12px; font-weight:700; color:#14264f;">2️⃣ $1</div>')
                .replace(/3️⃣ \*\*(.*?)\*\*/g, '<div style="margin-top:12px; font-weight:700; color:#14264f;">3️⃣ $1</div>')
                .replace(/4️⃣ \*\*(.*?)\*\*/g, '<div style="margin-top:12px; font-weight:700; color:#14264f;">4️⃣ $1</div>')
                .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
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
            const isCrossScenario = text && text.includes("End-of-Month Financial Reset") && sender === 'ai';
            const isPortfolio = data === 'PORTFOLIO';

            // ⭐ 1. Cross Scenario Card
            if (isCrossScenario) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderOrchestrationCard(text);
            }
            // ⭐ 2. Balance Card
            else if (isBalanceData) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.border = 'none';
                const cardDiv = document.createElement('div');
                cardDiv.innerHTML = renderBalanceCard(data.balance, data.currency);
                bubble.appendChild(cardDiv);
            } 
            // ⭐ 3. Portfolio Card
            else if (isPortfolio) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderPortfolioCard();
            }
            // ⭐ 4. Action Card (Confirm)
            else if (isConfirmAction) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderActionCard(text);
            }
            // ⭐ 5. Investment Chart (Analysis)
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
            // ⭐ 6. Investment Success (บันทึกลง Portfolio)
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
            // ⭐ 7. Subscription Dashboard Chart
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
            // ⭐ 8. Receipt Card (Split Bill)
            else if (isReceipt) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderReceiptCard(text);
            }
            // ⭐ 9. Transfer E-Bill
            else if (isTransferBill) {
                bubble.style.background = 'transparent'; bubble.style.boxShadow = 'none'; bubble.style.padding = '0'; bubble.style.maxWidth = '100%'; bubble.style.border = 'none';
                bubble.innerHTML = renderTransferBill(text);
            }
            // ⭐ 10. Text & Tables ปกติ
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

            // ⭐ 11. โชว์ปุ่ม Yes/No แบบดั้งเดิม (ถ้ามี)
            if (showConfirmButtons && !isConfirmAction && !isCrossScenario) {
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

            // ⭐ 12. Save last_investment for parsing
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