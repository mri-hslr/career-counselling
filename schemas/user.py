from pydantic import BaseModel, EmailStr
from models.users import UserRole
from typing import Optional
from uuid import UUID

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    # Change .student to .STUDENT
    role: UserRole = UserRole.STUDENT 

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str