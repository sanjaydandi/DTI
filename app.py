import os
import logging
import base64
import io
import numpy as np
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
from PIL import Image

from face_utils import encode_face, compare_faces
from data_store import (
    get_admin, get_student, add_student, mark_attendance, 
    get_students, get_attendance_records, get_student_attendance,
    initialize_data
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize data store with default admin
initialize_data()

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
        
        admin = get_admin(username)
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['username'] = admin['username']
            session['is_admin'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('admin_login.html')

# Student login routes
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        
        student = get_student(student_id)
        
        if student and check_password_hash(student['password_hash'], password):
            session['student_id'] = student['id']
            session['name'] = student['name']
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
    
    # Get all students and attendance records
    students = get_students()
    attendance_records = get_attendance_records()
    
    # Calculate attendance statistics
    today = date.today().isoformat()
    students_present_today = len([record for record in attendance_records 
                               if record['date'] == today])
    
    total_students = len(students)
    attendance_percentage = 0
    if total_students > 0:
        attendance_percentage = (students_present_today / total_students) * 100
    
    # Group attendance by date for chart
    attendance_by_date = {}
    for record in attendance_records:
        if record['date'] in attendance_by_date:
            attendance_by_date[record['date']] += 1
        else:
            attendance_by_date[record['date']] = 1
    
    # Sort dates for chart
    dates = sorted(attendance_by_date.keys())
    counts = [attendance_by_date[d] for d in dates]
    
    return render_template('admin_dashboard.html', 
                          students=students,
                          attendance_records=attendance_records,
                          dates=dates,
                          counts=counts,
                          students_present_today=students_present_today,
                          total_students=total_students,
                          attendance_percentage=attendance_percentage)

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
            
            # Hash the password
            password_hash = generate_password_hash(password)
            
            # Add student to the data store
            student = add_student(student_id, name, password_hash, class_name, face_encoding)
            
            if student:
                flash(f'Student {name} added successfully!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Student ID already exists', 'danger')
                
        except Exception as e:
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
    student = get_student(student_id)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('student_login'))
    
    # Get attendance records for this student
    attendance = get_student_attendance(student_id)
    
    return render_template('student_dashboard.html', 
                          student=student, 
                          attendance=attendance)

# Mark attendance route
@app.route('/student/attendance', methods=['GET', 'POST'])
def attendance():
    if not session.get('student_id'):
        flash('Please login first!', 'warning')
        return redirect(url_for('student_login'))
    
    student_id = session.get('student_id')
    student = get_student(student_id)
    
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
            stored_encoding = np.array(student['face_encoding'])
            match = compare_faces(stored_encoding, face_encoding)
            
            if match:
                # Mark attendance
                mark_attendance(student_id)
                flash('Attendance marked successfully!', 'success')
                return redirect(url_for('student_dashboard'))
            else:
                flash('Face verification failed. Please try again.', 'danger')
                
        except Exception as e:
            logger.error(f"Error marking attendance: {str(e)}")
            flash(f'Error marking attendance: {str(e)}', 'danger')
    
    return render_template('attendance.html', student=student)

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))
