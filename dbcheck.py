import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def view_hard_logic():
    db_url = os.getenv("DATABASE_URL")
    
    query = """
        SELECT document 
        FROM langchain_pg_embedding 
        WHERE cmetadata->>'target_grade' = '6-8' 
          AND cmetadata->>'category' = 'Logical Reasoning' 
          AND cmetadata->>'difficulty' = 'Easy'
        ORDER BY id ASC;
    """

    try:
        conn = psycopg2.connect(db_url)
        # Use RealDictCursor to access columns by name easily
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(query)
        rows = cur.fetchall()

        if not rows:
            print("⚠️ No Hard Logical Reasoning questions found for Grade 6-8.")
            return

        print(f"🔍 Found {len(rows)} Hard Questions:\n")
        print("="*60)

        for i, row in enumerate(rows, 1):
            print(f"ENTRY #{i}")
            print(row['document'])
            print("-" * 60)

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    view_hard_logic()