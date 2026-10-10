"""Grounding DINO on CPU (same model and preprocessing as v2d.grounding_dino.lib.image_to_object_bboxes, device cpu).
    python t3_gdino_cpu.py <model dir> <prompt> <out dir> <image>...
"""
import json, os, sys
import groundingdino, imageio.v3 as iio
from groundingdino.util.inference import load_model, predict
from torchvision.ops import box_convert
from v2d.grounding_dino.lib.image_list_to_object_bboxes import _preprocess_image
model_dir, prompt, out = sys.argv[1], sys.argv[2], sys.argv[3]
model = load_model(os.path.join(groundingdino.__path__[0], "config", "GroundingDINO_SwinT_OGC.py"),
                   os.path.join(model_dir, "groundingdino_swint_ogc.pth"), device="cpu")
for path in sys.argv[4:]:
    src = iio.imread(path)
    h, w = src.shape[:2]
    boxes, logits, phrases = predict(model=model, image=_preprocess_image(src), caption=prompt, box_threshold=0.25, text_threshold=0.2, device="cpu")
    xyxy = box_convert(boxes=boxes, in_fmt="cxcywh", out_fmt="xyxy") * boxes.new_tensor([w, h, w, h])
    dets = sorted(({"label": p, "confidence": round(float(l), 4), "box": dict(zip(("x0", "y0", "x1", "y1"), map(float, b)))}
                   for b, l, p in zip(xyxy.tolist(), logits.tolist(), phrases)), key=lambda d: -d["confidence"])
    name = os.path.splitext(os.path.basename(path))[0]
    json.dump(dets, open(os.path.join(out, f"det_{name}.json"), "w"), indent=1)
    print(name, [(d["label"], d["confidence"], [round(v) for v in d["box"].values()]) for d in dets])
