"""Camera height and horizon of one fixed exo camera from objects resting on the floor, without its focal length.

Single-view metrology: a floor point seen at image row v, at depth z, satisfies v - v_h = f h / z (small pitch), where
v_h is the horizon row and h the camera height. f / z, the pixels per metre at that depth, is measured from the
object itself: the official mesh at CARI4D's pose renders s_render pixels wide (linear, sqrt of area) with MoGe's
focal f_m at depth z_0, the SAM2 mask is s_mask wide, so f / z = (f_m / z_0) * s_mask / s_render whatever the true f.
Regressing the mask's lowest row (where the object meets the floor) on f / z over many resting objects gives v_h
(intercept, pixels) and h (slope, metres). h is compared with the released ground plane's offset (1.39 m), which
equals the camera height only if this camera is the world camera; v_h with the horizon each focal/pitch pair implies.

Events (Tier 3 inputs and CARI4D output only): every EVERY-th frame where the object is physically still, judged on the
mask itself (centroid moves < STILL_PX and area changes < STILL_AREA between frames i-STILL_GAP and i+STILL_GAP;
CARI4D's own trajectory jitters too much to tell rest from motion), kept when the mask is big (>= MIN_PX), clear of the person
(overlap <= MAX_PERSON) and of the image border, the render agrees with it (IoU >= MIN_IOU, so CARI4D's rotation is
usable), and CARI4D's lowest point is within FLOOR_M of the released plane taken in the camera frame (floor, not a
table; the depth scale is off by a few percent, a table is 0.7 m up).

    python t3_camera_height.py <tier3 root> <comma-separated episode dir names> <out .json>
"""

import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from t3_object_check import load_mesh, rasterise

STILL_PX = 3.0
STILL_AREA = 0.05
STILL_GAP = 5
EVERY = 5
MIN_PX = 1500
MAX_PERSON = 0.02
BORDER = 5
MIN_IOU = 0.6
FLOOR_M = 0.30


def huber_line(x: np.ndarray, y: np.ndarray, k: float = 3.0, iters: int = 50) -> tuple[float, float, np.ndarray]:
    w = np.ones_like(x)
    for _ in range(iters):
        a = np.vstack([np.ones_like(x), x]).T * np.sqrt(w)[:, None]
        c0, c1 = np.linalg.lstsq(a, y * np.sqrt(w), rcond=None)[0]
        r = y - (c0 + c1 * x)
        s = 1.4826 * np.median(np.abs(r)) + 1e-9
        w = np.minimum(1.0, k * s / np.maximum(np.abs(r), 1e-9))
    return float(c0), float(c1), r


def main() -> None:
    root, names, out = Path(sys.argv[1]), sys.argv[2].split(","), Path(sys.argv[3])
    metas = {f"ep{m['episode_index']:02d}_{m['object']}": m for m in
             map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    events, per_ep = [], {}
    for name in names:
        conv, work, m = root / "runs/convert" / name, root / "runs/work" / name, metas[name]
        if not (conv / "object_cam.npz").exists():
            continue
        oc = np.load(conv / "object_cam.npz")
        poses, k = oc["T_cam_glb"].astype(np.float64), np.asarray(oc["intrinsics"], np.float64)
        fm = k[1, 1]
        gp = np.asarray(t3_inputs.ground_plane(root, m), np.float64)
        n_w, d_w = gp[:3] / np.linalg.norm(gp[:3]), gp[3] / np.linalg.norm(gp[:3])
        if d_w < 0:
            n_w, d_w = -n_w, -d_w
        verts, faces = load_mesh(root / "input" / m["mesh"])
        kept = 0
        why = {"sampled": 0, "moving": 0, "small": 0, "person": 0, "border": 0, "not_floor": 0, "iou": 0}

        def mask(i: int) -> np.ndarray | None:
            f = work / "sam2_masks/1" / f"{i:06d}.png"
            return np.asarray(Image.open(f).convert("L")) > 0 if f.exists() else None

        for i in range(STILL_GAP, len(poses) - STILL_GAP, EVERY):
            obj = mask(i)
            if obj is None:
                continue
            why["sampled"] += 1
            before, after = mask(i - STILL_GAP), mask(i + STILL_GAP)
            if before is None or after is None or not before.any() or not after.any() or not obj.any():
                why["moving"] += 1
                continue
            cb, ca = np.argwhere(before).mean(0), np.argwhere(after).mean(0)
            if np.linalg.norm(cb - ca) > STILL_PX or abs(float(after.sum()) / float(before.sum()) - 1) > STILL_AREA:
                why["moving"] += 1
                continue
            pm = work / "sam2_masks/0" / f"{i:06d}.png"
            person = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros_like(obj)
            h, w = obj.shape
            area = int(obj.sum())
            if area < MIN_PX:
                why["small"] += 1
                continue
            if (obj & person).sum() > MAX_PERSON * area:
                why["person"] += 1
                continue
            ys, xs = np.nonzero(obj)
            if ys.min() < BORDER or xs.min() < BORDER or ys.max() >= h - BORDER or xs.max() >= w - BORDER:
                why["border"] += 1
                continue
            t = poses[i]
            vc = verts @ t[:3, :3].T + t[:3, 3]
            if float((vc @ n_w + d_w).min()) > FLOOR_M:
                why["not_floor"] += 1
                continue
            rend = rasterise(vc, faces, k, h, w)
            iou = float((rend & obj).sum()) / float((rend | obj).sum())
            if iou < MIN_IOU:
                why["iou"] += 1
                continue
            low = vc[np.argmax(vc[:, 1] / vc[:, 2])]  # vertex that projects lowest in the image
            ppm = fm / low[2] * np.sqrt(area / rend.sum())
            v_low = float(np.percentile(ys, 99.5))  # robust lowest mask row
            events.append({"episode": name, "frame": i, "v": round(v_low, 1), "ppm": round(float(ppm), 2), "iou": round(iou, 3),
                           "scale": round(float(np.sqrt(area / rend.sum())), 4), "released_d": round(float(d_w), 4)})
            kept += 1
        per_ep[name] = kept
        print(json.dumps({"episode": name, "events": kept, **why}), flush=True)
    x = np.array([e["ppm"] for e in events])
    y = np.array([e["v"] for e in events])
    report = {"events": len(events), "per_episode": per_ep}
    if len(events) >= 5:
        v_h, h_cam, r = huber_line(x, y)
        boot = []
        rng = np.random.default_rng(0)
        eps = sorted({e["episode"] for e in events})
        for _ in range(500):  # resample episodes, not frames: frames of one segment are not independent
            pick = rng.choice(eps, len(eps))
            idx = np.concatenate([[j for j, e in enumerate(events) if e["episode"] == p] for p in pick]).astype(int)
            if len(idx) >= 5:
                boot.append(huber_line(x[idx], y[idx])[:2])
        boot = np.array(boot)
        report |= {"horizon_row": round(v_h, 1), "camera_height_m": round(h_cam, 4),
                   "horizon_row_ci90": np.percentile(boot[:, 0], [5, 95]).round(1).tolist(),
                   "camera_height_m_ci90": np.percentile(boot[:, 1], [5, 95]).round(4).tolist(),
                   "residual_px_mad": round(float(1.4826 * np.median(np.abs(r))), 1),
                   "released_d_median": round(float(np.median([e["released_d"] for e in events])), 4)}
    report["event_rows"] = events
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "event_rows"}))


if __name__ == "__main__":
    main()
