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
from functools import wraps  # Add this import for the decorator
from werkzeug.security import generate_password_hash, check_password_hash

from face_utils import encode_face, compare_faces
from models import db, init_db, Admin, Student, Attendance, StudentRegistrationRequest, RequestStatus

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Define admin_required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Please login as admin first!', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Configure database
db_url = os.environ.get('DATABASE_URL')
if db_url:
    # If using external PostgreSQL, ensure URL starts with postgresql://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    # For PythonAnywhere MySQL
    username = 'your_pythonanywhere_username'
    mysql_username = username
    mysql_password = 'your_database_password'
    mysql_hostname = username + '.mysql.pythonanywhere-services.com'
    mysql_database = username + '$default'
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://{mysql_username}:{mysql_password}@{mysql_hostname}/{mysql_database}'
    # Fallback to SQLite if no DATABASE_URL is provided
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300
}

# Initialize database and recreate all tables
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    # Check if we should preserve the database
    preserve_db = os.environ.get('PRESERVE_DB', 'False').lower() == 'true'
    
    if not preserve_db:
        db.drop_all()  # This will drop all existing tables
        
    db.create_all()  # This will create all tables with updated schema
    
    # Create default admin only if it doesn't exist
    if Admin.query.count() == 0:
        default_admin = Admin(username='admin', full_name='System Administrator')
        default_admin.set_password('admin')
        db.session.add(default_admin)
        db.session.commit()

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

        logger.debug(f"Login attempt for student ID: {student_id}")
        student = Student.query.get(student_id)

        if student and student.check_password(password):
            logger.debug("Student found and password check successful")
            session['student_id'] = student.id
            session['name'] = student.name
            session['is_admin'] = False
            flash('Login successful!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            if not student:
                logger.debug(f"No student found with ID: {student_id}")
            else:
                logger.debug("Password check failed")
            flash('Invalid student ID or password', 'danger')
            return redirect(url_for('student_login'))

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

    # Get pending registration requests count
    pending_count = StudentRegistrationRequest.query.filter_by(
        status=RequestStatus.PENDING.value
    ).count()
    
    # Debug the chart data
    logger.debug(f"Chart dates: {dates}")
    logger.debug(f"Chart counts: {counts}")
    logger.debug(f"Pending registration requests: {pending_count}")

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
                          pending_count=pending_count,
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
                face_encoding=face_encoding_str,
                profile_image=face_image_data  # Save the captured image
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

            # Get the currently logged in student's face encoding
            stored_encoding = json.loads(student.face_encoding)
            stored_encoding_np = np.array(stored_encoding)

            # Handle both numpy arrays and lists for face_encoding
            if hasattr(face_encoding, 'tolist'):
                face_encoding_to_compare = face_encoding
            else:
                face_encoding_to_compare = np.array(face_encoding)  # Convert list to numpy array

            # Compare with stored face encoding - Make sure it matches the logged-in student
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
                    # Create new attendance record for the logged-in student only
                    new_attendance = Attendance(
                        student_id=student_id,  # Use the student_id from the session
                        date=today,
                        time=datetime.now().time()
                    )
                    db.session.add(new_attendance)
                    db.session.commit()
                    flash('Attendance marked successfully!', 'success')

                return redirect(url_for('student_dashboard'))
            else:
                flash('Face verification failed. The face does not match your registered face. Please try again.', 'danger')
                logger.warning(f"Face verification failed for student {student_id}")

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
@app.route('/admin/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        student.name = request.form['name']
        student.class_name = request.form['class_name']
        student.email = request.form['email']
        
        # Update password if provided
        if request.form['password'] and request.form['password'].strip():
            student.set_password(request.form['password'])
        
        # Handle profile image update if provided
        if 'profile_image' in request.files and request.files['profile_image'].filename:
            file = request.files['profile_image']
            # Process and save the image
            # This depends on how you're handling image storage
            
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('student_profiles'))
    
    return render_template('edit_student.html', student=student)

@app.route('/admin/delete_student/<student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    
    # Delete related attendance records first
    Attendance.query.filter_by(student_id=student_id).delete()
    
    # Delete the student
    db.session.delete(student)
    db.session.commit()
    
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('student_profiles'))

# Student Registration Route
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        try:
            # Get form data
            student_id = request.form.get('student_id')
            name = request.form.get('name')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            class_name = request.form.get('class_name')
            email = request.form.get('email')
            agree_terms = request.form.get('agree_terms')
            
            # Validate required fields
            if not (student_id and name and password and confirm_password and class_name and agree_terms):
                flash('Please fill all required fields', 'danger')
                return render_template('student_register.html')
            
            # Check if passwords match
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return render_template('student_register.html')
                
            # Check if student ID already exists in students table
            existing_student = Student.query.get(student_id)
            if existing_student:
                flash('A student with this ID already exists', 'danger')
                return render_template('student_register.html')
                
            # Check if there's already a pending request with this ID
            existing_request = StudentRegistrationRequest.query.filter_by(
                student_id=student_id
            ).first()
            
            if existing_request:
                if existing_request.status == RequestStatus.PENDING.value:
                    flash('A registration request with this ID is already pending approval', 'warning')
                elif existing_request.status == RequestStatus.REJECTED.value:
                    flash('Your previous registration request was rejected. Please contact an administrator.', 'warning')
                else:
                    flash('You are already registered. Please login.', 'info')
                return render_template('student_register.html')
            
            # Process face image captured from webcam
            profile_image_data = None
            face_encoding_str = None
            face_image_data = request.form.get('face_image')
            
            if face_image_data:
                try:
                    # Process the base64 image data
                    if ',' in face_image_data:
                        face_image_data = face_image_data.split(',')[1]
                    
                    # Store the base64 data for the profile image
                    profile_image_data = face_image_data
                    
                    # Decode base64 for face encoding
                    face_image_binary = base64.b64decode(face_image_data)
                    image = Image.open(io.BytesIO(face_image_binary))
                    image_np = np.array(image)
                    
                    # Convert RGB to BGR for OpenCV if color image
                    if len(image_np.shape) == 3:  # Color image
                        image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
                    
                    # Encode the face
                    face_encoding = encode_face(image_np)
                    
                    if face_encoding is None:
                        flash('No face detected in the captured image. Please try again with a clearer face position.', 'danger')
                        return render_template('student_register.html')
                    
                    # Convert face encoding to JSON for storage
                    if hasattr(face_encoding, 'tolist'):
                        face_encoding_list = face_encoding.tolist()
                    else:
                        face_encoding_list = face_encoding
                    
                    face_encoding_str = json.dumps(face_encoding_list)
                except Exception as e:
                    logger.error(f"Error processing captured face image: {str(e)}")
                    flash('Error processing the captured image. Please try again.', 'danger')
                    return render_template('student_register.html')
            else:
                # No face image provided
                flash('Please capture your face using the camera before registering.', 'danger')
                return render_template('student_register.html')
            
            # Create the registration request
            new_request = StudentRegistrationRequest(
                student_id=student_id,
                name=name,
                class_name=class_name,
                email=email,
                profile_image=profile_image_data,
                face_encoding=face_encoding_str,
                status=RequestStatus.PENDING.value
            )
            new_request.set_password(password)
            
            # Save to database
            db.session.add(new_request)
            db.session.commit()
            
            flash('Your registration request has been submitted. An administrator will review it shortly.', 'success')
            return redirect(url_for('student_login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in student registration: {str(e)}")
            flash(f'Error in registration: {str(e)}', 'danger')
    
    return render_template('student_register.html')

# Admin Manage Registration Requests Route
@app.route('/admin/manage_requests')
def manage_requests():
    if not session.get('is_admin'):
        flash('Please login as admin first!', 'warning')
        return redirect(url_for('admin_login'))
    
    # Fetch requests by status
    pending_requests = StudentRegistrationRequest.query.filter_by(
        status=RequestStatus.PENDING.value
    ).order_by(StudentRegistrationRequest.created_at.desc()).all()
    
    approved_requests = StudentRegistrationRequest.query.filter_by(
        status=RequestStatus.APPROVED.value
    ).order_by(StudentRegistrationRequest.updated_at.desc()).all()
    
    rejected_requests = StudentRegistrationRequest.query.filter_by(
        status=RequestStatus.REJECTED.value
    ).order_by(StudentRegistrationRequest.updated_at.desc()).all()
    
    # Count of requests by status
    pending_count = len(pending_requests)
    approved_count = len(approved_requests)
    rejected_count = len(rejected_requests)
    
    return render_template('manage_requests.html',
                          pending_requests=pending_requests,
                          approved_requests=approved_requests,
                          rejected_requests=rejected_requests,
                          pending_count=pending_count,
                          approved_count=approved_count,
                          rejected_count=rejected_count)

# Admin Approve/Reject Registration Routes
@app.route('/admin/manage_requests/approve', methods=['POST'])
def approve_request():
    if not session.get('is_admin'):
        return {'success': False, 'message': 'Unauthorized'}, 401
    
    try:
        data = request.json
        request_id = data.get('request_id')
        admin_notes = data.get('admin_notes', '')
        
        if not request_id:
            return {'success': False, 'message': 'Missing request ID'}, 400
        
        # Find the request
        reg_request = StudentRegistrationRequest.query.get(request_id)
        if not reg_request:
            return {'success': False, 'message': 'Request not found'}, 404
        
        # Check if already processed
        if reg_request.status != RequestStatus.PENDING.value:
            return {
                'success': False, 
                'message': f'Request already {reg_request.status}'
            }, 400
        
        # Create a new student from the request
        new_student = Student(
            id=reg_request.student_id,
            name=reg_request.name,
            password_hash=reg_request.password_hash,  # Use the same password hash
            class_name=reg_request.class_name,
            email=reg_request.email,
            face_encoding=reg_request.face_encoding,
            profile_image=reg_request.profile_image
        )
        
        # Update request status
        reg_request.status = RequestStatus.APPROVED.value
        reg_request.admin_notes = admin_notes
        reg_request.updated_at = datetime.utcnow()
        
        # Save to database
        db.session.add(new_student)
        db.session.commit()
        
        return {'success': True, 'message': 'Request approved successfully'}
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving request: {str(e)}")
        return {'success': False, 'message': f'Error: {str(e)}'}, 500

@app.route('/admin/manage_requests/reject', methods=['POST'])
def reject_request():
    if not session.get('is_admin'):
        return {'success': False, 'message': 'Unauthorized'}, 401
    
    try:
        data = request.json
        request_id = data.get('request_id')
        admin_notes = data.get('admin_notes', '')
        
        if not request_id:
            return {'success': False, 'message': 'Missing request ID'}, 400
        
        # Find the request
        reg_request = StudentRegistrationRequest.query.get(request_id)
        if not reg_request:
            return {'success': False, 'message': 'Request not found'}, 404
        
        # Check if already processed
        if reg_request.status != RequestStatus.PENDING.value:
            return {
                'success': False, 
                'message': f'Request already {reg_request.status}'
            }, 400
        
        # Update request status
        reg_request.status = RequestStatus.REJECTED.value
        reg_request.admin_notes = admin_notes
        reg_request.updated_at = datetime.utcnow()
        
        # Save to database
        db.session.commit()
        
        return {'success': True, 'message': 'Request rejected successfully'}
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting request: {str(e)}")
        return {'success': False, 'message': f'Error: {str(e)}'}, 500

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/admin/student_profiles')
@admin_required
def student_profiles():
    # Get all students from the database
    students = Student.query.all()
    
    # Get search and filter parameters
    search = request.args.get('search', '')
    class_filter = request.args.get('class', '')
    sort_by = request.args.get('sort', 'name')
    
    # Apply search filter if provided
    if search:
        students = [s for s in students if search.lower() in s.name.lower() or search.lower() in s.id.lower()]
    
    # Apply class filter if provided
    if class_filter:
        students = [s for s in students if s.class_name == class_filter]
    
    # Get list of unique class names for the filter dropdown
    class_list = sorted(list(set(s.class_name for s in Student.query.all() if s.class_name)))
    
    # Calculate attendance percentage for each student
    for student in students:
        total_days = Attendance.query.filter_by(student_id=student.id).count()
        if total_days > 0:
            present_days = Attendance.query.filter_by(student_id=student.id, status='present').count()
            student.attendance_percentage = (present_days / total_days) * 100
        else:
            student.attendance_percentage = 0
        
        # Get latest attendance record
        student.latest_attendance = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).first()
    
    # Sort students based on selected criteria
    if sort_by == 'name':
        students.sort(key=lambda x: x.name)
    elif sort_by == 'id':
        students.sort(key=lambda x: x.id)
    elif sort_by == 'attendance':
        students.sort(key=lambda x: x.attendance_percentage, reverse=True)
    
    return render_template('student_profiles.html', 
                          students=students, 
                          class_list=class_list,
                          request=request)

@app.route('/admin/student_profile/<student_id>')
@admin_required
def student_profile_detail(student_id):
    student = Student.query.get_or_404(student_id)
    
    # Get attendance records for this student
    attendance_records = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc()).all()
    
    # Calculate attendance statistics
    total_days = len(attendance_records)
    if total_days > 0:
        attendance_percentage = (total_days / total_days) * 100
    else:
        attendance_percentage = 0
    
    # Get dates for attendance chart
    dates = [record.date.strftime('%Y-%m-%d') for record in attendance_records]
    
    return render_template('student_profile_detail.html',
                          student=student,
                          attendance_records=attendance_records,
                          attendance_percentage=attendance_percentage,
                          dates=dates)