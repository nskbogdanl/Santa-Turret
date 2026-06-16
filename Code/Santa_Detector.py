import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2
from ultralytics import YOLO
import time
import numpy as np
import torch
import serial
import serial.tools.list_ports
from pathlib import Path


def find_arduino():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        description = port.description.lower()
        if port.vid == 0x2341:  # Arduino VID
            print(f"✅ Arduino found on: {port.device}")
            return port.device
    return None

def connect_arduino(arduino_port, baudrate):
    try:
        arduino = serial.Serial(arduino_port, baudrate, timeout=1)
        time.sleep(2)
        print(f"✅ Arduino connected on {arduino_port}")
        return arduino
    except Exception as e:
        print(f"❌ Failed to connect to Arduino: {e}")
        return None
    
def send_arduino(arduino, msg, arduino_port, baudrate):
    try:
        arduino.write(msg)
        print(f"📡 Sent to Arduino: {msg.decode().strip()}")
    except serial.SerialException:
        arduino = connect_arduino(arduino_port, baudrate)
    return arduino

# ------------------------ DEVICE (CUDA / ROCm / CPU) ------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 Using device: {device}")

# ------------------------ PATHS (CROSS-PLATFORM) ------------------------
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "Santa_Claus_Weight.pt"
assert MODEL_PATH.exists(), f"❌ Model not found: {MODEL_PATH}"

# ------------------------ ARDUINO SETTINGS ------------------------
arduino_port = find_arduino()
baudrate = 9600 # Make sure, that baudrate in arduino script is the same
last_seen_time = time.time()
reset_send = False
SEND_INTERVAL = 0.05  # 50ms = max 20 commands/second, to avoid overwhelming the Arduino
last_send_time = 0

arduino=connect_arduino(arduino_port, baudrate)
arduino=send_arduino(arduino, b"90,90\n", arduino_port, baudrate) # Send 90, 90 to servos (Full stop)

# ------------------------ MODEL LOADING ------------------------
print("0. Program started")
t0 = time.time()

model = YOLO(str(MODEL_PATH))
model.to(device)

print(f"1. Model loaded in {time.time() - t0:.2f} sec")

torch.set_num_threads(4)

print("2. Warming up model...")
dummy = np.zeros((640, 640, 3), dtype=np.uint8)
t_warm = time.time()

model(dummy, imgsz=640, device=device, verbose=False)

print(f"3. Warm-up completed in {time.time() - t_warm:.2f} sec")

# ------------------------ CAMERA ------------------------
print("4. Opening camera")
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G')) # Must be set before FPS and resolution
cap.set(cv2.CAP_PROP_FPS, 90) # FPS of the camera
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920) # Resolution X-Axis
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1200) # Resolution Y-Axis

if not cap.isOpened():
    print("❌ Failed to open webcam")
    exit()

actual_fps = cap.get(cv2.CAP_PROP_FPS)
actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
print(f"Actual settings: {actual_width}x{actual_height} @ {actual_fps}fps")

print("5. Camera opened")
print("Press 'q' to exit")

# ------------------------ MAIN LOOP ------------------------
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to get frame")
            break

        frame_height, frame_width, _ = frame.shape

        results = model(
            frame,
            imgsz=640,
            conf=0.5,
            device=device,
            verbose=False
        )
        result = results[0]

        if len(result.boxes) > 0:

            frame_center_x = frame_width / 2
            frame_center_y = frame_height / 2

            santa_boxes = []
            other_boxes = []

            for box in result.boxes: # Filtering classes
                cls_idx = int(box.cls[0])
                cls_name = model.names[cls_idx]

                if cls_name == "Santa":
                    santa_boxes.append(box)
                else:
                    other_boxes.append(box)

            best_box = None
            min_distance = float("inf")

            for box in santa_boxes: # Finding the most centered Santa
                x1, y1, x2, y2 = box.xyxy[0]
                box_center_x = (x1 + x2) / 2
                box_center_y = (y1 + y2) / 2

                distance = ((box_center_x - frame_center_x) ** 2 +
                            (box_center_y - frame_center_y) ** 2) ** 0.5

                if distance < min_distance:
                    min_distance = distance
                    best_box = box

            for box in santa_boxes: # Draw all Santa-Boxes
                x1, y1, x2, y2 = box.xyxy[0]
                conf = box.conf[0].item()

                if box is best_box: # Aiming at the most centered Santa
                    last_seen_time = time.time()
                    reset_send = False
                    color = (0, 0, 255)

                    x_center = ((x1 + x2) / 2) / frame_width
                    y_center = ((y1 + y2) / 2) / frame_height

                    # ------------------------ CONTROL INVERSION ------------------------
                    servo_x = int(90 - (x_center - 0.5) * 180)
                    servo_y = int(90 - (y_center - 0.5) * 180)
                    # -------------------------------------------------------------------

                    servo_x = max(50, min(130, servo_x)) # To make sure that
                    servo_y = max(50, min(130, servo_y)) # servos get command 0-180

                    if arduino and (time.time() - last_send_time >= SEND_INTERVAL):
                        arduino=send_arduino(arduino, f"{servo_x},{servo_y}\n".encode(), arduino_port, baudrate)
                        last_send_time = time.time()
                    label = f"TARGET {conf:.2f}"

                else:
                    color = (0, 255, 0)
                    label = f"Santa {conf:.2f}"

                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(frame, label, (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        else:
            if time.time() - last_seen_time < 0.5: # If santa wasn't found for 0.5 seconds
                print("Santa disappeared, still waiting...")
            elif arduino and not reset_send:
                arduino=send_arduino(arduino, b"90,90\n", arduino_port, baudrate) # Send 90, 90 to servos (Full stop)
                reset_send=True

        cv2.imshow("YOLO Webcam", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            if arduino:
                print("STOP")
                arduino=send_arduino(arduino, b"90,90\n", arduino_port, baudrate) # Send 90, 90 to servos (Full stop)
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()