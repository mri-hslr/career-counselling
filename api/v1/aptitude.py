import os
import random
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Depends # Added Depends
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy.orm import Session       # Added Session
from core.database import get_db         # Added get_db
from models.users import User            # Added User model

router = APIRouter(prefix="/api/v1/assessments", tags=["Career Engine"])
DATABASE_URL = os.getenv("DATABASE_URL")

class AssessmentSubmission(BaseModel):
    userId: UUID
    moduleKey: str
    payload: dict  # This will contain the 'scores' object from frontend
    
# --- CLEAN UTILS ---
def extract_qa(text: str):
    """Parses raw document text into clean question, options, answer, and explanation."""
    try:
        parts = text.split("A)")
        raw_question = parts[0]
        clean_q = re.sub(r"(?i)^(Question:|Q\d+[\.:])", "", raw_question).strip()
        
        options_blob = "A)" + parts[1]
        labels = ['A)', 'B)', 'C)', 'D)']
        final_options = []
        
        for i, current_label in enumerate(labels):
            if current_label in options_blob:
                start_content = options_blob.split(current_label)[1]
                terminators = labels[i+1:] + ["Correct Answer:", "Explanation:", "Q"]
                option_content = start_content
                for term in terminators:
                    if term in option_content:
                        option_content = option_content.split(term)[0]
                        break
                final_options.append(f"{current_label} {option_content.strip()}")

        ans_match = re.search(r"Correct Answer:\s*(?:Option\s*)?([A-D])", text, re.IGNORECASE)
        correct_letter = ans_match.group(1).upper() if ans_match else "A"
        
        explanation = "N/A"
        if "Explanation:" in text:
            explanation = text.split("Explanation:")[1].split("Question:")[0].strip()
            
        return clean_q, final_options, correct_letter, explanation
    except:
        return "Parsing Error", ["A) N/A", "B) N/A", "C) N/A", "D) N/A"], "A", "N/A"

# --- ROUTES ---

@router.get("/aptitude/generate/assessment-pool")
async def get_assessment_pool(target_grade: str):
    categories = ["Logical Reasoning", "Quantitative Aptitude", "Verbal Ability"]
    difficulties = ["Easy", "Medium", "Hard"]
    
   # Use LIKE to match "8" inside "6-8"
    query = """
    SELECT document, cmetadata->>'category' as cat, cmetadata->>'difficulty' as diff 
    FROM langchain_pg_embedding 
    WHERE cmetadata->>'target_grade' LIKE %s
    """
    
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Wrap the grade in wildcards: e.g., "%8%"
                cur.execute(query, (f"%{target_grade}%",))
                rows = cur.fetchall()
                print(f"DEBUG: Found {len(rows)} rows for grade {target_grade}")

        raw_pool = {cat: {diff: [] for diff in difficulties} for cat in categories}
        
        for r in rows:
            cat, diff = r.get('cat'), r.get('diff')
            if cat in categories and diff in difficulties:
                q_text, opts, ans, expl = extract_qa(r['document'])
                raw_pool[cat][diff].append({
                    "question": q_text,
                    "options": opts,
                    "answer": ans,
                    "explanation": expl,
                    "category": cat,
                    "difficulty": diff
                })
        final_balanced_pool = []
        for cat in categories:
            for diff in difficulties:
                available = raw_pool[cat][diff]
                sampled = random.sample(available, min(len(available), 5))
                final_balanced_pool.extend(sampled)

        return {
            "total_count": len(final_balanced_pool),
            "questions": final_balanced_pool
        }

    except Exception as e:
        print(f"Pool Generation Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate question pool.")
    
@router.post("/submit")
async def submit_assessment(data: AssessmentSubmission, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.userId).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.moduleKey == 'aptitude':
        user.apti_data = data.payload.get('scores')
    
    db.commit()
    db.refresh(user) # Refresh to get the updated state
    return {"message": "Assessment saved successfully", "scores": user.apti_data}