import logging
from datetime import datetime
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

# In-memory data stores
admins = {}
students = {}
attendance_records = []

def initialize_data():
    """Initialize data store with default admin"""
    # Add default admin if not exists
    if not admins:
        add_admin("admin", "admin", "Admin User")
        logger.info("Default admin account created")

def add_admin(username, password, full_name):
    """Add an admin to the data store"""
    admin_id = len(admins) + 1
    admins[username] = {
        'id': admin_id,
        'username': username,
        'password_hash': generate_password_hash(password),
        'full_name': full_name
    }
    return admins[username]

def get_admin(username):
    """Get admin by username"""
    return admins.get(username)

def add_student(student_id, name, password_hash, class_name, face_encoding):
    """Add a student to the data store"""
    if student_id in students:
        return None
    
    students[student_id] = {
        'id': student_id,
        'name': name,
        'password_hash': password_hash,
        'class_name': class_name,
        'face_encoding': face_encoding,
        'created_at': datetime.now().isoformat()
    }
    return students[student_id]

def get_student(student_id):
    """Get student by student ID"""
    return students.get(student_id)

def get_students():
    """Get all students"""
    return list(students.values())

def mark_attendance(student_id):
    """Mark attendance for a student"""
    now = datetime.now()
    
    # Check if student has already been marked for today
    today = now.date().isoformat()
    for record in attendance_records:
        if record['student_id'] == student_id and record['date'] == today:
            record['time'] = now.strftime('%H:%M:%S')
            return record
    
    # Create new attendance record
    attendance_record = {
        'id': len(attendance_records) + 1,
        'student_id': student_id,
        'student_name': students[student_id]['name'],
        'class_name': students[student_id]['class_name'],
        'date': today,
        'time': now.strftime('%H:%M:%S')
    }
    
    attendance_records.append(attendance_record)
    return attendance_record

def get_attendance_records():
    """Get all attendance records"""
    return attendance_records

def get_student_attendance(student_id):
    """Get attendance records for a specific student"""
    return [record for record in attendance_records if record['student_id'] == student_id]
