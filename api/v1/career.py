import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from core.database import get_db
from api.deps import get_current_user
from models.users import User

router = APIRouter(prefix="/api/v1/ai", tags=["DeepSeek Career Engine"])

class CareerOption(BaseModel):
    title: str = Field(description="Career title")
    rationale: str = Field(description="Why this fits")

class AIRecommendationResponse(BaseModel):
    brutal_truth_summary: str = Field(description="Honest assessment of the student's trajectory")
    top_5_careers: List[CareerOption] = Field(description="5 tailored career paths")

@router.post("/recommend", response_model=AIRecommendationResponse)
async def generate_career_roadmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u = current_user
    
    # 1. Collect all confirmed JSONB data from the current user
    data = {
        "academic": u.academic_data,
        "lifestyle": u.lifestyle_data,
        "aspiration": u.aspiration_data,
        "personality": u.personality_data,
        "aptitude": u.apti_data,
        "financial": u.financial_data
    }

    # 2. Basic Validation: Ensure critical data exists before calling AI
    if not u.academic_data or not u.lifestyle_data:
        raise HTTPException(
            status_code=400, 
            detail="Assessment data incomplete. Please fill out Academic and Lifestyle modules."
        )

    # 3. AI Execution Configuration
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="DeepSeek API Key not configured in environment.")

    llm = ChatOpenAI(
        model="deepseek-chat", 
        openai_api_key=api_key, 
        openai_api_base="https://api.deepseek.com",
        temperature=0.4
    )
    
    parser = PydanticOutputParser(pydantic_object=AIRecommendationResponse)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Career Counselor. Analyze the student's data and provide a realistic career roadmap. {format_instructions}"),
        ("human", "Analyze this student data: {data}")
    ])

    try:
        # 4. Generate AI response
        chain = prompt | llm | parser
        response = chain.invoke({
            "data": str(data), 
            "format_instructions": parser.get_format_instructions()
        })
        
        # NOTE: u.ai_insight_summary logic removed as requested.
        # No db.commit() needed here since we aren't modifying the User record.
        
        return response
        
    except Exception as e:
        # Log the error for debugging
        print(f"AI Engine Error: {str(e)}")
        raise HTTPException(status_code=500, detail="The AI Career Engine failed to generate a response.")