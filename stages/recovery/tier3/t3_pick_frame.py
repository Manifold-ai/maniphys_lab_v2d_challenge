"""Pick the frame that shows the target object best and extract it for SAM 3D Objects image-to-mesh.

Inputs are the SAM2 mask streams `<work>/sam2_masks/0/*.png` (person) and `<work>/sam2_masks/1/*.png`
(object) plus the episode video. Score per frame = object mask area x (1 - overlap of the object mask's
bounding box with the person mask): big, and not hidden behind the person. The chosen frame is written
with ffmpeg (-noautorotate, full resolution) next to a copy of its object mask, both at native size, as
the CARI4D README requires. Motion blur is not measured. In Tier 3 nobody looks at the picked frames
(Kaggle Foundational Rule 4.b).

Tier 3 change from the Track 1 t1_pick_frame.py: picks `--k` frames, greedily by score with at least
`--min-gap-fraction` of the clip between them, so SAM 3D Objects sees the object from several moments. One
frame can show a partial view (ep14: a tipped round table seen top-on gave a 4.8 cm disk). `frame_index` in
pick.json stays the best-scoring frame; `frames` lists all picks.

    python t3_pick_frame.py --work <tier3 work>/ep20_rice_cooker --video <mp4> --out <dir> [--k 3]
"""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "libs" / "v2d_infra"))
from tier_guard import forbid_tier1


def load(p: pathlib.Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("L")) > 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--stride", type=int, default=3, help="score every k-th frame")
    ap.add_argument("--k", type=int, default=3, help="frames to pick")
    ap.add_argument("--min-gap-fraction", type=float, default=0.15, help="minimum spacing between picks, as a share of the clip")
    a = ap.parse_args()
    forbid_tier1()
    work, out = pathlib.Path(a.work).expanduser(), pathlib.Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    obj_dir, person_dir = work / "sam2_masks" / "1", work / "sam2_masks" / "0"
    frames = sorted(obj_dir.glob("*.png"))
    scored = []
    for p in frames[:: a.stride]:
        obj = load(p)
        area = int(obj.sum())
        if area == 0:
            continue
        ys, xs = np.nonzero(obj)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        person_p = person_dir / p.name
        overlap = 0.0
        if person_p.exists():
            person = load(person_p)
            box = person[y0:y1, x0:x1]
            overlap = float(box.mean()) if box.size else 0.0
        touching_edge = y0 == 0 or x0 == 0 or y1 == obj.shape[0] or x1 == obj.shape[1]
        score = area * (1.0 - overlap) * (0.5 if touching_edge else 1.0)
        scored.append((score, int(p.stem), area, overlap, bool(touching_edge)))
    scored.sort(reverse=True)
    gap = a.min_gap_fraction * len(frames)
    picks = []
    for cand in scored:
        if all(abs(cand[1] - p[1]) >= gap for p in picks):
            picks.append(cand)
        if len(picks) == a.k:
            break
    for _, idx, *_ in picks:
        frame_png = out / f"frame_{idx:06d}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-noautorotate", "-i", a.video, "-vf", f"select=eq(n\\,{idx})", "-frames:v", "1", str(frame_png)],
            check=True,
        )
        mask_png = out / f"mask_{idx:06d}.png"
        shutil.copy(obj_dir / f"{idx:06d}.png", mask_png)
        fw, fh = Image.open(frame_png).size
        mw, mh = Image.open(mask_png).size
        assert (fw, fh) == (mw, mh), f"frame {fw}x{fh} vs mask {mw}x{mh}: sizes must match"
    best = picks[0]
    idx = best[1]
    frame_png, mask_png = out / f"frame_{idx:06d}.png", out / f"mask_{idx:06d}.png"
    report = {
        "frame_index": idx,
        "frames": [p[1] for p in picks],
        "frame": str(frame_png),
        "mask": str(mask_png),
        "size": [fw, fh],
        "candidates": [
            {"frame_index": f, "area_px": ar, "person_overlap": round(ov, 3), "touches_edge": te, "score": round(sc)}
            for sc, f, ar, ov, te in scored[: a.top]
        ],
    }
    (out / "pick.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["candidates"][0]), "->", frame_png.name)


if __name__ == "__main__":
    main()
