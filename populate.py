import psycopg2
import json
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def populate_personality():
    # 40 Questions total: 8 per Module 4 Category [cite: 56, 159]
    questions = [
        # --- CURIOSITY & CREATIVITY (8 Questions) [cite: 57] ---
        ("C1", "Curiosity & Creativity", "Intellectual Depth", "I often spend my free time researching topics mentioned briefly in class.", "positive"),
        ("C2", "Curiosity & Creativity", "Innovation", "I find it boring to learn about subjects that don't directly help me get marks.", "negative"),
        ("C3", "Curiosity & Creativity", "Problem Solving", "I enjoy coming up with multiple unique solutions to a single problem.", "positive"),
        ("C4", "Curiosity & Creativity", "Openness", "I prefer following a set of instructions exactly rather than trying a new way.", "negative"),
        ("C5", "Curiosity & Creativity", "Imagination", "I often imagine how existing technology could be improved in the future.", "positive"),
        ("C6", "Curiosity & Creativity", "Status Quo", "I rarely question why things are done the way they are.", "negative"),
        ("C7", "Curiosity & Creativity", "Discovery", "I like to take things apart to see how they work internally.", "positive"),
        ("C8", "Curiosity & Creativity", "Fixed Mindset", "I believe I am either born with a talent or I am not; I can't change it much.", "negative"),

        # --- DISCIPLINE & CONSISTENCY (8 Questions) [cite: 58] ---
        ("D1", "Discipline & Consistency", "Routine", "I strictly follow a daily study schedule even when exams are far away.", "positive"),
        ("D2", "Discipline & Consistency", "Procrastination", "I often leave my school assignments for the very last minute.", "negative"),
        ("D3", "Discipline & Consistency", "Grit", "When I start a difficult project, I make sure to finish it no matter what.", "positive"),
        ("D4", "Discipline & Consistency", "Organization", "My study area is usually messy and disorganized.", "negative"),
        ("D5", "Discipline & Consistency", "Goal Setting", "I write down my weekly goals and track my progress regularly.", "positive"),
        ("D6", "Discipline & Consistency", "Distractibility", "I find it very hard to stay focused on one task for more than 20 minutes.", "negative"),
        ("D7", "Discipline & Consistency", "Reliability", "If I promise to complete a group task by a certain time, I always meet the deadline.", "positive"),
        ("D8", "Discipline & Consistency", "Impulsiveness", "I often make quick decisions without thinking about the long-term consequences.", "negative"),

        # --- SOCIAL CONFIDENCE (8 Questions) [cite: 59] ---
        ("S1", "Social Confidence", "Leadership", "I feel energetic and comfortable when leading a group discussion.", "positive"),
        ("S2", "Social Confidence", "Introversion", "I prefer working alone rather than in a team where I have to speak up.", "negative"),
        ("S3", "Social Confidence", "Initiative", "I find it easy to start conversations with people I have just met.", "positive"),
        ("S4", "Social Confidence", "Public Speaking", "I get very nervous when I have to present my ideas in front of the class.", "negative"),
        ("S5", "Social Confidence", "Influence", "I am good at' persuading my friends to see things from my perspective.", "positive"),
        ("S6", "Social Confidence", "Social Anxiety", "I worry a lot about what others think of me when I speak in a group.", "negative"),
        ("S7", "Social Confidence", "Networking", "I enjoy meeting new people and learning about their backgrounds.", "positive"),
        ("S8", "Social Confidence", "Passive Behavior", "I usually stay quiet in groups and let others make the final decisions.", "negative"),

        # --- EMPATHY & TEAMWORK (8 Questions) [cite: 60] ---
        ("E1", "Empathy & Teamwork", "Collaboration", "I prioritize the team's harmony over individual success in projects.", "positive"),
        ("E2", "Empathy & Teamwork", "Indifference", "I struggle to understand why people get emotional over small failures.", "negative"),
        ("E3", "Empathy & Teamwork", "Social Awareness", "I naturally notice when a classmate is feeling left out and try to include them.", "positive"),
        ("E4", "Empathy & Teamwork", "Self-Centeredness", "I find it frustrating to have to explain things to teammates who are slower than me.", "negative"),
        ("E5", "Empathy & Teamwork", "Conflict Resolution", "I try to help my friends resolve their arguments instead of taking sides.", "positive"),
        ("E6", "Empathy & Teamwork", "Individualism", "I believe that the best work is always done by individuals, not groups.", "negative"),
        ("E7", "Empathy & Teamwork", "Supportiveness", "I feel genuinely happy when my classmates succeed, even if I didn't.", "positive"),
        ("E8", "Empathy & Teamwork", "Lack of Tact", "I often say what's on my mind even if it might hurt someone's feelings.", "negative"),

        # --- STRESS HANDLING (8 Questions) [cite: 61] ---
        ("H1", "Stress Handling", "Composure", "I stay calm and clear-headed even when facing tight deadlines.", "positive"),
        ("H2", "Stress Handling", "Anxiety", "I get anxious easily when too many tasks are assigned at once.", "negative"),
        ("H3", "Stress Handling", "Adaptability", "Unexpected changes in my schedule rarely upset my focus.", "positive"),
        ("H4", "Stress Handling", "Panic", "When things go wrong, my first reaction is to panic or get frustrated.", "negative"),
        ("H5", "Stress Handling", "Resilience", "After a major failure, I can bounce back and start working again quickly.", "positive"),
        ("H6", "Stress Handling", "Overwhelm", "I often feel overwhelmed by the pressure of my school responsibilities.", "negative"),
        ("H7", "Stress Handling", "Patience", "I can wait patiently for results without getting stressed or restless.", "positive"),
        ("H8", "Stress Handling", "Emotional Volatility", "My mood changes very quickly when I face a small setback.", "negative")
    ]

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Clear existing to avoid ID conflicts
        cur.execute("TRUNCATE TABLE personality_question_bank;")
        
        query = "INSERT INTO personality_question_bank (id, trait, sub_trait, question_text, question_type) VALUES (%s, %s, %s, %s, %s)"
        cur.executemany(query, questions)
        
        conn.commit()
        print(f"Successfully inserted {len(questions)} personality questions across 5 Big Five traits.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    populate_personality()