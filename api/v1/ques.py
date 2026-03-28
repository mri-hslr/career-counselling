import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

# Router setup
router = APIRouter(prefix="/api/v1/assessments", tags=["Career Engine"])

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)

# Registry for all module types and their data sources
MODULE_REGISTRY = {
    "profile": {"type": "template", "table": "profiles", "uuid": "00000000-0000-0000-0000-000000000001"},
    "academic": {"type": "template", "table": "academic_profiles", "uuid": "00000000-0000-0000-0000-000000000002"},
    "psychometric": {"type": "template", "table": "psychometric_profiles", "uuid": "00000000-0000-0000-0000-000000000003"},
    "lifestyle": {"type": "template", "table": "lifestyle_profiles", "uuid": "00000000-0000-0000-0000-000000000004"},
    "financial": {"type": "template", "table": "financial_profiles", "uuid": "00000000-0000-0000-0000-000000000005"},
    "aspiration": {"type": "template", "table": "aspiration_profiles", "uuid": "00000000-0000-0000-0000-000000000006"},
    "interests":{"type":"template","table":"career_interest","uuid":"00000000-0000-0000-0000-000000000003"},
    "personality": {"type": "bank", "table": "personality_question_bank", "limit": 35},
    "aptitude": {"type": "vector_bank", "table": "langchain_pg_embedding", "limit": 45},
    "passion":{"type": "template", "table": "passion_strength","uuid":"00000000-0000-0000-0000-000000000007"},
}

@router.get("/questions/{module_name}")
async def get_module_questions(
    module_name: str, 
    target_grade: Optional[str] = Query(None, description="Grade level as string (e.g., '10', '12')")
):
    """
    Universal question fetcher. 
    - For 'aptitude', passing 'target_grade' (string) is mandatory.
    - Handles polymorphic retrieval from template rows, question banks, and vector stores.
    """
    module = MODULE_REGISTRY.get(module_name.lower())
    
    if not module:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found.")

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # --- CASE 1: STATIC TEMPLATES (Lifestyle, Academic, etc.) ---
                if module["type"] == "template":
                    ignored_columns = ("id", "user_id", "updated_at", "focus_score", "discipline_score", "digital_risk_score")
                    query = f"SELECT * FROM {module['table']} WHERE id = %s"
                    cur.execute(query, (module["uuid"],))
                    row = cur.fetchone()
                    
                    if not row:
                        raise HTTPException(status_code=404, detail="Template row not found in DB.")
                    
                    questions = {k: v for k, v in row.items() if k not in ignored_columns}
                    return {"status": "success", "module": module_name, "questions": questions}

                # --- CASE 2: APTITUDE (Grade-based from LangChain table) ---
                elif module_name.lower() == "aptitude":
                    if not target_grade:
                        raise HTTPException(status_code=400, detail="Target grade is required for aptitude questions.")

                    # Safely casting the string to int within the query logic
                    apti_query = f"""
                        SELECT id, document as question_text, cmetadata 
                        FROM {module['table']} 
                        WHERE (cmetadata->>'target_grade') = %s
                        ORDER BY RANDOM() 
                        LIMIT %s;
                    """
                    cur.execute(apti_query, (target_grade, module["limit"]))
                    rows = cur.fetchall()
                    
                    if not rows:
                        raise HTTPException(status_code=404, detail=f"No questions found for Grade: {target_grade}")

                    questions = {
                        str(r['id']): {
                            "text": r['question_text'],
                            "category": r['cmetadata'].get("category", "General"),
                            "difficulty": r['cmetadata'].get("difficulty", "Medium")
                        } for r in rows
                    }
                    return {"status": "success", "module": "aptitude", "grade": target_grade, "questions": questions}

                # --- CASE 3: PERSONALITY (Balanced Trait Pull) ---
                elif module_name.lower() == "personality":
                    pers_query = f"""
                        SELECT id, trait, sub_trait, question_text, question_type
                        FROM (
                            SELECT id, trait, sub_trait, question_text, question_type,
                                   ROW_NUMBER() OVER(PARTITION BY trait ORDER BY RANDOM()) as rn
                            FROM {module['table']}
                        ) t
                        WHERE rn <= 7 LIMIT %s;
                    """
                    cur.execute(pers_query, (module["limit"],))
                    rows = cur.fetchall()
                    
                    questions = {
                        str(r['id']): {
                            "text": r['question_text'],
                            "trait": r['trait'],
                            "sub_trait": r['sub_trait'],
                            "type": r['question_type']
                        } for r in rows
                    }
                    return {"status": "success", "module": "personality", "questions": questions}

    except Exception as e:
        logger.error(f"Error fetching questions for {module_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching assessment.")