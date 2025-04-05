import os
from dotenv import load_dotenv
import psycopg2
import json
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# Get database connection string
db_url = os.environ.get('DATABASE_URL')

def insert_test_student():
    """Insert a test student directly into the database"""
    conn = None
    try:
        # Connect to the database
        print("Connecting to database...")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Create a test student
        student_id = "TEST123"
        name = "Test Student"
        password_hash = generate_password_hash("password123")
        class_name = "Test Class"
        
        # Simple face encoding (just a placeholder)
        face_encoding = json.dumps([0.1, 0.2, 0.3, 0.4, 0.5])
        
        # Check if student already exists
        cursor.execute("SELECT COUNT(*) FROM students WHERE id = %s", (student_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"Student with ID {student_id} already exists. Skipping insert.")
            return
        
        # Insert the student
        print("Inserting test student...")
        cursor.execute("""
            INSERT INTO students (id, name, password_hash, class_name, face_encoding, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (student_id, name, password_hash, class_name, face_encoding))
        
        # Commit the transaction
        conn.commit()
        print("Test student inserted successfully!")
        
        # Verify the insert
        cursor.execute("SELECT id, name, class_name FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if student:
            print(f"Verified student in database: ID={student[0]}, Name={student[1]}, Class={student[2]}")
        else:
            print("Failed to verify student in database after insert.")
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error inserting test student: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Test Student Insertion")
    print("=====================")
    
    insert_test_student()
    
    print("\nDone. Now run view_database.py to check if the student appears.")