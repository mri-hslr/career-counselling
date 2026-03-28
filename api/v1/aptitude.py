import os
import random
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/assessments", tags=["Career Engine"])
DATABASE_URL = os.getenv("DATABASE_URL")

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

# --- REWIRED ROUTE ---

@router.get("/aptitude/generate/assessment-pool")
async def get_assessment_pool(target_grade: str):
    """
    Fetches exactly 45 questions:
    - 15 questions per category (Logical, Quant, Verbal)
    - Within each: 5 Easy, 5 Medium, 5 Hard
    """
    categories = ["Logical Reasoning", "Quantitative Aptitude", "Verbal Ability"]
    difficulties = ["Easy", "Medium", "Hard"]
    
    query = """
    SELECT document, cmetadata->>'category' as cat, cmetadata->>'difficulty' as diff 
    FROM langchain_pg_embedding 
    WHERE cmetadata->>'target_grade' = %s
    """
    
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (target_grade,))
                rows = cur.fetchall()

        # Group fetched questions by Category and Difficulty
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

        # Build the final balanced pool
        final_balanced_pool = []
        for cat in categories:
            for diff in difficulties:
                available = raw_pool[cat][diff]
                # Sample exactly 5, or all if less than 5 available
                sampled = random.sample(available, min(len(available), 5))
                final_balanced_pool.extend(sampled)

        return {
            "total_count": len(final_balanced_pool),
            "questions": final_balanced_pool
        }

    except Exception as e:
        print(f"Pool Generation Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate balanced question pool.")