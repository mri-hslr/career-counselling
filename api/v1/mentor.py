import logging
from datetime import datetime, timedelta, time, date
from uuid import UUID
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, 
    WebSocket, WebSocketDisconnect, status
)
from jose import jwt, JWTError
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from core.database import get_db
from core.security import SECRET_KEY, ALGORITHM
from api.deps import get_current_user
from models.users import User, UserRole
from models.mentorship import (
    Mentor, MentorAvailability, SessionLog, 
    ChatMessage, MentorshipRequest
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Mentorship"])

# Semantic Search Model
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

# ── Utilities ──────────────────────────────────────────────────────────────

def get_next_weekday(start_date: date, weekday: int):
    """weekday: 1=Mon, 7=Sun."""
    days_ahead = (weekday - 1) - start_date.weekday()
    if days_ahead <= 0: 
        days_ahead += 7
    return start_date + timedelta(days_ahead)

# ── Connection Manager ──────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(room, []).append(ws)

    def disconnect(self, room: str, ws: WebSocket):
        if ws in self._rooms.get(room, []):
            self._rooms[room].remove(ws)

    async def broadcast(self, room: str, payload: dict):
        for ws in self._rooms.get(room, []):
            try:
                await ws.send_json(payload)
            except:
                pass

manager = ConnectionManager()

# ── SCHEMAS ────────────────────────────────────────────────────────────────

class MentorResponse(BaseModel):
    id: UUID
    user_id: UUID
    expertise: str
    bio: Optional[str] = None
    years_experience: int
    rating: float
    is_verified: bool
    class Config:
        from_attributes = True

class MentorProfileIn(BaseModel):
    expertise: str
    bio: Optional[str] = None
    years_experience: int = 0

class AvailabilitySlotIn(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7)
    start_time: time
    end_time: time

class MentorAvailabilityUpdate(BaseModel):
    slots: List[AvailabilitySlotIn]

class RequestIn(BaseModel):
    mentor_id: UUID
    availability_id: UUID 
    message: Optional[str] = None

class UpcomingSessionResponse(BaseModel):
    session_id: UUID
    scheduled_at: datetime
    other_party_name: str
    is_live: bool
    seconds_until_start: int

# ── PROFILE & AI SEARCH ───────────────────────────────────────────────────

@router.post("/profiles/mentors/", status_code=201)
def create_mentor_profile(body: MentorProfileIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(status_code=403, detail="Mentor role required.")
    
    try:
        vector = embed_model.encode(body.expertise).tolist()
        mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
        
        if mentor:
            # Update existing profile
            mentor.expertise = body.expertise
            mentor.expertise_vector = vector
            mentor.bio = body.bio
            mentor.years_experience = body.years_experience
            message = "AI-indexed profile updated."
        else:
            # Create new profile
            mentor = Mentor(
                user_id=current_user.id,
                expertise=body.expertise,
                expertise_vector=vector,
                bio=body.bio,
                years_experience=body.years_experience,
                is_verified=True
            )
            db.add(mentor)
            message = "AI-indexed profile created."
        
        db.commit()
        return {"message": message}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating/updating mentor profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error occurred during profile processing.")

@router.get("/profiles/mentors/me", response_model=MentorResponse)
def get_my_mentor_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetches the mentor profile for the currently logged-in user."""
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(status_code=403, detail="Access denied. Mentor role required.")
        
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    
    if not mentor:
        # Returns 404 so the React frontend knows to show the "Create Profile" form
        raise HTTPException(status_code=404, detail="Mentor profile not found.")
        
    return mentor

@router.get("/mentorship/search/", response_model=List[MentorResponse])
def search_mentors(career_goal: str = Query(...), db: Session = Depends(get_db)):
    search_vector = embed_model.encode(career_goal).tolist()
    results = (
        db.query(Mentor)
        .filter(Mentor.is_verified == True)
        .order_by(Mentor.expertise_vector.cosine_distance(search_vector))
        .limit(5).all()
    )
    return results

# ── MENTOR AVAILABILITY ───────────────────────────────────────────────────

@router.post("/availability/", status_code=201)
def set_mentor_availability(body: MentorAvailabilityUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(status_code=403)

    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    if not mentor: raise HTTPException(status_code=404)

    db.query(MentorAvailability).filter(MentorAvailability.mentor_id == mentor.id, MentorAvailability.is_booked == False).delete()

    new_slots = []
    for slot in body.slots:
        current_start = datetime.combine(date.today(), slot.start_time)
        actual_end = datetime.combine(date.today(), slot.end_time)
        while current_start + timedelta(hours=1) <= actual_end:
            new_slots.append(MentorAvailability(
                mentor_id=mentor.id, day_of_week=slot.day_of_week,
                start_time=current_start.time(), end_time=(current_start + timedelta(hours=1)).time()
            ))
            current_start += timedelta(hours=1)

    db.add_all(new_slots)
    db.commit()
    return {"message": f"Created {len(new_slots)} atomic slots."}

# ── REQUESTS & DASHBOARD ───────────────────────────────────────────────────

@router.get("/requests/pending/")
def get_pending_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    if not mentor: raise HTTPException(status_code=403)

    pending = (
        db.query(MentorshipRequest, User.full_name, MentorAvailability)
        .join(User, MentorshipRequest.student_id == User.id)
        .join(MentorAvailability, MentorshipRequest.availability_id == MentorAvailability.id)
        .filter(MentorshipRequest.mentor_id == mentor.id, MentorshipRequest.status == "pending")
        .all()
    )
    return [{"request_id": r[0].id, "student_name": r[1], "time_slot": f"Day {r[2].day_of_week}: {r[2].start_time}"} for r in pending]

@router.get("/sessions/upcoming", response_model=List[UpcomingSessionResponse])
def get_upcoming_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now()
    sessions = db.query(SessionLog).filter(
        ((SessionLog.student_id == current_user.id) | (SessionLog.mentor_id == current_user.id)),
        SessionLog.status == "scheduled",
        SessionLog.scheduled_at >= (now - timedelta(hours=1))
    ).all()

    res = []
    for s in sessions:
        other_id = s.mentor_id if current_user.id == s.student_id else s.student_id
        other_user = db.query(User).filter(User.id == other_id).first()
        res.append({
            "session_id": s.id,
            "scheduled_at": s.scheduled_at,
            "other_party_name": other_user.full_name if other_user else "User",
            "is_live": now >= s.scheduled_at,
            "seconds_until_start": int((s.scheduled_at - now).total_seconds())
        })
    return res
# ── Task: Get Single Mentor Profile ────────────────────────────────────────

@router.get("/mentorship/mentors/{mentor_id}", response_model=MentorResponse)
def get_mentor_detail(mentor_id: UUID, db: Session = Depends(get_db)):
    mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
    
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found.")
        
    # We want to make sure the full_name from the User model is accessible
    # If your MentorResponse schema doesn't include it, you might want to 
    # return a custom dictionary or update the schema.
    return mentor

@router.post("/requests/{request_id}/approve")
async def approve_request(request_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    req = db.query(MentorshipRequest).filter(MentorshipRequest.id == request_id).first()
    
    if not req or req.mentor_id != mentor.id: raise HTTPException(status_code=404)
    slot = db.query(MentorAvailability).filter(MentorAvailability.id == req.availability_id).first()
    
    slot.is_booked = True
    req.status = "approved"
    session_date = get_next_weekday(date.today(), slot.day_of_week)
    
    session = SessionLog(
        student_id=req.student_id, mentor_id=req.mentor_id, 
        scheduled_at=datetime.combine(session_date, slot.start_time),
        status="scheduled"
    )
    db.add(session)
    db.commit()
    return {"session_id": session.id, "scheduled_at": session.scheduled_at}

# ── SESSION CONTROL & WEBSOCKET ───────────────────────────────────────────

@router.post("/sessions/{session_id}/end")
async def end_session(session_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Only the Mentor can officially trigger the end-of-session workflow."""
    session = db.query(SessionLog).filter(SessionLog.id == session_id).first()
    if not session: raise HTTPException(status_code=404)

    # Validate that the person ending it is the mentor for this session
    mentor_profile = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    if not mentor_profile or session.mentor_id != mentor_profile.id:
        raise HTTPException(status_code=403, detail="Only the mentor can end this session.")

    # 1. Update DB Status
    session.status = "completed"
    db.commit()

    # 2. Broadcast 'SESSION_ENDED' event to the Room
    # Both student and mentor UI will listen for this to show feedback/close chat
    await manager.broadcast(str(session_id), {
        "event": "SESSION_ENDED",
        "message": "The mentor has concluded the session. Redirecting to feedback...",
        "session_id": str(session_id)
    })
    
    return {"message": "Session marked as completed."}

@router.websocket("/mentorship/sessions/{session_id}/chat/")
async def websocket_chat(websocket: WebSocket, session_id: UUID, token: str = Query(...), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
    except JWTError:
        await websocket.close(code=1008)
        return

    user = db.query(User).filter(User.email == email).first()
    session = db.query(SessionLog).filter(SessionLog.id == session_id).first()
    
    if not user or not session:
        await websocket.close(code=1008)
        return

    # Gatekeeper: Block early entry (More than 2 mins before)
    now = datetime.now()
    if now < (session.scheduled_at - timedelta(minutes=2)):
        await websocket.accept()
        await websocket.send_json({"event": "ERROR", "message": "Room is still locked."})
        await websocket.close(code=4003)
        return

    # Block if session is already concluded
    if session.status == "completed":
        await websocket.accept()
        await websocket.send_json({"event": "ERROR", "message": "This session has already ended."})
        await websocket.close(code=4003)
        return

    await manager.connect(str(session_id), websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_text = data.get('message', '').strip()
            if msg_text:
                # Store message in DB
                db.add(ChatMessage(session_id=session_id, sender_id=user.id, message=msg_text))
                db.commit()
                # Broadcast real-time
                await manager.broadcast(str(session_id), {
                    "event": "NEW_MESSAGE",
                    "sender": user.full_name, 
                    "message": msg_text,
                    "timestamp": datetime.now().isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(str(session_id), websocket)
        
@router.post("/requests/create", status_code=201)
def request_mentorship(body: RequestIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Check if slot exists
    slot = db.query(MentorAvailability).filter(MentorAvailability.id == body.availability_id).first()
    if not slot or slot.is_booked:
        raise HTTPException(status_code=400, detail="Slot unavailable.")

    # 2. NEW: Check if someone else already has a pending request for this specific slot
    existing_request = db.query(MentorshipRequest).filter(
        MentorshipRequest.availability_id == body.availability_id,
        MentorshipRequest.status == "pending"
    ).first()
    
    if existing_request:
        raise HTTPException(
            status_code=400, 
            detail="This slot is currently being reviewed for another student. Please pick another time."
        )

    # 3. Create request
    new_request = MentorshipRequest(
        student_id=current_user.id,
        mentor_id=body.mentor_id,
        availability_id=body.availability_id,
        message=body.message,
        status="pending"
    )
    db.add(new_request)
    db.commit()
    return {"message": "Request sent to mentor."}


@router.get("/availability/{mentor_id}")
def get_mentor_availability(mentor_id: UUID, db: Session = Depends(get_db)):
    """NEW: Returns unbooked slots for a specific mentor."""
    slots = db.query(MentorAvailability).filter(
        MentorAvailability.mentor_id == mentor_id,
        MentorAvailability.is_booked == False
    ).all()
    return slots