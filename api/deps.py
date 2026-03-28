import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import SECRET_KEY, ALGORITHM
from models.users import User

# This tells FastAPI where to look for the token when using Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Validates the JWT token in the request header and returns the current logged-in User object.
    Matches the consolidated JSONB User model (no separate profile table).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decode the token to get the user identity (email)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # 2. Fetch the user directly from the users table
    user = db.query(User).filter(User.email == email).first()
    
    # 3. Validation: We only check if the user exists. 
    # We NO LONGER check for user.profile because that data is now in JSONB columns.
    if user is None:
        raise credentials_exception
        
    return user