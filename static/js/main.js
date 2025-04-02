/**
 * Main JavaScript for the application
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize webcam on attendance page
    initializeWebcam();
    
    // Initialize charts on admin dashboard
    initializeCharts();
    
    // Set up validation for forms
    setupFormValidation();
});

function initializeWebcam() {
    const videoElement = document.getElementById('webcam-video');
    const canvasElement = document.getElementById('webcam-canvas');
    
    if (videoElement && canvasElement) {
        // Check if we're on the attendance or add student page
        const isAttendancePage = document.getElementById('mark-attendance-form') !== null;
        const isAddStudentPage = document.getElementById('add-student-form') !== null;
        
        if (isAttendancePage || isAddStudentPage) {
            const captureButtonId = isAttendancePage ? 'capture-btn' : 'capture-face-btn';
            const retakeButtonId = isAttendancePage ? 'retake-btn' : 'retake-face-btn';
            const saveButtonId = isAttendancePage ? 'submit-attendance-btn' : 'submit-student-btn';
            const imageInputId = isAttendancePage ? 'face-image' : 'face-image';
            
            const webcam = new WebcamCapture(
                videoElement,
                canvasElement,
                captureButtonId,
                retakeButtonId,
                saveButtonId,
                imageInputId
            );
            
            webcam.start().then(success => {
                if (!success) {
                    console.error('Failed to start webcam');
                }
            });
            
            // Set up form submission validation
            const form = document.getElementById(isAttendancePage ? 'mark-attendance-form' : 'add-student-form');
            if (form) {
                form.addEventListener('submit', function(event) {
                    if (!webcam.isCaptured()) {
                        event.preventDefault();
                        alert('Please capture your face image first.');
                    }
                });
            }
        }
    }
}

function initializeCharts() {
    // Check if we're on the admin dashboard
    const attendanceChartElement = document.getElementById('attendance-chart');
    const distributionChartElement = document.getElementById('attendance-distribution-chart');
    
    if (attendanceChartElement) {
        // Get chart data from data attributes
        const dates = JSON.parse(attendanceChartElement.getAttribute('data-dates') || '[]');
        const counts = JSON.parse(attendanceChartElement.getAttribute('data-counts') || '[]');
        
        // Initialize attendance chart
        initAttendanceChart('attendance-chart', dates, counts);
    }
    
    if (distributionChartElement) {
        // Get chart data from data attributes
        const presentCount = parseInt(distributionChartElement.getAttribute('data-present') || '0');
        const absentCount = parseInt(distributionChartElement.getAttribute('data-absent') || '0');
        
        // Initialize distribution chart
        initAttendanceDistributionChart('attendance-distribution-chart', presentCount, absentCount);
    }
}

function setupFormValidation() {
    // Add client-side validation for forms
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        }, false);
    });
}
