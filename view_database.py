import os
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from tabulate import tabulate
import json

# Load environment variables
load_dotenv()

# Get database connection string
db_url = os.environ.get('DATABASE_URL')

def view_table(table_name):
    """View all records in a specified table"""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(sql.SQL("SELECT * FROM {} LIMIT 0").format(sql.Identifier(table_name)))
        colnames = [desc[0] for desc in cursor.description]
        
        # Get all records
        cursor.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name)))
        rows = cursor.fetchall()
        
        # Print table
        if rows:
            print(f"\n=== {table_name.upper()} TABLE ===")
            
            # For students table, truncate long fields for better display
            if table_name.lower() == 'students':
                formatted_rows = []
                for row in rows:
                    formatted_row = list(row)
                    # Truncate face_encoding and profile_image if they exist
                    for i, col in enumerate(colnames):
                        if col in ['face_encoding', 'profile_image'] and formatted_row[i]:
                            if len(str(formatted_row[i])) > 30:
                                formatted_row[i] = str(formatted_row[i])[:30] + "..."
                    formatted_rows.append(formatted_row)
                print(tabulate(formatted_rows, headers=colnames, tablefmt="grid"))
            else:
                print(tabulate(rows, headers=colnames, tablefmt="grid"))
                
            print(f"Total records: {len(rows)}")
        else:
            print(f"\nNo records found in {table_name} table.")
            
            # If this is the student table, let's check if it exists and has the right structure
            if table_name.lower() == 'students':
                print("\nChecking students table structure...")
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'students'
                """)
                columns = cursor.fetchall()
                
                if columns:
                    print("\nStudents table structure:")
                    print(tabulate(columns, headers=["Column", "Type"], tablefmt="grid"))
                    
                    # Check for recent inserts
                    try:
                        cursor.execute("""
                            SELECT * FROM pg_stat_user_tables
                            WHERE relname = 'students'
                        """)
                        stats = cursor.fetchone()
                        if stats:
                            print("\nTable statistics:")
                            print(f"Inserts: {stats[5]}")
                            print(f"Updates: {stats[6]}")
                            print(f"Deletes: {stats[7]}")
                            print(f"Live rows: {stats[9]}")
                            print(f"Dead rows: {stats[10]}")
                    except Exception as e:
                        print(f"Could not check table statistics: {str(e)}")
                else:
                    print(f"Table 'students' exists but has no columns defined.")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if conn:
            conn.close()

def examine_students_table():
    """Specifically examine the students table in detail"""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check if students table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'students'
            )
        """)
        students_exists = cursor.fetchone()[0]
        
        if not students_exists:
            print("\nThe 'students' table does not exist in the database.")
            return
        
        # Check for any records using a direct count
        cursor.execute("SELECT COUNT(*) FROM students")
        count = cursor.fetchone()[0]
        
        print(f"\nFound {count} records in the students table.")
        
        if count > 0:
            # Try to get just the IDs and names to verify data exists
            cursor.execute("SELECT id, name FROM students")
            students = cursor.fetchall()
            print("\nStudent IDs and Names:")
            print(tabulate(students, headers=["ID", "Name"], tablefmt="grid"))
            
            # Check a specific student record in detail
            if students:
                student_id = students[0][0]  # Get the first student's ID
                cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
                student = cursor.fetchone()
                
                if student:
                    cursor.execute("SELECT * FROM students LIMIT 0")
                    colnames = [desc[0] for desc in cursor.description]
                    
                    print(f"\nDetailed record for student ID: {student_id}")
                    for i, col in enumerate(colnames):
                        value = student[i]
                        if col in ['face_encoding', 'profile_image'] and value:
                            print(f"{col}: [Data length: {len(str(value))} characters]")
                        else:
                            print(f"{col}: {value}")
        else:
            # Check constraints that might be preventing inserts
            cursor.execute("""
                SELECT conname, contype, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'students'::regclass
            """)
            constraints = cursor.fetchall()
            
            if constraints:
                print("\nTable constraints that might be preventing inserts:")
                print(tabulate(constraints, headers=["Name", "Type", "Definition"], tablefmt="grid"))
                
            # Check if there are any errors in recent logs
            try:
                cursor.execute("""
                    SELECT * FROM pg_stat_activity 
                    WHERE query LIKE '%INSERT%INTO%students%'
                    ORDER BY query_start DESC
                    LIMIT 5
                """)
                activities = cursor.fetchall()
                
                if activities:
                    print("\nRecent INSERT activities:")
                    for act in activities:
                        print(f"- {act}")
            except Exception as e:
                print(f"Could not check pg_stat_activity: {str(e)}")
                
    except Exception as e:
        print(f"Error examining students table: {str(e)}")
    finally:
        if conn:
            conn.close()

def list_tables():
    """List all tables in the database"""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Query to get all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        
        print("\n=== AVAILABLE TABLES ===")
        for i, table in enumerate(tables, 1):
            print(f"{i}. {table[0]}")
            
        return [table[0] for table in tables]
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Database Viewer")
    print("===============")
    
    tables = list_tables()
    
    if not tables:
        print("No tables found or couldn't connect to the database.")
        exit()
    
    # First, specifically examine the students table
    print("\nExamining students table in detail...")
    examine_students_table()
    
    while True:
        try:
            choice = input("\nEnter table number to view (or 'q' to quit): ")
            
            if choice.lower() == 'q':
                break
                
            table_index = int(choice) - 1
            if 0 <= table_index < len(tables):
                view_table(tables[table_index])
            else:
                print("Invalid table number.")
                
        except ValueError:
            print("Please enter a valid number or 'q'.")
        except Exception as e:
            print(f"Error: {str(e)}")