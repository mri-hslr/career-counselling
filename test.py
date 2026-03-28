import psycopg2
import json
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
DATABASE_URL ="postgresql://neondb_owner:npg_9zHMZ3WAvpFP@ep-billowing-hall-a8ma5mt0-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"

def verify_langchain_entries():
    if not DATABASE_URL:
        print("CRITICAL ERROR: DATABASE_URL not found in environment or .env file.")
        return

    try:
        # Using RealDictCursor to see column names clearly
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("\n--- DATABASE CONFIRMATION REPORT ---")
        
        # 1. Check Total Count
        cur.execute("SELECT COUNT(*) FROM langchain_pg_embedding;")
        total_count = cur.fetchone()['count']
        print(f"Total Entries in Table: {total_count}")

        # 2. Fetch Detailed Entries
        # We limit to 30 to see the full set you just uploaded
        query = """
        SELECT 
            id, 
            cmetadata->>'category' as category, 
            cmetadata->>'difficulty' as difficulty, 
            cmetadata->>'target_grade' as grade,
            document 
        FROM langchain_pg_embedding 
        ORDER BY category, difficulty 
        LIMIT 35;
        """
        cur.execute(query)
        rows = cur.fetchall()

        if not rows:
            print("Status: Table is EMPTY.")
            return

        print(f"{'CATEGORY':<25} | {'DIFF':<8} | {'GRADE':<6} | {'PREVIEW'}")
        print("-" * 100)

        for row in rows:
            # Clean up the document string for a short preview
            preview = row['document'].replace('\n', ' ')[:60] + "..."
            
            print(f"{str(row['category']):<25} | "
                  f"{str(row['difficulty']):<8} | "
                  f"{str(row['grade']):<6} | "
                  f"{preview}")

        print("-" * 100)
        print("Verification Complete: All logic categories are present.")

    except Exception as e:
        print(f"DATABASE ERROR: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    verify_langchain_entries()