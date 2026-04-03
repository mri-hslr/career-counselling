import os
import logging
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from core.database import get_db
from api.deps import get_current_user
from models.users import User
from models.mentorship import MentorFeedback, ParentFeedback
from models.roadmaps import Roadmap, RoadmapPhase, RoadmapTask

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/roadmaps", tags=["Career Roadmap"])


# ── Response Schema ───────────────────────────────────────────────────────────

class WeeklyTask(BaseModel):
    week_number: int
    topic: str = Field(description="Specific focus for this week")
    tasks: List[str] = Field(description="3-5 concrete, actionable tasks each completable in one session")
    resources: List[str] = Field(description="2-3 free or low-cost resources (official docs, YouTube, freeCodeCamp, etc.)")


class RoadmapPhaseIn(BaseModel):
    phase_number: int
    phase_title: str
    description: str
    importance: str = Field(description="CRITICAL | STRATEGIC | SPECIALIZATION")
    duration_weeks: int
    skills_targeted: List[str] = Field(description="Specific skills built in this phase")
    weekly_breakdown: List[WeeklyTask]
    milestone_project: str = Field(description="A real, portfolio-worthy project that proves phase completion")
    success_criteria: str = Field(description="Measurable condition that proves the student is ready to advance")


class CareerRoadmapResponse(BaseModel):
    career_title: str
    student_level: str = Field(description="BEGINNER | INTERMEDIATE | ADVANCED — assessed from student profile")
    difficulty_level: str
    total_duration: str
    daily_commitment: str = Field(description="Realistic daily hours derived from student's lifestyle data")
    phases: List[RoadmapPhaseIn]
    mentor_adjustments: str = Field(default="", description="How mentor action items shaped this roadmap")
    parent_adjustments: str = Field(default="", description="How parent observations shaped this roadmap")


# ── Persistence Schemas ──────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    id: UUID
    sequence: int
    title: str
    description: Optional[str]
    status: str
    class Config: from_attributes = True

class PhaseResponse(BaseModel):
    id: UUID
    sequence: int
    title: str
    status: str
    progress_percentage: float
    tasks: List[TaskResponse]
    class Config: from_attributes = True

class RoadmapResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    status: str
    progress_percentage: float
    phases: List[PhaseResponse]
    class Config: from_attributes = True


# ── Gold Prompt ───────────────────────────────────────────────────────────────

_GOLD_SYSTEM_PROMPT = """\
You are an Expert Career Architect and Personalized Learning Coach. \
Build a deeply personalized, achievable 6-month roadmap for the student below. \
This is NOT a generic tutorial — every decision must reflect THIS student's data.

╔══════════════════════════════════════════════════════╗
  STUDENT PROFILE
╚══════════════════════════════════════════════════════╝
Target Career  : {career_goal}
Long-term Vision: {vision}
Academic Background: {academic_summary}
Aptitude Scores: {aptitude_summary}
Personality / Learning Style: {personality_summary}
Daily Study Availability: {study_hours}
Financial Constraints: {financial_context}

╔══════════════════════════════════════════════════════╗
  MENTOR ACTION ITEMS  ← HIGH PRIORITY, address these first
╚══════════════════════════════════════════════════════╝
{mentor_action_items}

╔══════════════════════════════════════════════════════╗
  PARENT OBSERVATIONS  ← behavioral context
╚══════════════════════════════════════════════════════╝
{parent_observations}

╔══════════════════════════════════════════════════════╗
  MANDATORY RULES
╚══════════════════════════════════════════════════════╝
1. The roadmap title and every phase must directly serve "{career_goal}". \
   Never substitute with a generic career path.
2. Start from the student's ACTUAL level — derive it from their academic/aptitude data. \
   Do not assume prior knowledge they haven't demonstrated.
3. Respect study availability: fewer hours = fewer topics, higher ruthless prioritization.
4. If mentor flagged specific gaps, those skills MUST appear in Phase 1 or Phase 2.
5. If parent noted behavioral issues (distraction, stress, inconsistency), \
   embed matching study-habit strategies into the relevant phase description.
6. Every task must start with an action verb and be completable in one 2–4 hour session.
7. Resources must be free or affordable: official docs, YouTube, freeCodeCamp, \
   The Odin Project, MDN, GitHub repos, open textbooks. No paid gatekeeping unless critical.
8. The milestone_project per phase must be a real, buildable deliverable for a portfolio.
9. success_criteria must be objectively measurable \
   (e.g., "Build X from scratch without reference" or "Score 80%+ on Y practice test").
10. Generate exactly 5 phases covering the full stated duration realistically.
11. In mentor_adjustments, explicitly state which mentor action items you addressed and where.
12. In parent_adjustments, explicitly state how you adapted the plan to parent observations.

{format_instructions}
"""


# ── LLM Helpers ──────────────────────────────────────────────────────────────

def _build_llm(api_key: str, base_url: str, model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.2,
        max_tokens=6000,
        model_kwargs={"top_p": 0.9}
    )


