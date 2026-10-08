"""Injected-defect probe for t3_masks.check_masks on real SAM2 output.

Must pass: the real masks of ep20 (rice cooker rotated in place) and ep05 (big box near the camera, larger
than the person). Must fail: the ep20 object mask replaced by the largest detected table box (a support),
moved to a far corner (never touched), and unioned with the table box on every frame except the prompt
frame (SAM2 leaking onto the table after the prompt).

    python probe_mask_check.py <tier3 work dir> <weights dir>
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_masks as tm


def prompt_of(work: Path, name: str, weights: str):
    d = work / name
    video = next(d.glob("episode_*.0.color.mp4"))
    total = len(list((d / "sam2_masks" / "1").glob("*.png")))
    obj = name.split("_", 1)[1]
    pick = tm.choose_prompt_frame(d / "detect", video, total, "a " + obj.replace("_", " "), weights, 0.3, 13, object_name=obj)
    return d / "sam2_masks", total, pick["candidates"][0]


def check(masks: Path, total: int, best: dict) -> dict:
    return tm.check_masks(masks, total, 1536, best["frame_index"], best["box"], best.get("support_boxes", []))


def variant(masks: Path, total: int, best: dict, fn) -> dict:
    d = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(masks / "0", d / "0")
        (d / "1").mkdir()
        for p in sorted((masks / "1").glob("*.png")):
            m = np.asarray(Image.open(p).convert("L")) > 0
            Image.fromarray(fn(m, int(p.stem)).astype(np.uint8) * 255).save(d / "1" / p.name)
        return check(d, total, best)
    finally:
        shutil.rmtree(d)


def main() -> None:
    work, weights = Path(sys.argv[1]), sys.argv[2]
    results = {}
    for name in ("ep20_rice_cooker", "ep05_big_black_box"):
        masks, total, best = prompt_of(work, name, weights)
        results[f"real {name}"] = (check(masks, total, best), True)
    masks, total, best = prompt_of(work, "ep20_rice_cooker", weights)
    table = max(best["support_boxes"], key=lambda b: (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))

    def table_mask(m):
        out = np.zeros_like(m)
        out[int(table["y0"]):int(table["y1"]), int(table["x0"]):int(table["x1"])] = True
        return out

    def far(m, _):
        out = np.zeros_like(m)
        out[20:120, 1380:1500] = True
        return out

    results["table-shaped"] = (variant(masks, total, best, lambda m, _: table_mask(m)), False)
    results["far corner"] = (variant(masks, total, best, far), False)
    results["leak after prompt"] = (variant(masks, total, best, lambda m, i: m if i == best["frame_index"] else m | table_mask(m)), False)
    bad = 0
    for label, (r, want_ok) in results.items():
        verdict = "as expected" if r["ok"] == want_ok else "WRONG"
        bad += verdict == "WRONG"
        print(f"{verdict:11s} {label}: ok={r['ok']} {r['why']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
