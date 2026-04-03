import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import Routers
from api.v1.auth import router as auth_router
from api.v1.submit import router as submit_router
from api.v1.ques import router as ques_router
from api.v1.aptitude import router as aptitude_router
from api.v1.profile import router as profile_router
from api.v1.career import router as career_router
from api.v1.roadmap import router as roadmap_router
from router.personality import router as personality_router
from api.v1.mentor import router as mentor_router
from api.v1.parent import router as parent_router
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Career Counseling AI API",
    description="Multilingual AI-driven career guidance platform",
    version="1.0.0"
)

# CORS configuration for React frontend
# allow_origins=["*"] is incompatible with allow_credentials=True — browsers
# reject that combination. JWT is sent via Authorization header (not a cookie),
# so credentials=False is correct and sufficient.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routes
app.include_router(auth_router)
app.include_router(roadmap_router)
app.include_router(ques_router)
app.include_router(submit_router)
app.include_router(aptitude_router)
app.include_router(profile_router)
app.include_router(career_router)
app.include_router(personality_router)
app.include_router(mentor_router)
app.include_router(parent_router)
@app.get("/")
async def root():
    return {"message": "Career Counseling AI API is running."}