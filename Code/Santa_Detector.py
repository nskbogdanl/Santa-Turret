import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2
from ultralytics import YOLO
import time
import numpy as np
import torch
import serial
from pathlib import Path

# ------------------------ DEVICE (CUDA / ROCm / CPU) ------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 Using device: {device}")

# ------------------------ PATHS (CROSS-PLATFORM) ------------------------
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "YOLO" / "Santa_Claus_Weight.pt"

# ------------------------ ARDUINO SETTINGS ------------------------
arduino_port = 'COM3'
baudrate = 9600
last_seen_time = time.time()

try:
    arduino = serial.Serial('COM3', 9600, timeout=1)
    time.sleep(2)
    print(f"✅ Arduino connected on {arduino_port}")
except Exception as e:
    print(f"❌ Failed to connect to Arduino: {e}")
    arduino = None

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
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print("❌ Failed to open webcam")
    exit()

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

            for box in result.boxes:
                cls_idx = int(box.cls[0])
                cls_name = model.names[cls_idx]

                if cls_name == "Santa":
                    santa_boxes.append(box)
                else:
                    other_boxes.append(box)

            best_box = None
            min_distance = float("inf")

            for box in santa_boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                box_center_x = (x1 + x2) / 2
                box_center_y = (x1 + x2) / 2

                distance = ((box_center_x - frame_center_x) ** 2 +
                            (box_center_y - frame_center_y) ** 2) ** 0.5

                if distance < min_distance:
                    min_distance = distance
                    best_box = box

            for box in santa_boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                conf = box.conf[0].item()
                cls_idx = int(box.cls[0])
                cls_name = model.names[cls_idx]

                if box is best_box:
                    last_seen_time = time.time()
                    color = (0, 0, 255)

                    x_center = ((x1 + x2) / 2) / frame_width
                    y_center = ((y1 + y2) / 2) / frame_height

                    # ------------------------ CONTROL INVERSION ------------------------
                    servo_x = int(90 - (x_center - 0.5) * 180)
                    servo_y = int(90 - (y_center - 0.5) * 180)
                    # -------------------------------------------------------------------

                    servo_x = max(0, min(180, servo_x))
                    servo_y = max(0, min(180, servo_y))

                    if arduino:
                        msg = f"{servo_x},{servo_y}\n"
                        arduino.write(msg.encode())
                        print("-> sent:", msg.strip())

                    label = f"TARGET {conf:.2f}"

                else:
                    color = (0, 255, 0)
                    label = f"Santa {conf:.2f}"

                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(frame, label, (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        else:
            if time.time() - last_seen_time < 0.5:
                print("Santa disappeared, still waiting...")

            if arduino:
                print("Santa lost, timeout reached")
                arduino.write(b"90,90\n")

        cv2.imshow("YOLO Webcam", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            if arduino:
                print("STOP")
                arduino.write(b"90,90\n")
                time.sleep(0.2)
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()
