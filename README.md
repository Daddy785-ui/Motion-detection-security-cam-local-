# Motion Detection Security Cam (Local) 🎥

A lightweight Python script that turns your webcam into a motion detection security camera. Runs entirely locally on your Windows machine.

## ✨ Features

- Real-time motion detection with visual feedback
- Automatic photo capture when motion is detected
- Beep alert on detection
- Adjustable sensitivity (hotkeys)
- Clean on-screen display with stats
- Zero configuration required - just run it!

## 🚀 Quick Start

### Prerequisites
- Python 3.6 or newer
- Windows (for sound alerts)

### Installation

1. **Clone or download this repo**
   ```bash
   git clone https://github.com/YOUR_USERNAME/motion-security-cam-local.git
   cd motion-security-cam-local
Install required packages


pip install opencv-python numpy
Run it!


python motion_cam.py
🎮 Controls
Key	Action
q	Quit the program
+	Increase sensitivity (detect smaller movements)
-	Decrease sensitivity (ignore small movements)
c	Reset motion counter
⚙️ How It Works
The script captures your webcam feed

Compares each frame to detect changes

Draws green boxes around moving objects

Saves a photo when motion is detected

Plays a beep sound as an alert

All photos are saved in the motion_captures folder (created automatically).

🔧 Customizing Sensitivity
Edit these values in the Config class at the top of the script:


THRESHOLD = 25        # Lower = more sensitive (5-50 range works well)
MIN_CONTOUR_AREA = 1000  # Lower = detect smaller objects
RESOLUTION = (640, 480)  # Change camera resolution
BLUR_SIZE = (15, 15)     # Lower = more sensitive to noise
📁 Output
When motion is detected, images are saved as:

motion_captures/motion_20240101_123456_789.jpg
⚠️ Notes
Windows only (uses winsound for beeps)

Works best in well-lit rooms

The camera may turn off in very dark conditions (hardware limitation)

All processing is done locally - no internet required

📝 License
MIT License - feel free to use and modify!

🤝 Contributing
Found a bug? Want to improve it? Open an issue or submit a pull request!
