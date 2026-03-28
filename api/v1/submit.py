import os
import logging
import json
import psycopg2
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any

# 1. Router Setup
router = APIRouter(prefix="/api/v1/assessments", tags=["Submission"])

# 2. Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)

# 3. The Mapping Logic (Verified against your SQL results)
# This maps the "Frontend Module Name" to the "Actual Database Column"
COLUMN_MAPPING = {
    "academic": "academic_data",
    "aptitude": "apti_data",
    "personality": "personality_data",
    "lifestyle": "lifestyle_data",
    "financial": "financial_data",
    "passion": "passion_strength_data",
    "aspiration": "aspiration_data",
    "interests":"career_interest_data"
}

class UniversalSubmission(BaseModel):
    user_id: str
    module_key: str  # e.g., "lifestyle", "academic"
    payload: Dict[str, Any]  # The "Template Swapped" JSON blob

@router.post("/submit-generic")
async def submit_generic_assessment(submission: UniversalSubmission):
    """
    Universal sync endpoint:
    Takes a JSON blob from the frontend, identifies the target column 
    based on the module_key, and persists it to the users table.
    """
    
    # Normalize the key to lowercase to prevent mapping misses
    key = submission.module_key.lower()
    
    # 1. Validation: Ensure the module actually exists in our schema
    target_column = COLUMN_MAPPING.get(key)
    
    if not target_column:
        logger.warning(f"Submission attempt for unsupported module: {key}")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid module key: '{key}'. Supported: {list(COLUMN_MAPPING.keys())}"
        )

    # 2. Atomic Database Update
    # Using parameterized queries to prevent SQL injection
    query = f"""
    UPDATE users 
    SET {target_column} = %s, 
        updated_at = NOW() 
    WHERE id = %s;
    """

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Convert the Python dictionary payload to a JSON string for Postgres
                cur.execute(query, (json.dumps(submission.payload), submission.user_id))
            
            # Commit the transaction
            conn.commit()
            
        logger.info(f"Successfully synced {key} for User: {submission.user_id}")
        
        return {
            "status": "success",
            "message": f"Module '{key}' has been successfully persisted to '{target_column}'",
            "module_synced": key
        }

    except Exception as e:
        logger.error(f"Database Error during {key} submission: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Internal Server Error: Data persistence failed."
        )