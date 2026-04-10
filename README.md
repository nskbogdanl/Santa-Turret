# Santa-Turret

Trigger-based real-time object detection system using YOLO that tracks a target ("Santa") and controls two servo motors via Arduino.

---

## Features

-  Real-time webcam video processing  
-  Object detection using Ultralytics YOLOv26
-  Prioritizes class `Santa` detection
-  Selects object closest to frame center as target  
-  Controls 2-axis servo system via Arduino (Serial)  
-  Model warm-up for faster inference  

---

## How It Works

1. Webcam captures frames  
2. YOLO model runs inference on each frame  
3. Filters detections for class `Santa`  
4. Chooses detection closest to image center  
5. Converts normalized coordinates to servo commands:
   - X → servoX (0–180)
   - Y → servoY (0–180)
   - 90 = stop, 180 - max speed CW, 0 - max speed CCW
6. Sends data to Arduino in format:
   ```
   x,y
   ```

---

## Tech Stack

- Python 3.10+
- OpenCV
- PyTorch
- Ultralytics YOLO
- NumPy
- pySerial
- Arduino (C++)

---

## Installation

```bash
pip install ultralytics opencv-python numpy torch pyserial
```

---

## Project Structure

```
│
├── Code/
│ ├── Santa_Detector.py
│ ├── Santa_Claus_Weight.pt
│ └── Arduino.ino
│
├── STL/
│ ├── *.stl (parts for 3D-printing)
│
├── Kompas 3D/
│ ├── *.m3d
│ ├── *.m3d.bak
│ └── CAD design files
│
└── README.md
```

---

## Arduino Setup

Upload sketch "Arduino.ino" to your Arduino

---

## Run Project

```bash
python main.py
```

Exit:
```
q
```

---

## Communication Protocol

Python → Arduino:

```
x,y
```

Example:
```
120,45
```

---

## Behavior Logic

- Red box → active target  
- Green boxes → other detections  
- If target lost → servos stop 

---

## Optimizations Used

- YOLO warm-up before loop  
- CPU thread limiting  
- Fixed inference size (640)  
- Confidence threshold filtering  

---

## Author

Bogdan Lomp  
GitHub: [Santa-Turret](https://github.com/nskbogdanl/Santa-Turret)
