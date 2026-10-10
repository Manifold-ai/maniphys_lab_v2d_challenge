"""Focal length of each Tier 3 exo camera from Depth Anything 3 (DA3-LARGE-1.1, Apache-2.0), a fourth estimate next to
MoGe-2, GeoCalib and the ceiling grid. CPU.

Per episode: FRAMES full-resolution frames spread over the clip, each run as a single view, and the same frames run
together as one multi-view batch (a fixed camera has no parallax, so the batch mainly averages). DA3 reports intrinsics at
its processing resolution; they are scaled back to the 1536 px video width.

    python t3_da3_intrinsics.py <DA3 weights dir> <tier3 work root> <comma-separated episode dir names> <out .json>
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

FRAMES = 5


def main() -> None:
    from depth_anything_3.api import DepthAnything3

    weights, work, names, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].split(","), Path(sys.argv[4])
    torch.set_num_threads(4)
    model = DepthAnything3.from_pretrained(str(weights)).eval().to("cpu")

    def focal(frames: list[np.ndarray]) -> list[dict]:
        with torch.no_grad():
            pred = model.inference(frames)
        w_proc = pred.processed_images.shape[2]
        rows = []
        for k, frame in zip(pred.intrinsics, frames):
            s = frame.shape[1] / w_proc
            rows.append({"fx": round(float(k[0, 0]) * s, 1), "fy": round(float(k[1, 1]) * s, 1),
                         "cx": round(float(k[0, 2]) * s, 1), "cy": round(float(k[1, 2]) * s, 1)})
        return rows

    result = []
    for name in names:
        vids = sorted((work / name).glob("episode_*.0.color.mp4"))
        if not vids:
            continue
        cap = cv2.VideoCapture(str(vids[0]))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        for i in np.linspace(0, n - 1, FRAMES).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
            ok, f = cap.read()
            if ok:
                frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        single = [focal([f])[0] for f in frames]
        multi = focal(frames)
        row = {"episode": name, "single": single, "multi": multi,
               "fx_single_median": float(np.median([r["fx"] for r in single])), "fx_multi_median": float(np.median([r["fx"] for r in multi]))}
        result.append(row)
        print(json.dumps({"episode": name, "fx_single": [r["fx"] for r in single], "fx_multi": [r["fx"] for r in multi],
                          "cy_single": [r["cy"] for r in single]}), flush=True)
    out.write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
