from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class CareerSelectRequest(BaseModel):
    career_title: str

class CareerSelectResponse(BaseModel):
    success: bool
    career: str

class SelectedCareerResponse(BaseModel):
    career_title: Optional[str] = None
    career_id: Optional[UUID] = None