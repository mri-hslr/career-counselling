import uuid
from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from models.users import User

# Your specific ID
USER_UUID = "988b1973-77e2-40b7-b609-c3550812d1cb"

def verify_user_json_data():
    db = SessionLocal()
    try:
        # Convert string to UUID object
        target_id = uuid.UUID(USER_UUID)
        
        # Fetch the user
        user = db.query(User).filter(User.id == target_id).first()

        if not user:
            print(f"❌ Error: No user found with ID {USER_UUID}")
            return

        print(f"--- Data Verification for: {user.email} ---")
        print(f"Full Name: {user.full_name}")
        print("-" * 40)

        # List of JSONB fields to check
        json_fields = [
            "academic_data",
            "apti_data",
            "personality_data",
            "lifestyle_data",
            "financial_data",
            "passion_strength_data",
            "aspiration_data",
            "career_interest_data"
        ]

        for field in json_fields:
            data = getattr(user, field)
            status = "✅ Populated" if data else "⚠️ Empty/Null"
            print(f"{field:25} : {status}")
            if data:
                print(f"   Content: {data}")
            print("-" * 40)

    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_user_json_data()