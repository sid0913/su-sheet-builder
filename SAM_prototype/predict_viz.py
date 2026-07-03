import os, glob, random
import numpy as np
from PIL import Image
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from ultralytics import YOLO

random.seed(1)
SP = r"C:\Users\Photogrammetry\AutomateSuSheetCreation\SAM_prototype"
WEIGHTS = os.path.join(SP, "yolo_runs", "feature_detector", "weights", "best.pt")
VAL_IMG = os.path.join(SP, "yolo_dataset", "images", "val")
VAL_LBL = os.path.join(SP, "yolo_dataset", "labels", "val")
OUT = os.path.join(SP, "detector_pred_vs_gt.png")
CONF = 0.25

imgs = random.sample(glob.glob(os.path.join(VAL_IMG, "*.png")), 6)
model = YOLO(WEIGHTS)
res = model.predict(imgs, conf=CONF, imgsz=1024, device=0, verbose=False)

fig, ax = plt.subplots(2, 3, figsize=(21, 14))
for a, img_path, r in zip(ax.ravel(), imgs, res):
    im = np.array(Image.open(img_path)); H, W = im.shape[:2]
    a.imshow(im); a.set_xticks([]); a.set_yticks([])
    # GT boxes (green)
    lbl = os.path.join(VAL_LBL, os.path.splitext(os.path.basename(img_path))[0] + ".txt")
    ng = 0
    if os.path.exists(lbl):
        for line in open(lbl):
            p = line.split()
            if len(p) < 5: continue
            cx, cy, w, h = [float(x) for x in p[1:5]]
            a.add_patch(mpatches.Rectangle(((cx-w/2)*W, (cy-h/2)*H), w*W, h*H,
                        fill=False, edgecolor="lime", linewidth=0.8)); ng += 1
    # predicted boxes (red)
    nb = len(r.boxes)
    for b in r.boxes.xyxy.cpu().numpy():
        a.add_patch(mpatches.Rectangle((b[0], b[1]), b[2]-b[0], b[3]-b[1],
                    fill=False, edgecolor="red", linewidth=0.8))
    a.set_title(f"{os.path.basename(img_path)}  GT(green)={ng}  pred(red)={nb}", fontsize=9)
plt.tight_layout(); plt.savefig(OUT, dpi=110, bbox_inches="tight")
print("wrote", OUT)
