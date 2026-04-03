import logging
from datetime import datetime, timedelta, time, date,timezone
from uuid import UUID
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, 
    WebSocket, WebSocketDisconnect, status
)
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_
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
    days_ahead = (weekday - 1) - start_date.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return start_date + timedelta(days=days_ahead)

# ── Connection Manager ──────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket):
        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(ws)

    def disconnect(self, room: str, ws: WebSocket):
        if room in self._rooms:
            self._rooms[room].discard(ws)
            if not self._rooms[room]:
                del self._rooms[room]

    async def broadcast(self, room: str, payload: dict):
        if room in self._rooms:
            for ws in self._rooms[room]:
                try:
                    await ws.send_json(payload)
                except Exception:
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

# ── PROFILE & SEARCH ──────────────────────────────────────────────────────

@router.post("/profiles/mentors/", status_code=201)
def create_mentor_profile(body: MentorProfileIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(status_code=403, detail="Mentor role required.")
    
    try:
        vector = embed_model.encode(body.expertise).tolist()
        mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
        
        if mentor:
            mentor.expertise = body.expertise
            mentor.expertise_vector = vector
            mentor.bio = body.bio
            mentor.years_experience = body.years_experience
            message = "AI-indexed profile updated."
        else:
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
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error.")

@router.get("/profiles/mentors/me", response_model=MentorResponse)
def get_my_mentor_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(status_code=403, detail="Mentor role required.")
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    if not mentor:
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

@router.get("/mentorship/mentors/{mentor_id}", response_model=MentorResponse)
def get_mentor_detail(mentor_id: UUID, db: Session = Depends(get_db)):
    mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found.")
    return mentor

# ── AVAILABILITY & SESSIONS ───────────────────────────────────────────────

@router.post("/availability/", status_code=201)
def set_mentor_availability(body: MentorAvailabilityUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(status_code=403)
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    if not mentor:
        raise HTTPException(status_code=404)

    db.query(MentorAvailability).filter(
        MentorAvailability.mentor_id == mentor.id,
        MentorAvailability.is_booked == False
    ).delete()

    now = datetime.now()
    today = now.date()
    today_weekday = today.weekday() + 1

    new_slots = []
    for slot in body.slots:
        if slot.day_of_week == today_weekday:
            slot_date = today
            earliest_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            effective_start = max(datetime.combine(slot_date, slot.start_time), earliest_start)
        else:
            days_ahead = (slot.day_of_week - 1) - today.weekday()
            if days_ahead < 0: days_ahead += 7
            slot_date = today + timedelta(days=days_ahead)
            effective_start = datetime.combine(slot_date, slot.start_time)

        actual_end = datetime.combine(slot_date, slot.end_time)
        if effective_start + timedelta(hours=1) > actual_end: continue

        current_start = effective_start
        while current_start + timedelta(hours=1) <= actual_end:
            new_slots.append(MentorAvailability(
                mentor_id=mentor.id,
                day_of_week=slot.day_of_week,
                start_time=current_start.time(),
                end_time=(current_start + timedelta(hours=1)).time()
            ))
            current_start += timedelta(hours=1)

    db.add_all(new_slots)
    db.commit()
    return {"message": f"Created {len(new_slots)} slots."}

@router.get("/sessions/upcoming", response_model=List[UpcomingSessionResponse])
def get_upcoming_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now().replace(tzinfo=None)
    mentor_profile = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    mentor_id = mentor_profile.id if mentor_profile else None

    sessions = db.query(SessionLog).filter(
        or_(SessionLog.student_id == current_user.id, SessionLog.mentor_id == mentor_id),
        SessionLog.status == "scheduled",
        SessionLog.scheduled_at >= (now - timedelta(hours=2))
    ).order_by(SessionLog.scheduled_at.asc()).all()

    res = []
    for s in sessions:
        other_user_name = "User"
        if mentor_id and s.mentor_id == mentor_id:
            student_user = db.query(User).filter(User.id == s.student_id).first()
            other_user_name = student_user.full_name if student_user else "Student"
        else:
            mentor_user = db.query(User).join(Mentor).filter(Mentor.id == s.mentor_id).first()
            other_user_name = mentor_user.full_name if mentor_user else "Mentor"

        sch_naive = s.scheduled_at.replace(tzinfo=None)
        is_live = now >= (sch_naive - timedelta(minutes=5))
        seconds_until_start = int((sch_naive - now).total_seconds())

        res.append({
            "session_id": s.id, "scheduled_at": sch_naive,
            "other_party_name": other_user_name, "is_live": is_live,
            "seconds_until_start": seconds_until_start
        })
    return res

# ── CHAT & REAL-TIME ──────────────────────────────────────────────────────

@router.websocket("/mentorship/sessions/{session_id}/chat/")
async def websocket_chat(
    websocket: WebSocket, 
    session_id: UUID, 
    token: str = Query(...), 
    db: Session = Depends(get_db)
):
    # 1. PRE-ACCEPT AUTHENTICATION (Security Firewall)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("sub")
        if not user_email:
            raise JWTError
    except JWTError:
        # Rejects handshake immediately without leaving a "hanging" socket
        return 

    # 2. DATA CONSISTENCY CHECK
    user = db.query(User).filter(User.email == user_email).first()
    session = db.query(SessionLog).filter(SessionLog.id == session_id).first()
    
    if not user or not session:
        return # Session or User does not exist in DB

    # 3. BULLETPROOF TIME LOGIC (UTC ONLY)
    # Get current UTC time (Aware object)
    now_utc = datetime.now(timezone.utc)
    
    # Force DB timestamp to be UTC Aware
    sch_utc = session.scheduled_at
    if sch_utc.tzinfo is None:
        sch_utc = sch_utc.replace(tzinfo=timezone.utc)

    # Calculate 'Unlocking Time' (exactly 2 mins before the scheduled start)
    # Example: Scheduled 09:30 UTC -> Unlocks at 09:28 UTC
    unlock_time = sch_utc - timedelta(minutes=2)

    # --- EDGE CASE 1: Joining too early ---
    # If it is 2:50 PM IST and start is 3:00 PM IST, block access.
    if now_utc < unlock_time:
        await websocket.accept()
        await websocket.send_json({
            "event": "ERROR", 
            "message": f"Room opens 2 mins before start. (Server: {now_utc.strftime('%H:%M')} UTC)"
        })
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # --- EDGE CASE 2: Session already completed ---
    # Even if the time is right, if the status is 'completed', block entry.
    if session.status == "completed":
        await websocket.accept()
        await websocket.send_json({
            "event": "ERROR", 
            "message": "This session has already concluded."
        })
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # --- EDGE CASE 3: Late Joiner (The "Whenever" Rule) ---
    # If now_utc >= unlock_time AND status != 'completed', the door is OPEN.
    # This naturally handles 3:05 PM, 3:45 PM, etc.

    # 4. ESTABLISH WEBSOCKET CONNECTION
    await websocket.accept()
    await manager.connect(str(session_id), websocket)
    
    try:
        while True:
            # Wait for incoming JSON message
            data = await websocket.receive_json()
            msg_text = data.get('message', '').strip()
            
            if msg_text:
                try:
                    # 5. ATOMIC DB PERSISTENCE
                    new_msg = ChatMessage(
                        session_id=session_id, 
                        sender_id=user.id, 
                        message=msg_text
                    )
                    db.add(new_msg)
                    db.commit()
                    
                    # 6. REAL-TIME BROADCAST
                    await manager.broadcast(str(session_id), {
                        "event": "NEW_MESSAGE", 
                        "sender": user.full_name, 
                        "message": msg_text, 
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except Exception as e:
                    db.rollback()
                    logger.error(f"Persistence Failure: {e}")
                    # Optionally notify user message failed to save
    
    except WebSocketDisconnect:
        manager.disconnect(str(session_id), websocket)
    except Exception as e:
        logger.error(f"WebSocket Runtime Error: {e}")
        manager.disconnect(str(session_id), websocket)
# ── REQUEST MANAGEMENT ────────────────────────────────────────────────────

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

@router.post("/requests/create", status_code=201)
def request_mentorship(body: RequestIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slot = db.query(MentorAvailability).filter(MentorAvailability.id == body.availability_id).first()
    if not slot or slot.is_booked: raise HTTPException(status_code=400, detail="Slot unavailable.")
    
    existing = db.query(MentorshipRequest).filter(MentorshipRequest.availability_id == body.availability_id, MentorshipRequest.status == "pending").first()
    if existing: raise HTTPException(status_code=400, detail="Pending request exists.")

    new_req = MentorshipRequest(student_id=current_user.id, mentor_id=body.mentor_id, availability_id=body.availability_id, message=body.message, status="pending")
    db.add(new_req); db.commit()
    return {"message": "Request sent."}

@router.post("/requests/{request_id}/approve")
async def approve_request(request_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    req = db.query(MentorshipRequest).filter(MentorshipRequest.id == request_id).first()
    if not req or req.mentor_id != mentor.id: raise HTTPException(status_code=404)
    
    slot = db.query(MentorAvailability).filter(MentorAvailability.id == req.availability_id).first()
    slot.is_booked = True; req.status = "approved"
    
    session_date = get_next_weekday(date.today(), slot.day_of_week)
    session = SessionLog(student_id=req.student_id, mentor_id=req.mentor_id, scheduled_at=datetime.combine(session_date, slot.start_time), status="scheduled")
    db.add(session); db.commit()
    return {"session_id": session.id, "scheduled_at": session.scheduled_at}

@router.post("/sessions/{session_id}/end")
async def end_session(session_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(SessionLog).filter(SessionLog.id == session_id).first()
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    if not session or session.mentor_id != mentor.id: raise HTTPException(status_code=403)

    session.status = "completed"; db.commit()
    await manager.broadcast(str(session_id), {"event": "SESSION_ENDED", "message": "Concluded.", "session_id": str(session_id)})
    return {"message": "Session completed."}

@router.get("/availability/{mentor_id}")
def get_mentor_availability(mentor_id: UUID, db: Session = Depends(get_db)):
    pending = db.query(MentorshipRequest.availability_id).filter(MentorshipRequest.status == "pending").subquery()
    return db.query(MentorAvailability).filter(MentorAvailability.mentor_id == mentor_id, MentorAvailability.is_booked == False, ~MentorAvailability.id.in_(pending)).all()