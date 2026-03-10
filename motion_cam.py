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
    THRESHOLD = 25
    MIN_CONTOUR_AREA = 1000
    COOLDOWN = 2.0
    OVERLAY_DURATION = 5.0
    SAVE_QUALITY = 90
    THEME_COLOR = (41, 128, 185)
    ALERT_COLOR = (231, 76, 60)
    SUCCESS_COLOR = (46, 204, 113)

# UI Panel class for draggable and resizable panels
class UIPanel:
    def __init__(self, name, x, y, width, height, color=(40,40,55)):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.min_width = 200
        self.min_height = 150
        
    def contains(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height
    
    def get_resize_handle(self, x, y, handle_size=15):
        handles = {
            "bottom-right": (self.x + self.width - handle_size, self.y + self.height - handle_size, handle_size, handle_size)
        }
        
        for direction, (hx, hy, hw, hh) in handles.items():
            if hx <= x <= hx + hw and hy <= y <= hy + hh:
                return direction
        return None
    
    def start_drag(self, x, y):
        self.dragging = True
        self.drag_offset_x = x - self.x
        self.drag_offset_y = y - self.y
        
    def start_resize(self, x, y, direction):
        self.resizing = True
        self.resize_direction = direction
        self.drag_offset_x = x
        self.drag_offset_y = y
        
    def update_drag(self, x, y):
        if self.dragging:
            self.x = x - self.drag_offset_x
            self.y = y - self.drag_offset_y
            
    def update_resize(self, x, y):
        if not self.resizing:
            return
            
        if self.resize_direction == "bottom-right":
            new_width = x - self.x
            new_height = y - self.y
            if new_width >= self.min_width:
                self.width = new_width
            if new_height >= self.min_height:
                self.height = new_height
    
    def stop_interaction(self):
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        
    def draw(self, frame, overlay):
        # Draw panel background
        cv2.rectangle(overlay, (self.x, self.y), (self.x + self.width, self.y + self.height), 
                     self.color, -1)
        
        # Draw resize handle (only bottom-right for simplicity)
        handle_color = (100, 100, 120)
        handle_size = 15
        cv2.rectangle(overlay, 
                     (self.x + self.width - handle_size, self.y + self.height - handle_size), 
                     (self.x + self.width, self.y + self.height), 
                     handle_color, -1)
        
        return overlay

# Create capture folder
if not os.path.exists("motion_captures"):
    os.makedirs("motion_captures")

# Performance optimizations
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

# Initialize video capture
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.RESOLUTION[0])
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.RESOLUTION[1])
cap.set(cv2.CAP_PROP_FPS, Config.FPS_LIMIT)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Create resizable window
cv2.namedWindow("Security Monitor", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Security Monitor", Config.RESOLUTION[0], Config.RESOLUTION[1])

# Create UI Panels
panels = [
    UIPanel("Status", 20, 300, 280, 180, (40, 40, 55)),
    UIPanel("History", 400, 80, 200, 100, (40, 40, 55))
]

# Mouse interaction variables
active_panel = None
interaction_mode = None

# Global variables
motion_history = []
motion_detected = False
last_motion_time = 0
motion_count = 0
fps = 0
frame_count = 0
last_fps_time = time.time()

# Mouse callback function
def mouse_callback(event, x, y, flags, param):
    global active_panel, interaction_mode, panels
    
    if event == cv2.EVENT_LBUTTONDOWN:
        for panel in reversed(panels):
            resize_dir = panel.get_resize_handle(x, y)
            if resize_dir:
                active_panel = panel
                interaction_mode = "resize"
                panel.start_resize(x, y, resize_dir)
                print(f"Resizing {panel.name}")
                return
            
            if panel.contains(x, y):
                active_panel = panel
                interaction_mode = "drag"
                panel.start_drag(x, y)
                print(f"Dragging {panel.name}")
                return
                
    elif event == cv2.EVENT_MOUSEMOVE:
        if active_panel and interaction_mode == "drag":
            active_panel.update_drag(x, y)
        elif active_panel and interaction_mode == "resize":
            active_panel.update_resize(x, y)
            
    elif event == cv2.EVENT_LBUTTONUP:
        if active_panel:
            active_panel.stop_interaction()
            active_panel = None
            interaction_mode = None
            print("Interaction ended")

# Set mouse callback
cv2.setMouseCallback("Security Monitor", mouse_callback)

# Read initial frame
ret, frame1 = cap.read()
frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
frame1_gray = cv2.GaussianBlur(frame1_gray, Config.BLUR_SIZE, 0)

def beep_sound():
    try:
        winsound.Beep(1000, 200)
    except:
        pass

def save_image_async(image, timestamp):
    def save():
        filename = f"motion_captures/motion_{timestamp}.jpg"
        cv2.imwrite(filename, image, [cv2.IMWRITE_JPEG_QUALITY, Config.SAVE_QUALITY])
    threading.Thread(target=save, daemon=True).start()

def draw_text_in_panel(overlay, text, x, y, max_width, max_height, scale=0.5, color=(255,255,255)):
    """Draw text that stays inside panel boundaries"""
    # Split text into words
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        text_size = cv2.getTextSize(test_line, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0]
        
        if text_size[0] <= max_width - 20:  # Leave margin
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # Draw each line
    line_height = int(20 * scale * 2)
    current_y = y
    
    for line in lines:
        if current_y + line_height > y + max_height - 10:  # Don't draw outside panel
            break
        cv2.putText(overlay, line, (x + 10, current_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)
        current_y += line_height

def create_ui_overlay(frame, motion_detected, motion_count, fps, elapsed_time):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    # Draw header (fixed position)
    header_height = 60
    cv2.rectangle(overlay, (0, 0), (w, header_height), (30, 30, 46), -1)
    
    # Scale header text based on window width
    header_scale = min(1.0, w / 800)
    cv2.putText(overlay, "SECURITY MONITOR", (20, 45), cv2.FONT_HERSHEY_DUPLEX, 
                header_scale, (255, 255, 255), 2, cv2.LINE_AA)
    
    # Status indicator
    status_color = Config.ALERT_COLOR if motion_detected else Config.SUCCESS_COLOR
    status_text = "ACTIVE" if not motion_detected else "ALERT"
    cv2.circle(overlay, (w - 100, 30), 8, status_color, -1)
    cv2.putText(overlay, status_text, (w - 80, 38), cv2.FONT_HERSHEY_SIMPLEX, 
                0.7, (255, 255, 255), 1, cv2.LINE_AA)
    
    # Draw all panels
    for panel in panels:
        overlay = panel.draw(frame, overlay)
        
        # Draw panel-specific content that STAYS INSIDE the panel
        if panel.name == "Status":
            # Panel title
            title_scale = min(0.7, panel.width / 400)
            cv2.putText(overlay, "SYSTEM STATUS", 
                       (panel.x + 10, panel.y + 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, title_scale, (200, 200, 220), 1, cv2.LINE_AA)
            
            # Calculate text scale based on panel height
            text_scale = min(0.6, panel.height / 300)
            line_height = int(25 * text_scale * 2)
            
            stats = [
                f"Detections: {motion_count}",
                f"FPS: {fps:.1f}",
                f"Runtime: {elapsed_time//60:02.0f}:{elapsed_time%60:02.0f}",
                f"Threshold: {Config.THRESHOLD}"
            ]
            
            # Draw each stat, ensuring it stays inside panel
            for i, stat in enumerate(stats):
                y_pos = panel.y + 50 + i * line_height
                if y_pos + line_height < panel.y + panel.height - 20:
                    # Split long text if needed
                    if len(stat) > 15 and panel.width < 250:
                        parts = stat.split(': ')
                        if len(parts) == 2:
                            draw_text_in_panel(overlay, parts[0] + ':', 
                                             panel.x, y_pos, panel.width, panel.height, 
                                             text_scale * 0.8, (180, 180, 200))
                            draw_text_in_panel(overlay, parts[1], 
                                             panel.x, y_pos + line_height, panel.width, panel.height, 
                                             text_scale, Config.THEME_COLOR)
                    else:
                        # Draw label and value with different colors
                        label, value = stat.split(': ')
                        cv2.putText(overlay, label + ':', (panel.x + 10, y_pos), 
                                   cv2.FONT_HERSHEY_SIMPLEX, text_scale, (180, 180, 200), 1, cv2.LINE_AA)
                        
                        value_x = panel.x + panel.width - 100
                        if value_x > panel.x + 10:
                            cv2.putText(overlay, value, (value_x, y_pos), 
                                       cv2.FONT_HERSHEY_SIMPLEX, text_scale, Config.THEME_COLOR, 1, cv2.LINE_AA)
        
        elif panel.name == "History":
            # Panel title
            cv2.putText(overlay, "HISTORY", (panel.x + 10, panel.y + 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 220), 1, cv2.LINE_AA)
            
            # Draw mini graph that scales with panel
            if len(motion_history) > 1:
                graph_h = panel.height - 50
                graph_w = panel.width - 30
                graph_x = panel.x + 15
                graph_y = panel.y + 35
                
                if graph_h > 20 and graph_w > 20:
                    max_val = max(motion_history) if max(motion_history) > 0 else 1
                    points = []
                    for i, val in enumerate(motion_history[-min(20, len(motion_history)):]):
                        x = graph_x + i * (graph_w / min(20, len(motion_history)))
                        y = graph_y + graph_h - (val / max_val) * graph_h
                        points.append((int(x), int(y)))
                    
                    for i in range(1, len(points)):
                        if 0 <= points[i-1][0] <= w and 0 <= points[i-1][1] <= h:
                            cv2.line(overlay, points[i-1], points[i], Config.THEME_COLOR, 1, cv2.LINE_AA)
    
    # Time display (top right)
    current_time = datetime.now().strftime("%H:%M:%S")
    date_str = datetime.now().strftime("%Y-%m-%d")
    cv2.putText(overlay, current_time, (w - 120, 25), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(overlay, date_str, (w - 120, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 200), 1, cv2.LINE_AA)
    
    # Add transparency
    alpha = 0.85
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    
    # Alert banner
    if motion_detected:
        banner_height = 40
        banner_overlay = frame.copy()
        cv2.rectangle(banner_overlay, (0, header_height), (w, header_height + banner_height), 
                     Config.ALERT_COLOR, -1)
        
        flash = int((time.time() * 10) % 2)
        text = "⚠️  MOTION DETECTED  ⚠️"
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)[0]
        text_x = (w - text_size[0]) // 2
        
        if flash:
            cv2.putText(banner_overlay, text, (text_x, header_height + 28), 
                       cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.putText(banner_overlay, text, (text_x, header_height + 28), 
                       cv2.FONT_HERSHEY_DUPLEX, 0.7, (30, 30, 30), 2, cv2.LINE_AA)
        
        alpha = 0.6
        cv2.addWeighted(banner_overlay, alpha, frame, 1 - alpha, 0, frame)
    
    return frame

def update_fps():
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
print("   Press 'c' to reset counter")
print("🎮 Drag panels by clicking inside them")
print("📏 Resize panels by dragging the bottom-right corner")
print("📝 Text automatically wraps and scales to fit panels")

start_time = time.time()

while True:
    ret, frame2 = cap.read()
    if not ret:
        break
    
    # Process for motion detection
    gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, Config.BLUR_SIZE, 0)
    
    diff = cv2.absdiff(frame1_gray, gray)
    thresh = cv2.threshold(diff, Config.THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    current_motion = False
    motion_intensity = 0
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < Config.MIN_CONTOUR_AREA:
            continue
        
        current_motion = True
        motion_intensity += area
        
        x, y, w, h = cv2.boundingRect(contour)
        
        cv2.rectangle(frame2, (x-2, y-2), (x+w+2, y+h+2), (255, 255, 255), 1)
        
        intensity = min(area / 5000, 1.0)
        color = tuple(int(Config.ALERT_COLOR[i] * intensity + 50) for i in range(3))
        cv2.rectangle(frame2, (x, y), (x + w, y + h), color, 2)
        
        label = f"{int(area)}px"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.rectangle(frame2, (x, y - label_size[1] - 4), 
                     (x + label_size[0] + 4, y), color, -1)
        cv2.putText(frame2, label, (x + 2, y - 2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    motion_history.append(motion_intensity)
    if len(motion_history) > 50:
        motion_history.pop(0)
    
    if current_motion and (time.time() - last_motion_time > Config.COOLDOWN):
        last_motion_time = time.time()
        motion_detected = True
        motion_count += 1
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        ret, original_frame = cap.read()
        if ret:
            save_image_async(original_frame, timestamp)
        
        threading.Thread(target=beep_sound, daemon=True).start()
        
        print(f"📸 Capture #{motion_count} at {datetime.now().strftime('%H:%M:%S')}")
    else:
        motion_detected = False
    
    current_fps = update_fps()
    elapsed_time = time.time() - start_time
    
    frame2 = create_ui_overlay(frame2, motion_detected, motion_count, current_fps, elapsed_time)
    
    cv2.imshow("Security Monitor", frame2)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('+') or key == ord('='):
        Config.THRESHOLD = max(5, Config.THRESHOLD - 5)
        print(f"➕ Sensitivity increased (Threshold: {Config.THRESHOLD})")
    elif key == ord('-') or key == ord('_'):
        Config.THRESHOLD = min(50, Config.THRESHOLD + 5)
        print(f"➖ Sensitivity decreased (Threshold: {Config.THRESHOLD})")
    elif key == ord('c'):
        motion_count = 0
        motion_history.clear()
        print("🔄 Counter reset")
    
    frame1_gray = gray

cap.release()
cv2.destroyAllWindows()
print(f"\n✅ Session ended - {motion_count} detections captured")
