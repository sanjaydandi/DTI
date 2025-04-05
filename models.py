import os
from datetime import datetime
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name
        }

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.String(20), primary_key=True)  # Student ID (used as primary key)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    face_encoding = db.Column(db.Text, nullable=True)  # Store as JSON string
    profile_image = db.Column(db.Text, nullable=True)  # Store base64 image
    email = db.Column(db.String(100), nullable=True)  # Optional email for contact
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    attendances = db.relationship('Attendance', backref='student', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'class_name': self.class_name,
            'email': self.email,
            'face_encoding': self.face_encoding is not None,
            'profile_image': self.profile_image,  # Return the actual base64 image data
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class RequestStatus(Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class StudentRegistrationRequest(db.Model):
    __tablename__ = 'student_registration_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    profile_image = db.Column(db.Text, nullable=True)  # Store base64 image
    face_encoding = db.Column(db.Text, nullable=True)  # Store as JSON string
    status = db.Column(db.String(20), default=RequestStatus.PENDING.value, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    admin_notes = db.Column(db.Text, nullable=True)  # Notes added by admin when approving/rejecting
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'name': self.name,
            'class_name': self.class_name,
            'email': self.email,
            'face_encoding': self.face_encoding is not None,
            'profile_image': self.profile_image,  # Return the actual base64 image data
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Attendance(db.Model):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    time = db.Column(db.Time, nullable=False, default=datetime.utcnow().time)
    status = db.Column(db.String(20), nullable=False, default='present')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else None,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'time': self.time.strftime('%H:%M:%S') if self.time else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

# Initialize the database with a default admin user
def init_db(app):
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # Check if there's at least one admin user
        if Admin.query.count() == 0:
            # Create a default admin with username 'admin' and password 'admin'
            default_admin = Admin(
                username='admin',
                full_name='System Administrator'
            )
            default_admin.set_password('admin')
            db.session.add(default_admin)
            db.session.commit()
            print("Default admin account created with username: admin, password: admin")