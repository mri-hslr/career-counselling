import uuid
from sqlalchemy import Column, Float, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name = Column(Text, nullable=False)
    dob = Column(Text) 
    gender = Column(Text)
    current_class = Column(Text)
    school_type = Column(Text)
    state = Column(Text)
    area_type = Column(Text)
    medium_of_learning = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # FIX: Removed back_populates="profile" to stop the KeyError
    user = relationship("User")

class AcademicProfile(Base):
    __tablename__ = "academic_profiles"
    __table_args__ = {'extend_existing': True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    overall_percentage_band = Column(Text)
    strongest_subject = Column(Text)
    weakest_subject = Column(Text)
    favorite_subject = Column(Text)
    learning_style = Column(Text)
    study_hours_home = Column(Text) 
    homework_completion = Column(Text)
    achievements = Column(Text)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PsychometricProfile(Base):
    __tablename__ = "psychometric_profiles"
    __table_args__ = {'extend_existing': True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    personality_type = Column(Text)
    riasec_code = Column(Text)
    work_environment = Column(Text)
    work_style = Column(Text)
    biggest_strength = Column(Text)
    biggest_weakness = Column(Text)
    motivation_driver = Column(Text)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class LifestyleProfile(Base):
    __tablename__ = "lifestyle_profiles"
    __table_args__ = {'extend_existing': True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    
    study_hours = Column(Text)
    screen_time = Column(Text)
    routine_consistency = Column(Text)
    sleep_quality = Column(Text)
    distraction_level = Column(Text)
    task_completion = Column(Text)
    reaction_to_failure = Column(Text)
    stress_level = Column(Text)
    pressure_handling = Column(Text)
    social_preference = Column(Text)
    focus_ability = Column(Text)
    biggest_distraction = Column(Text)
    
    focus_score = Column(Float)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class FinancialProfile(Base):
    __tablename__ = "financial_profiles"
    __table_args__ = {'extend_existing': True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    family_structure = Column(Text)
    income_band = Column(Text)
    father_education = Column(Text)
    mother_education = Column(Text)
    affordability_level = Column(Text)
    coaching_access = Column(Text) 
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class AspirationProfile(Base):
    __tablename__ = "aspiration_profiles"
    __table_args__ = {'extend_existing': True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    dream_career = Column(Text)
    life_direction = Column(Text)
    ten_year_vision = Column(Text)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())