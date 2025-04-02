import os
import logging
import base64
import io
import json
import numpy as np
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash
import cv2
from PIL import Image

from face_utils import encode_face, compare_faces
from models import db, init_db, Admin, Student, Attendance

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure database
db_url = os.environ.get('DATABASE_URL')
if db_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    # Fallback to SQLite if no DATABASE_URL is provided
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {'connect_timeout': 15}
}

# Initialize database
init_db(app)

# Route for home page
@app.route('/')
def index():
    return render_template('index.html')

# Admin login routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # For debugging
        logger.debug(f"Login attempt for admin: {username}")
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['username'] = admin.username
            session['is_admin'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            # For debugging admin authentication issues
            if admin:
                logger.debug(f"Admin found but password check failed for: {username}")
            else:
                logger.debug(f"Admin not found: {username}")
            flash('Invalid username or password', 'danger')
    
    return render_template('admin_login.html')

# Student login routes
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        
        student = Student.query.get(student_id)
        
        if student and student.check_password(password):
            session['student_id'] = student.id
            session['name'] = student.name
            session['is_admin'] = False
            flash('Login successful!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid student ID or password', 'danger')
    
    return render_template('student_login.html')

# Admin dashboard route
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        flash('Please login as admin first!', 'warning')
        return redirect(url_for('admin_login'))
    
    # Get all students and attendance records from database
    students = Student.query.all()
    attendance_records = Attendance.query.all()
    
    # Calculate attendance statistics
    today = date.today()
    students_present_today = Attendance.query.filter(
        Attendance.date == today
    ).count()
    
    total_students = len(students)
    attendance_percentage = 0
    if total_students > 0:
        attendance_percentage = (students_present_today / total_students) * 100
    
    # Group attendance by date for chart
    attendance_by_date = {}
    for record in attendance_records:
        # Check if date attribute is a date object
        if hasattr(record, 'date'):
            # Convert date to string consistently using strftime
            if isinstance(record.date, str):
                date_str = record.date
            else:
                try:
                    date_str = record.date.strftime('%Y-%m-%d')
                except:
                    continue  # Skip this record if date is invalid
                
            if date_str in attendance_by_date:
                attendance_by_date[date_str] += 1
            else:
                attendance_by_date[date_str] = 1
    
    # Sort dates for chart
    dates = sorted(attendance_by_date.keys()) if attendance_by_date else []
    counts = [attendance_by_date[d] for d in dates] if dates else []
    
    # Debug the chart data
    logger.debug(f"Chart dates: {dates}")
    logger.debug(f"Chart counts: {counts}")
    
    # Convert student objects to dictionaries for template
    students_data = [student.to_dict() for student in students]
    attendance_data = [record.to_dict() for record in attendance_records]
    
    return render_template('admin_dashboard.html', 
                          students=students_data,
                          attendance_records=attendance_data,
                          dates=dates,
                          counts=counts,
                          students_present_today=students_present_today,
                          total_students=total_students,
                          attendance_percentage=attendance_percentage,
                          date=date)

# Add student route
@app.route('/admin/add_student', methods=['GET', 'POST'])
def add_student_route():
    if not session.get('is_admin'):
        flash('Please login as admin first!', 'warning')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            student_id = request.form.get('student_id')
            password = request.form.get('password')
            class_name = request.form.get('class_name')
            
            # Get face image from the form
            face_image_data = request.form.get('face_image')
            
            if not (name and student_id and password and class_name and face_image_data):
                flash('All fields are required', 'danger')
                return redirect(url_for('add_student_route'))
            
            # Process the base64 image data
            face_image_data = face_image_data.split(',')[1]
            face_image_binary = base64.b64decode(face_image_data)
            face_image = Image.open(io.BytesIO(face_image_binary))
            
            # Convert PIL Image to numpy array for face_recognition
            face_image_np = np.array(face_image)
            
            # Convert RGB to BGR for OpenCV
            if len(face_image_np.shape) == 3:  # Color image
                face_image_np = cv2.cvtColor(face_image_np, cv2.COLOR_RGB2BGR)
            
            # Encode the face
            face_encoding = encode_face(face_image_np)
            
            if face_encoding is None:
                flash('No face detected in the image. Please try again.', 'danger')
                return redirect(url_for('add_student_route'))
            
            # Check if student_id already exists
            existing_student = Student.query.get(student_id)
            if existing_student:
                flash('Student ID already exists', 'danger')
                return redirect(url_for('add_student_route'))
                
            # Convert face encoding to a JSON string for storage
            # Handle both numpy arrays and lists
            if hasattr(face_encoding, 'tolist'):
                face_encoding_list = face_encoding.tolist()
            else:
                face_encoding_list = face_encoding  # Already a list
                
            face_encoding_str = json.dumps(face_encoding_list)
            
            # Create a new student record
            new_student = Student(
                id=student_id,
                name=name,
                class_name=class_name,
                face_encoding=face_encoding_str
            )
            new_student.set_password(password)
            
            # Add to database
            db.session.add(new_student)
            db.session.commit()
            
            flash(f'Student {name} added successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding student: {str(e)}")
            flash(f'Error adding student: {str(e)}', 'danger')
    
    return render_template('add_student.html')

# Student dashboard route
@app.route('/student/dashboard')
def student_dashboard():
    if not session.get('student_id'):
        flash('Please login first!', 'warning')
        return redirect(url_for('student_login'))
    
    student_id = session.get('student_id')
    student = Student.query.get(student_id)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('student_login'))
    
    # Get attendance records for this student
    attendance_records = Attendance.query.filter_by(student_id=student_id).all()
    attendance_data = [record.to_dict() for record in attendance_records]
    
    # Import datetime and date to use in the template
    from datetime import datetime as dt, date
    
    return render_template('student_dashboard.html', 
                          student=student.to_dict(), 
                          attendance=attendance_data,
                          datetime=dt,
                          date=date)

# Mark attendance route
@app.route('/student/attendance', methods=['GET', 'POST'])
def attendance():
    if not session.get('student_id'):
        flash('Please login first!', 'warning')
        return redirect(url_for('student_login'))
    
    student_id = session.get('student_id')
    student = Student.query.get(student_id)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('student_login'))
    
    if request.method == 'POST':
        try:
            # Get face image from the form
            face_image_data = request.form.get('face_image')
            
            if not face_image_data:
                flash('No image provided', 'danger')
                return redirect(url_for('attendance'))
            
            # Process the base64 image data
            face_image_data = face_image_data.split(',')[1]
            face_image_binary = base64.b64decode(face_image_data)
            face_image = Image.open(io.BytesIO(face_image_binary))
            
            # Convert PIL Image to numpy array for face_recognition
            face_image_np = np.array(face_image)
            
            # Convert RGB to BGR for OpenCV
            if len(face_image_np.shape) == 3:  # Color image
                face_image_np = cv2.cvtColor(face_image_np, cv2.COLOR_RGB2BGR)
            
            # Encode the face
            face_encoding = encode_face(face_image_np)
            
            if face_encoding is None:
                flash('No face detected in the image. Please try again.', 'danger')
                return redirect(url_for('attendance'))
            
            # Compare with stored face encoding
            stored_encoding = json.loads(student.face_encoding)
            stored_encoding_np = np.array(stored_encoding)
            
            # Handle both numpy arrays and lists for face_encoding
            if hasattr(face_encoding, 'tolist'):
                face_encoding_to_compare = face_encoding
            else:
                face_encoding_to_compare = np.array(face_encoding)  # Convert list to numpy array
                
            match = compare_faces(stored_encoding_np, face_encoding_to_compare)
            
            if match:
                # Check if attendance already marked for today
                today = date.today()
                existing_attendance = Attendance.query.filter_by(
                    student_id=student_id,
                    date=today
                ).first()
                
                if existing_attendance:
                    flash('Attendance already marked for today', 'info')
                else:
                    # Create new attendance record
                    new_attendance = Attendance(
                        student_id=student_id,
                        date=today,
                        time=datetime.now().time()
                    )
                    db.session.add(new_attendance)
                    db.session.commit()
                    flash('Attendance marked successfully!', 'success')
                
                return redirect(url_for('student_dashboard'))
            else:
                flash('Face verification failed. Please try again.', 'danger')
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking attendance: {str(e)}")
            flash(f'Error marking attendance: {str(e)}', 'danger')
    
    return render_template('attendance.html', student=student.to_dict())

