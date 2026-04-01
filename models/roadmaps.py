import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Roadmap(Base):
    __tablename__ = "roadmaps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="Overview") # Overview, Active, Completed
    progress_percentage = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    phases = relationship("RoadmapPhase", back_populates="roadmap", cascade="all, delete-orphan", order_by="RoadmapPhase.sequence")

class RoadmapPhase(Base):
    __tablename__ = "roadmap_phases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    roadmap_id = Column(UUID(as_uuid=True), ForeignKey("roadmaps.id", ondelete="CASCADE"))
    sequence = Column(Integer, nullable=False) # Order of the phase
    title = Column(String, nullable=False)
    status = Column(String, default="Not Started") # Not Started, Active, Completed
    progress_percentage = Column(Float, default=0.0)

    roadmap = relationship("Roadmap", back_populates="phases")
    tasks = relationship("RoadmapTask", back_populates="phase", cascade="all, delete-orphan", order_by="RoadmapTask.sequence")

class RoadmapTask(Base):
    __tablename__ = "roadmap_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phase_id = Column(UUID(as_uuid=True), ForeignKey("roadmap_phases.id", ondelete="CASCADE"))
    sequence = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="Not Started") # Not Started, Completed
    
    phase = relationship("RoadmapPhase", back_populates="tasks")