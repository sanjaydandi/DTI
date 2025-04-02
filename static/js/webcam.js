/**
 * Webcam handling utility for face capture
 */
class WebcamCapture {
    constructor(videoElement, canvasElement, captureButtonId, retakeButtonId, saveButtonId, imageInputId) {
        this.video = videoElement;
        this.canvas = canvasElement;
        this.captureButton = document.getElementById(captureButtonId);
        this.retakeButton = document.getElementById(retakeButtonId);
        this.saveButton = document.getElementById(saveButtonId);
        this.imageInput = document.getElementById(imageInputId);
        
        this.stream = null;
        this.captured = false;
        
        this.initializeElements();
    }
    
    initializeElements() {
        // Set up canvas
        this.context = this.canvas.getContext('2d');
        
        // Register button events
        if (this.captureButton) {
            this.captureButton.addEventListener('click', () => this.capture());
        }
        
        if (this.retakeButton) {
            this.retakeButton.addEventListener('click', () => this.retake());
        }
        
        // Initial button states
        if (this.retakeButton) this.retakeButton.style.display = 'none';
        if (this.saveButton) this.saveButton.style.display = 'none';
    }
    
    async start() {
        try {
            // Request access to webcam
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { 
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: false
            });
            
            // Connect stream to video element
            this.video.srcObject = this.stream;
            this.video.style.display = 'block';
            this.canvas.style.display = 'none';
            
            // Enable capture button
            if (this.captureButton) this.captureButton.disabled = false;
            
            return true;
        } catch (error) {
            console.error('Error accessing webcam:', error);
            alert('Error accessing webcam. Please ensure your camera is connected and you have granted permission to use it.');
            return false;
        }
    }
    
    capture() {
        // Draw current video frame to canvas
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        this.context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Update UI
        this.video.style.display = 'none';
        this.canvas.style.display = 'block';
        if (this.captureButton) this.captureButton.style.display = 'none';
        if (this.retakeButton) this.retakeButton.style.display = 'inline-block';
        if (this.saveButton) this.saveButton.style.display = 'inline-block';
        
        // Store image data in hidden input
        const imageData = this.canvas.toDataURL('image/jpeg');
        if (this.imageInput) this.imageInput.value = imageData;
        
        this.captured = true;
    }
    
    retake() {
        // Reset UI
        this.video.style.display = 'block';
        this.canvas.style.display = 'none';
        if (this.captureButton) this.captureButton.style.display = 'inline-block';
        if (this.retakeButton) this.retakeButton.style.display = 'none';
        if (this.saveButton) this.saveButton.style.display = 'none';
        
        // Clear image data
        if (this.imageInput) this.imageInput.value = '';
        
        this.captured = false;
    }
    
    stop() {
        // Stop all video streams
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
    
    isCaptured() {
        return this.captured;
    }
}
