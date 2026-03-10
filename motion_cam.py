import cv2
import numpy as np
import time
import os
import winsound
import threading
from datetime import datetime
import math

# Configuration
class Config:
    RESOLUTION = (640, 480)
    FPS_LIMIT = 15
    BLUR_SIZE = (15, 15)
    THRESHOLD = 10  # CHANGED: Lower = more sensitive (was 25)
    MIN_CONTOUR_AREA = 500  # CHANGED: Lower = detect smaller movements (was 1000)
    COOLDOWN = 1.0  # CHANGED: Detect motion faster (was 2.0)
    OVERLAY_DURATION = 5.0
    SAVE_QUALITY = 90
    THEME_COLOR = (41, 128, 185)
    ALERT_COLOR = (231, 76, 60)
    SUCCESS_COLOR = (46, 204, 113)

# Create capture folder
if not os.path.exists("motion_captures"):
    os.makedirs("motion_captures")

# Performance optimizations
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

# Initialize video capture with anti-sleep settings
print("Initializing camera...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

# Set camera properties
cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.RESOLUTION[0])
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.RESOLUTION[1])
cap.set(cv2.CAP_PROP_FPS, Config.FPS_LIMIT)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Increased buffer
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))  # MJPG format

# Warm up camera
for _ in range(5):
    cap.read()
    time.sleep(0.1)

# Read initial frame
ret, frame1 = cap.read()
frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
frame1_gray = cv2.GaussianBlur(frame1_gray, Config.BLUR_SIZE, 0)

# Global variables
motion_history = []
motion_detected = False
last_motion_time = 0
motion_count = 0
fps = 0
frame_count = 0
last_fps_time = time.time()
last_keep_alive = time.time()

def beep_sound():
    """Play alert sound in separate thread"""
    try:
        winsound.Beep(1000, 200)
    except:
        pass

def keep_camera_awake():
    """Prevent camera from going to sleep"""
    global last_keep_alive
    current_time = time.time()
    
    # Do this every 2 seconds
    if current_time - last_keep_alive > 2.0:
        try:
            # Method 1: Toggle a property
            current_brightness = cap.get(cv2.CAP_PROP_BRIGHTNESS)
            cap.set(cv2.CAP_PROP_BRIGHTNESS, current_brightness)
            
            # Method 2: Read a frame (already doing this continuously)
            # Method 3: Reset exposure
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # Some cameras need this
            
            last_keep_alive = current_time
        except Exception as e:
            pass

def save_image_async(image, timestamp):
    """Save image without blocking main thread"""
    def save():
        filename = f"motion_captures/motion_{timestamp}.jpg"
        cv2.imwrite(filename, image, [cv2.IMWRITE_JPEG_QUALITY, Config.SAVE_QUALITY])
    threading.Thread(target=save, daemon=True).start()

# Rest of your UI functions (create_gradient, draw_rounded_rect, create_ui_overlay, update_fps)
# Keep them exactly the same

def update_fps():
    """Calculate FPS"""
    global fps, frame_count, last_fps_time
    current_time = time.time()
    frame_count += 1
    
    if current_time - last_fps_time >= 1.0:
        fps = frame_count / (current_time - last_fps_time)
        frame_count = 0
        last_fps_time = current_time
    return fps

print("🔒 Security Monitor Started")
print("   Press 'q' to quit")
print("   Press '+' to increase sensitivity")
print("   Press '-' to decrease sensitivity")

start_time = time.time()
camera_hung_count = 0

while True:
    # Keep camera awake
    keep_camera_awake()
    
    # Read frame with timeout check
    ret, frame2 = cap.read()
    if not ret:
        print("⚠️ Camera frame dropped, reconnecting...")
        camera_hung_count += 1
        
        # Try to reconnect if camera hangs too much
        if camera_hung_count > 5:
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.RESOLUTION[1])
            cap.set(cv2.CAP_PROP_FPS, Config.FPS_LIMIT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
            camera_hung_count = 0
            continue
        else:
            continue
    else:
        camera_hung_count = 0  # Reset counter on successful read
    
    # Process for motion detection
    gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, Config.BLUR_SIZE, 0)
    
    # Motion detection
    diff = cv2.absdiff(frame1_gray, gray)
    thresh = cv2.threshold(diff, Config.THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    current_motion = False
    motion_intensity = 0
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < Config.MIN_CONTOUR_AREA:
            continue
        
        current_motion = True
        motion_intensity += area
        
        # Draw bounding boxes
        x, y, w, h = cv2.boundingRect(contour)
        cv2.rectangle(frame2, (x-2, y-2), (x+w+2, y+h+2), (255, 255, 255), 1)
        intensity = min(area / 5000, 1.0)
        color = tuple(int(Config.ALERT_COLOR[i] * intensity + 50) for i in range(3))
        cv2.rectangle(frame2, (x, y), (x + w, y + h), color, 2)
        
        # Area label
        label = f"{int(area)}px"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.rectangle(frame2, (x, y - label_size[1] - 4), 
                     (x + label_size[0] + 4, y), color, -1)
        cv2.putText(frame2, label, (x + 2, y - 2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Update motion history
    motion_history.append(motion_intensity)
    if len(motion_history) > 50:
        motion_history.pop(0)
    
    # Check for motion events
    if current_motion and (time.time() - last_motion_time > Config.COOLDOWN):
        last_motion_time = time.time()
        motion_detected = True
        motion_count += 1
        
        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        save_image_async(frame2.copy(), timestamp)
        
        # Play sound
        threading.Thread(target=beep_sound, daemon=True).start()
        
        print(f"📸 Capture #{motion_count} at {datetime.now().strftime('%H:%M:%S')}")
    else:
        motion_detected = False
    
    # Update FPS
    current_fps = update_fps()
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Create UI overlay (add your create_ui_overlay function here)
    # frame2 = create_ui_overlay(frame2, motion_detected, motion_count, current_fps, elapsed_time)
    
    # Simple overlay for now (replace with your fancy UI later)
    cv2.putText(frame2, f"FPS: {current_fps:.1f}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame2, f"Detections: {motion_count}", (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Display window
    cv2.imshow("Security Monitor", frame2)
    
    # Handle key presses
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('+'):
        Config.THRESHOLD = max(5, Config.THRESHOLD - 5)
        print(f"➕ Sensitivity increased (Threshold: {Config.THRESHOLD})")
    elif key == ord('-'):
        Config.THRESHOLD = min(50, Config.THRESHOLD + 5)
        print(f"➖ Sensitivity decreased (Threshold: {Config.THRESHOLD})")
    elif key == ord('c'):
        motion_count = 0
        motion_history.clear()
        print("🔄 Counter reset")
    
    # Update background frame
    frame1_gray = gray

# Cleanup
cap.release()
cv2.destroyAllWindows()
print(f"\n✅ Session ended - {motion_count} detections captured")
