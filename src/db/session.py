# src/db/session.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
import os
from dotenv import load_dotenv

# โหลดค่าจาก .env
load_dotenv()

# Database URL (ใช้ SQLite เป็นค่าเริ่มต้น)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./banking.db")

# สร้าง engine (ตัวเชื่อมต่อ database)
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# สร้างตารางทั้งหมด (ถ้ายังไม่มี)
Base.metadata.create_all(engine)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """ใช้เป็น dependency ใน FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """สร้างตารางทั้งหมด"""
    Base.metadata.create_all(engine)
    print("✅ Database initialized")


if __name__ == "__main__":
    init_db()