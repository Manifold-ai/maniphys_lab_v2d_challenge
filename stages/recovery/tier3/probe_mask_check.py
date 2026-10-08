"""Probe t3_masks.check_masks: the real ep20 masks must pass; a table-shaped mask and a far-away mask must fail."""
import json, shutil, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, "/lab_data/yqchen/v2d/tier3/scripts")
import t3_masks as tm

W = Path("/lab_data/yqchen/v2d/tier3/runs/work/ep20_rice_cooker")
masks = W / "sam2_masks"
total = len(list((masks / "1").glob("*.png")))
pick = tm.choose_prompt_frame(W / "detect", W / "episode_000020.0.color.mp4", total, "a rice cooker", "/lab_data/yqchen/v2d/weights", 0.3, 13, object_name="rice_cooker")
best = pick["candidates"][0]
sup = best.get("support_boxes", [])
print("prompt", best["frame_index"], "support boxes", len(sup))
print("real:", tm.check_masks(masks, total, 1536, best["frame_index"], sup))

def variant(name, fn):
    d = Path(tempfile.mkdtemp())
    shutil.copytree(masks / "0", d / "0")
    (d / "1").mkdir()
    for p in sorted((masks / "1").glob("*.png")):
        m = np.asarray(Image.open(p).convert("L")) > 0
        Image.fromarray((fn(m) * 255).astype(np.uint8)).save(d / "1" / p.name)
    print(name + ":", tm.check_masks(d, total, 1536, best["frame_index"], sup))
    shutil.rmtree(d)

if sup:
    b = max(sup, key=lambda b: (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))
    def table(m):
        out = np.zeros_like(m); out[int(b["y0"]):int(b["y1"]), int(b["x0"]):int(b["x1"])] = True; return out
    variant("table-shaped", table)
def far(m):
    out = np.zeros_like(m); out[20:120, 1380:1500] = True; return out
variant("far corner", far)
