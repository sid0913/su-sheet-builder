"""
Train a single-class 'architectural feature' detector (YOLOv8) on the tiled
dataset from prep_yolo_dataset.py. GPU required.

Run:  python train_detector.py
Outputs weights to SAM_prototype/yolo_runs/feature_detector/weights/best.pt
"""
import os
from ultralytics import YOLO

SP = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SP, "yolo_dataset", "data.yaml")
PROJECT = os.path.join(SP, "yolo_runs")

# yolov8m: good small-object recall; tiles are already 1024 px so train at 1024.
model = YOLO("yolov8m.pt")
model.train(
    data=DATA,
    imgsz=1024,
    epochs=150,
    patience=30,          # early stop if val mAP plateaus
    batch=8,
    device=0,
    project=PROJECT,
    name="feature_detector",
    exist_ok=True,
    # small, dense, repetitive stones -> keep mosaic, add light scale/rotation
    degrees=5.0, scale=0.3, fliplr=0.5, flipud=0.5,
    mosaic=1.0, close_mosaic=20,
    box=7.5, cls=0.5,
    verbose=True,
)
# validate best
metrics = model.val(data=DATA, imgsz=1024, device=0)
print("VAL mAP50:", round(float(metrics.box.map50), 4),
      "mAP50-95:", round(float(metrics.box.map), 4))
print("DONE_TRAIN")
