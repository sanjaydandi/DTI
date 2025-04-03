import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)

# Initialize face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def encode_face(image):
    """
    Encodes a face from an image using a simplified method (face detection + image data).
    
    Args:
        image: Image as numpy array
        
    Returns:
        face_encoding: Simple representation of face (cropped face image flattened)
    """
    try:
        # Convert to grayscale for face detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            logger.warning("No faces found in the image")
            return None
        
        # Get the first face
        x, y, w, h = faces[0]
        
        # Crop the face
        face = gray[y:y+h, x:x+w]
        
        # Resize to standard size
        face_resized = cv2.resize(face, (100, 100))
        
        # Flatten the face image to create a simple "encoding"
        encoding = face_resized.flatten()
        
        # Normalize values
        encoding = encoding / 255.0
        
        # Return as list for JSON serialization
        return encoding.tolist()
    
    except Exception as e:
        logger.error(f"Error encoding face: {str(e)}")
        return None

def compare_faces(known_face_encoding, face_encoding_to_check, tolerance=0.6):
    """
    Compares a known face encoding with another face encoding to see if they match
    using a simplified method (Euclidean distance).
    
    Args:
        known_face_encoding: Known face encoding
        face_encoding_to_check: Face encoding to check
        tolerance: Tolerance for face comparison (higher is stricter)
        
    Returns:
        boolean: True if faces match, False otherwise
    """
    try:
        # Convert to numpy arrays if not already
        if isinstance(known_face_encoding, list):
            known_face_encoding = np.array(known_face_encoding)
        
        if isinstance(face_encoding_to_check, list):
            face_encoding_to_check = np.array(face_encoding_to_check)
        
        # Calculate Euclidean distance between the encodings
        distance = np.linalg.norm(known_face_encoding - face_encoding_to_check)
        
        # If distance is below threshold, consider it a match
        # Note: Lower distances mean more similar faces
        threshold = 30.0  # This value may need tuning
        
        logger.debug(f"Face comparison distance: {distance}, threshold: {threshold}")
        
        return distance < threshold
    
    except Exception as e:
        logger.error(f"Error comparing faces: {str(e)}")
        return False
def is_valid_attendance_time():
    """Check if current time is within allowed windows"""
    from datetime import datetime, time
    current_time = datetime.now().time()
    
    morning_start = time(8, 30)
    morning_end = time(9, 20)
    afternoon_start = time(13, 0)  # 1:00 PM
    afternoon_end = time(14, 0)    # 2:00 PM
    
    return ((morning_start <= current_time <= morning_end) or 
            (afternoon_start <= current_time <= afternoon_end))

def is_valid_location(latitude, longitude):
    """Check if location is within allowed radius of campus"""
    # Example coordinates - replace with actual campus coordinates
    CAMPUS_LAT = 15.492489908291073  
    CAMPUS_LONG = 80.0378496294504
    ALLOWED_RADIUS = 0.5  # kilometers
    
    from math import sin, cos, sqrt, atan2, radians
    R = 6371  # Earth's radius in km
    
    lat1, lon1 = radians(CAMPUS_LAT), radians(CAMPUS_LONG)
    lat2, lon2 = radians(float(latitude)), radians(float(longitude))
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return distance <= ALLOWED_RADIUS

 #  home 15.492489908291073, 80.0378496294504