async def generate_roadmap(
    career_goal: str,
    vision: str = "",
    academic_summary: str = "Not provided",
    aptitude_summary: str = "Not provided",
    personality_summary: str = "Not provided",
    study_hours: str = "2-3 hours/day",
    financial_context: str = "Standard",
    mentor_action_items: str = "None",
    parent_observations: str = "None",
) -> CareerRoadmapResponse:
    parser = PydanticOutputParser(pydantic_object=CareerRoadmapResponse)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _GOLD_SYSTEM_PROMPT),
        ("human", "Generate the personalized roadmap for career goal: {career_goal}"),
    ])
    
    invoke_args = {
        "career_goal": career_goal,
        "vision": vision or career_goal,
        "academic_summary": academic_summary,
        "aptitude_summary": aptitude_summary,
        "personality_summary": personality_summary,
        "study_hours": study_hours,
        "financial_context": financial_context,
        "mentor_action_items": mentor_action_items,
        "parent_observations": parent_observations,
        "format_instructions": parser.get_format_instructions(),
    }

    # USE DEEPSEEK ONLY
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise HTTPException(
            status_code=500,
            detail="DeepSeek API key is missing. Check your environment variables."
        )

    try:
        # Standardized helper call for DeepSeek
        llm = _build_llm(deepseek_key, "https://api.deepseek.com", "deepseek-chat")
        chain = prompt | llm | parser
        
        response = await chain.ainvoke(invoke_args)
        
        if not response:
            raise ValueError("AI returned an empty response")
            
        return response

    except Exception as e:
        logger.error(f"DeepSeek Generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Roadmap generation failed: {str(e)}"
        )


# ── Context Extractors ────────────────────────────────────────────────────────

def _academic_summary(data: Optional[dict]) -> str:
    if not isinstance(data, dict):
        return "Not provided"
    keys = [
        ("overall_percentage_band", "Grade band"),
        ("strongest_subject", "Strong in"),
        ("weakest_subject", "Weak in"),
        ("favorite_subject", "Enjoys"),
        ("learning_style", "Learning style"),
        ("study_hours_home", "Study hours at home"),
    ]
    parts = [f"{label}: {data[k]}" for k, label in keys if data.get(k)]
    return "; ".join(parts) or "Not provided"


def _aptitude_summary(data: Optional[dict]) -> str:
    if not isinstance(data, dict):
        return "Not provided"
    score_keys = [
        ("quantitative", "Quantitative"), ("quantitative_score", "Quantitative"),
        ("logical", "Logical Reasoning"), ("logical_score", "Logical Reasoning"),
        ("verbal", "Verbal"), ("verbal_score", "Verbal"),
    ]
    seen = set()
    parts = []
    for k, label in score_keys:
        if data.get(k) and label not in seen:
            parts.append(f"{label}: {data[k]}")
            seen.add(label)
    return "; ".join(parts) if parts else str(data)[:300]


def _personality_summary(data: Optional[dict]) -> str:
    if not isinstance(data, dict):
        return "Not provided"
    trait_map = {
        "O": "Openness/Creative", "C": "Conscientiousness/Disciplined",
        "E": "Extraversion/Social", "A": "Agreeableness/Empathetic",
        "N": "Neuroticism/Stress-prone",
    }
    parts = []
    if data.get("dominant_traits"):
        readable = [trait_map.get(t, t) for t in data["dominant_traits"]]
        parts.append(f"Dominant: {', '.join(readable)}")
    if data.get("scores"):
        parts.append(f"OCEAN scores: {data['scores']}")
    return "; ".join(parts) or "Not provided"


def _study_hours(lifestyle: Optional[dict]) -> str:
    if not isinstance(lifestyle, dict):
        return "Not specified"
    val = lifestyle.get("study_hours") or lifestyle.get("study_hours_home") or ""
    return str(val) if val else "2-3 hours/day"


def _financial_context(data: Optional[dict]) -> str:
    if not isinstance(data, dict):
        return "Standard"
    keys = [
        ("income_band", "Income"), ("affordability_level", "Affordability"),
        ("coaching_access", "Coaching access"),
    ]
    parts = [f"{label}: {data[k]}" for k, label in keys if data.get(k)]
    return "; ".join(parts) or "Standard"


# ── Generation Endpoint ──────────────────────────────────────────────────────────

