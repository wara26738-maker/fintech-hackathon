# src/db/models.py

from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime,
    Boolean, ForeignKey, Text, Enum
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class AccountType(enum.Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    FIXED = "fixed"


class TransactionType(enum.Enum):
    TRANSFER = "transfer"
    PAYMENT = "payment"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    REFUND = "refund"


class TransactionStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CardType(enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    VIRTUAL = "virtual"


class CardStatus(enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    LOST = "lost"
    EXPIRED = "expired"


class PermissionTier(enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(100), unique=True)
    national_id = Column(String(20), unique=True)
    date_of_birth = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    accounts = relationship("Account", back_populates="user")
    cards = relationship("Card", back_populates="user")
    beneficiaries = relationship("Beneficiary", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User {self.full_name} ({self.phone})>"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_number = Column(String(20), unique=True, nullable=False)
    account_type = Column(Enum(AccountType), default=AccountType.SAVINGS)
    balance = Column(Numeric(15, 2), default=0)
    currency = Column(String(3), default="THB")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    transactions_from = relationship(
        "Transaction",
        foreign_keys="Transaction.from_account_id",
        back_populates="from_account"
    )
    transactions_to = relationship(
        "Transaction",
        foreign_keys="Transaction.to_account_id",
        back_populates="to_account"
    )

    def __repr__(self):
        return f"<Account {self.account_number} ฿{self.balance}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    from_account_id = Column(Integer, ForeignKey("accounts.id"))
    to_account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default="THB")
    transaction_type = Column(Enum(TransactionType))
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    category = Column(String(50))
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    from_account = relationship(
        "Account", foreign_keys=[from_account_id],
        back_populates="transactions_from"
    )
    to_account = relationship(
        "Account", foreign_keys=[to_account_id],
        back_populates="transactions_to"
    )

    def __repr__(self):
        return f"<Transaction ฿{self.amount} {self.status.value}>"


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    card_number = Column(String(20), unique=True)
    card_type = Column(Enum(CardType))
    status = Column(Enum(CardStatus), default=CardStatus.ACTIVE)
    daily_limit = Column(Numeric(15, 2), default=20000)
    monthly_limit = Column(Numeric(15, 2), default=100000)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="cards")

    def __repr__(self):
        return f"<Card {self.card_number} {self.status.value}>"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    merchant_name = Column(String(100))
    amount = Column(Numeric(15, 2))
    currency = Column(String(3), default="THB")
    billing_cycle = Column(String(20))
    next_billing_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Subscription {self.merchant_name} ฿{self.amount}>"


class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nickname = Column(String(50))
    full_name = Column(String(100))
    phone = Column(String(20))
    account_number = Column(String(20))
    bank_name = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="beneficiaries")

    def __repr__(self):
        return f"<Beneficiary {self.nickname}>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(50))
    action = Column(String(100))
    permission_tier = Column(Enum(PermissionTier))
    input_text = Column(Text)
    intent = Column(String(100))
    plan = Column(Text)
    result = Column(String(50))
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} {self.result}>"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mfa_verified = Column(Boolean, default=False)
    mfa_token = Column(String(20))
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Session {self.session_id}>"