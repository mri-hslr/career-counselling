import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, UUID
from sqlalchemy.dialects.postgresql import JSONB 
from sqlalchemy.sql import func
import uuid
from core.database import Base

class UserRole(str, enum.Enum):
    STUDENT = "student"
    MENTOR = "mentor"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    # Using UUID to match your existing backend data
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True) 
    role = Column(String, nullable=False, default="student")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Career Engine JSONB Blocks ---
    academic_data = Column(JSONB, nullable=True)
    apti_data = Column(JSONB, nullable=True)
    personality_data = Column(JSONB, nullable=True)
    lifestyle_data = Column(JSONB, nullable=True)
    financial_data = Column(JSONB, nullable=True)
    passion_strength_data = Column(JSONB, nullable=True)
    aspiration_data = Column(JSONB, nullable=True)
    career_interest_data = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"