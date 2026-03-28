import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

router = APIRouter(prefix="/api/v1/career", tags=["Career Roadmap"])

class WeeklyTask(BaseModel):
    week_number: int
    topic: str = Field(description="The core focus of this specific week")
    tasks: List[str] = Field(description="3-4 high-impact actionable items")

class RoadmapPhase(BaseModel):
    phase_title: str
    description: str
    importance: str = Field(description="CRITICAL | STRATEGIC | SPECIALIZATION")
    duration_weeks: int
    weekly_breakdown: List[WeeklyTask]
    milestone_project: str = Field(description="A specific project to validate this phase")

class CareerRoadmapResponse(BaseModel):
    career_title: str
    difficulty_level: str
    total_duration: str
    phases: List[RoadmapPhase]

@router.get("/roadmap", response_model=CareerRoadmapResponse)
async def get_career_roadmap():
    target_job = "Full Stack Software Engineer (Node/React/Postgres)"
    GROQ_API_KEY=os.getenv("GROQ_API_KEY")
    
    # Groq is compatible with ChatOpenAI client by changing base_url
    llm = ChatOpenAI(
        model="llama-3.3-70b-versatile", 
        openai_api_key=GROQ_API_KEY, 
        openai_api_base="https://api.groq.com/openai/v1",
        temperature=0.2 # Lower temperature for better JSON structure adherence
    )
    
    parser = PydanticOutputParser(pydantic_object=CareerRoadmapResponse)

    system_prompt = """
    You are an Elite Curriculum Architect. Generate a hyper-specific, 6-month weekly roadmap for becoming a {job}.
    
    STRATEGIC GUIDELINES:
    1. NODAL STRUCTURE: Break the journey into 5 distinct phases. Each phase MUST contain a weekly breakdown.
    2. DEPTH: Week 1 shouldn't just be 'Learn HTML'. It should be 'Semantic HTML & Accessibility Standards'.
    3. MODERN STACK: Default to TypeScript, Next.js (App Router), Tailwind CSS, PostgreSQL (Prisma), and Docker.
    4. TASKS: Every task must be an action (e.g., 'Implement JWT using jose', not 'Read about JWT').
    
    {format_instructions}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Build a high-velocity 6-month Nodal Roadmap for: {job}.")
    ])

    try:
        chain = prompt | llm | parser
        response = chain.invoke({
            "job": target_job,
            "format_instructions": parser.get_format_instructions()
        })
        return response
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Roadmap Generation Failed via Groq Engine.")