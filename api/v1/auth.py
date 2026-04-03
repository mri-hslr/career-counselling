import enum
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from api.deps import get_current_user

from core.database import get_db
from core.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from models.users import User, UserRole
from schemas.user import UserCreate, UserResponse, Token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to register: {user_data.email}")
    
    db_user = db.query(User).filter(User.email == user_data.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_pw = get_password_hash(user_data.password)
    
    # Corrected field names to match User model
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_pw, 
        full_name=user_data.full_name,
        role=user_data.role.value if isinstance(user_data.role, enum.Enum) else user_data.role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user) 
    return new_user

@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    # Corrected to check hashed_password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = create_access_token(
        data={
            "sub": user.email, 
            "role": str(user.role), 
            "user_id": str(user.id)
        }, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me")
def get_user_progress_and_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns the current user's profile completion status safely.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    academic = getattr(user, 'academic_data', {}) or {}
    aptitude = getattr(user, 'apti_data', {}) or {}
    personality = getattr(user, 'personality_data', {}) or {}
    
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "progress": {
            "profile_done": len(academic) > 0, 
            "aptitude_done": len(aptitude) > 0,
            "personality_done": len(personality) > 0
        },
        "apti_data": aptitude,            # <--- ADD THIS
        "personality_data": personality,  # <--- ADD THIS 
        "academic_data": academic         # <--- ADD THIS
    }