# Admin manage attendance route
@app.route('/admin/manage_attendance', methods=['GET', 'POST'])
def manage_attendance():
    if not session.get('is_admin'):
        flash('Please login as admin first!', 'warning')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            student_id = request.form.get('student_id')
            attendance_date = request.form.get('date')
            
            if not (action and student_id and attendance_date):
                flash('Missing required parameters', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            # Convert string date to date object
            try:
                attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            # Check if student exists
            student = Student.query.get(student_id)
            if not student:
                flash('Student not found', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            if action == 'mark_present':
                # Check if attendance already exists for this date
                existing = Attendance.query.filter_by(
                    student_id=student_id,
                    date=attendance_date
                ).first()
                
                if not existing:
                    # Create new attendance record
                    new_attendance = Attendance(
                        student_id=student_id,
                        date=attendance_date,
                        time=datetime.now().time()
                    )
                    db.session.add(new_attendance)
                    db.session.commit()
                    flash(f'Marked {student.name} present on {attendance_date}', 'success')
                else:
                    flash(f'Attendance already marked for {student.name} on {attendance_date}', 'info')
                    
            elif action == 'mark_absent':
                # Find and delete attendance record
                existing = Attendance.query.filter_by(
                    student_id=student_id,
                    date=attendance_date
                ).first()
                
                if existing:
                    db.session.delete(existing)
                    db.session.commit()
                    flash(f'Marked {student.name} absent on {attendance_date}', 'success')
                else:
                    flash(f'No attendance record found for {student.name} on {attendance_date}', 'info')
            
            return redirect(url_for('admin_dashboard'))
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error managing attendance: {str(e)}")
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('admin_dashboard'))
    
    # For GET request, show all students and dates for selection
    students = Student.query.all()
    attendance_records = Attendance.query.all()
    
    return render_template('manage_attendance.html',
                          students=[s.to_dict() for s in students],
                          attendance_records=[a.to_dict() for a in attendance_records],
                          today=date.today().strftime('%Y-%m-%d'))

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))