@router.get("/generate", response_model=CareerRoadmapResponse)
async def get_career_roadmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    career: Optional[str] = Query(
        default=None,
        description="Career title override — sent by the frontend from the student's AI recommendation selection.",
    ),
):
    career_goal = (
        career
        or (
            isinstance(current_user.aspiration_data, dict)
            and (
                current_user.aspiration_data.get("dream_career")
                or current_user.aspiration_data.get("life_direction")
            )
        )
        or "Software Engineer"
    )
    if not isinstance(career_goal, str):
        career_goal = "Software Engineer"

    vision = ""
    if isinstance(current_user.aspiration_data, dict):
        vision = (
            current_user.aspiration_data.get("ten_year_vision")
            or current_user.aspiration_data.get("five_year_goal")
            or ""
        )

    mentor_rows = db.query(MentorFeedback).filter(MentorFeedback.student_id == current_user.id).order_by(MentorFeedback.submitted_at.desc()).limit(3).all()
    mentor_action_items = "\n".join(f"• {r.action_items}" for r in mentor_rows if r.action_items) or "None"

    parent_rows = db.query(ParentFeedback).filter(ParentFeedback.student_id == current_user.id).order_by(ParentFeedback.logged_at.desc()).limit(3).all()
    parent_observations = "\n".join(f"• Study habits: {r.study_habits or 'N/A'} | Behavior: {r.behavior_insights or 'N/A'}" for r in parent_rows) or "None"

    return await generate_roadmap(
        career_goal=career_goal,
        vision=vision,
        academic_summary=_academic_summary(current_user.academic_data),
        aptitude_summary=_aptitude_summary(current_user.apti_data),
        personality_summary=_personality_summary(current_user.personality_data),
        study_hours=_study_hours(current_user.lifestyle_data),
        financial_context=_financial_context(current_user.financial_data),
        mentor_action_items=mentor_action_items,
        parent_observations=parent_observations,
    )


# ── Persistence Endpoints ────────────────────────────────────────────────────────

@router.post("/save", status_code=201)
def save_roadmap(body: CareerRoadmapResponse, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Remove existing roadmap for this student
    db.query(Roadmap).filter(Roadmap.student_id == current_user.id).delete()
    
    new_roadmap = Roadmap(
        student_id=current_user.id,
        title=body.career_title,
        description=f"Level: {body.student_level} | Duration: {body.total_duration}",
        status="Overview"
    )
    db.add(new_roadmap)
    db.flush() # Get roadmap ID

    for p_idx, p_data in enumerate(body.phases):
        phase = RoadmapPhase(
            roadmap_id=new_roadmap.id,
            sequence=p_idx + 1,
            title=p_data.phase_title,
            status="Not Started"
        )
        db.add(phase)
        db.flush()

        # Add weekly tasks as atomic roadmap tasks
        for w_idx, w_data in enumerate(p_data.weekly_breakdown):
            for t_idx, t_text in enumerate(w_data.tasks):
                task = RoadmapTask(
                    phase_id=phase.id,
                    sequence=(w_idx * 10) + t_idx,
                    title=f"Week {w_data.week_number}: {t_text}",
                    status="Not Started"
                )
                db.add(task)
    
    db.commit()
    return {"message": "Roadmap persisted successfully.", "roadmap_id": new_roadmap.id}


@router.post("/start")
def start_roadmap(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roadmap = db.query(Roadmap).filter(Roadmap.student_id == current_user.id).first()
    if not roadmap: raise HTTPException(status_code=404, detail="No roadmap found.")
    
    roadmap.status = "Active"
    # Mark first phase as Active
    first_phase = db.query(RoadmapPhase).filter(RoadmapPhase.roadmap_id == roadmap.id).order_by(RoadmapPhase.sequence).first()
    if first_phase:
        first_phase.status = "Active"
    
    db.commit()
    return {"message": "Journey started!"}


@router.get("/current", response_model=RoadmapResponse)
def get_current_roadmap(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roadmap = db.query(Roadmap).filter(Roadmap.student_id == current_user.id).first()
    if not roadmap: raise HTTPException(status_code=404, detail="No active roadmap.")
    return roadmap


@router.patch("/tasks/{task_id}/complete")
def toggle_task_completion(task_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(RoadmapTask).join(RoadmapPhase).join(Roadmap).filter(
        RoadmapTask.id == task_id, Roadmap.student_id == current_user.id
    ).first()
    
    if not task: raise HTTPException(status_code=404)
    
    # Toggle status
    task.status = "Completed" if task.status == "Not Started" else "Not Started"
    db.flush()

    # Update Phase Progress
    phase = task.phase
    total_tasks = db.query(RoadmapTask).filter(RoadmapTask.phase_id == phase.id).count()
    completed_tasks = db.query(RoadmapTask).filter(RoadmapTask.phase_id == phase.id, RoadmapTask.status == "Completed").count()
    phase.progress_percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    
    if phase.progress_percentage == 100:
        phase.status = "Completed"
    elif phase.progress_percentage > 0:
        phase.status = "Active"

    # Update Roadmap Progress
    roadmap = phase.roadmap
    all_phases = db.query(RoadmapPhase).filter(RoadmapPhase.roadmap_id == roadmap.id).all()
    avg_progress = sum(p.progress_percentage for p in all_phases) / len(all_phases) if all_phases else 0
    roadmap.progress_percentage = avg_progress
    
    if roadmap.progress_percentage == 100:
        roadmap.status = "Completed"

    db.commit()
    return {"new_status": task.status, "phase_progress": phase.progress_percentage, "total_progress": roadmap.progress_percentage}
