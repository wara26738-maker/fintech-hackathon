# src/api/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
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

# ⭐ ชี้ไปที่โฟลเดอร์ static
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# ให้ FastAPI เข้าถึงไฟล์ CSS/JS ได้ผ่าน URL /static/...
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
    # เสิร์ฟไฟล์ index.html จากโฟลเดอร์ static
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

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
        
        response = process_message(request.message, request.user_id)
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