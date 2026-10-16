"""Register a corner exo camera onto the main camera's world from its own sightings of the main and second cameras
(Tier 3 inputs only).

The capture area has four tripod cameras at its corners: main (A), second (C, opposite A, registered by
t3_mutual_multi.py) and two side cameras. ep21's camera is one side camera; its plate shows the opposite side camera
straight ahead and A and C near its left and right edges. A and C are known in the main camera's plane coords, so the
pair of ep21's tripod feet whose separation best matches |A - C| (the sighted, straight-ahead tripod excluded) gives
the rigid floor-plane motion with two points: yaw and translation. Which foot is A follows from where the camera
stands: counter-clockwise from above, main -> this camera -> second puts A on its left (--left A); the mirrored
assignment (--left C) is reported alongside, since the four-corner layout is close to symmetric about its centre.

Tripod feet: bottom-centre of each Grounding DINO 'tripod' box on the floor (t3_gdino_cpu.py on the people-free plate
from t3_walls.py plates, plus on 500-px left and right edge crops of it, where the edge-cut A and C are found).
Convention as t3_convert_ep.py _camera_register: p_main = Rot(yaw) p + t in the plane basis named in the spec.

    python t3_corner_register.py <tier3 root> <floor_fit.json> <det dir> <crop det dir> <episode> <group> \
        --left=A|C [camera_register.json] [conv=<dir>] [base=<camera_register.json holding the second camera>]
conv= names the convert dir whose focal step holds the intrinsics (default convert); base= the register spec C is read
from (default runs/floor/camera_register.json). A floor fit with shift_m is met as in t3_mutual_multi.py (10-17).
pair=<json with pair_boxes> keeps the two tripod boxes of an earlier run (matched on x0 and y1 within 2 px) instead of the
pair whose separation best matches |A - C|.
"""
import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import sys
from pathlib import Path

import numpy as np

CROP_W = 500
DUP_M = 0.3


def rot(a: float) -> np.ndarray:
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith(("--left=", "conv=", "base=", "pair="))]
    pair_file = next((Path(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("pair=")), None)
    left = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--left=")), None)
    conv = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("conv=")), "convert")
    base = next((Path(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("base=")), None)
    if left not in ("A", "C") or len(args) < 6:
        raise SystemExit(__doc__)
    root, fit_path, det_dir, crop_dir, ep, group = Path(args[0]), Path(args[1]), Path(args[2]), Path(args[3]), args[4], int(args[5])
    reg_path = Path(args[6]) if len(args) > 6 else None
    meta = {f"ep{m['episode_index']:02d}_{m['object']}": m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    fit = json.loads(fit_path.read_text())["episodes"][ep]
    reg_all = json.loads((base or root / "runs/floor/camera_register.json").read_text())
    second = reg_all["groups"]["1"]
    A, C = np.zeros(2), np.asarray(second["t_m"], float)

    gp = np.asarray(t3_inputs.ground_plane(root, meta[ep]), float)
    n, d = gp[:3] / np.linalg.norm(gp[:3]), gp[3] / np.linalg.norm(gp[:3])
    if d < 0:
        n, d = -n, -d
    u = np.array([1.0, 0, 0]) - n[0] * n
    u /= np.linalg.norm(u)
    v, o = np.cross(n, u), -d * n
    R, s, sh = np.asarray(fit["rotation"]), float(fit["scale"]), float(fit.get("shift_m", 0.0))
    K = np.asarray(np.load(root / "runs" / conv / ep / "object_cam_focal.npz")["intrinsics"], float).reshape(3, 3)

    def on_floor(px):
        ray = s * (R @ (np.linalg.inv(K) @ np.array([px[0], px[1], 1.0])))
        X = (-(d + sh) / (n @ ray)) * ray + sh * n
        return np.array([(X - o) @ u, (X - o) @ v])

    dets = json.loads((det_dir / f"det_plate_{ep}.json").read_text())
    # image width from CARI4D's own intrinsics, whose principal point is the image centre (the focal step's K need not
    # be: GB's cx 701.8 would put the right crop 132 px off)
    width = int(round(2 * float(np.load(root / "runs" / conv / ep / "object_cam.npz")["intrinsics"].reshape(3, 3)[0, 2])))
    boxes = [x["box"] for x in dets if "tripod" in x["label"]]
    for side, off in (("L", 0), ("R", width - CROP_W)):
        f = crop_dir / f"det_{side}_{ep}.json"
        if f.exists():
            boxes += [{k: (b + off if k in ("x0", "x1") else b) for k, b in x["box"].items()} for x in json.loads(f.read_text()) if "tripod" in x["label"]]
    feet, feet_box = [], []
    for b in boxes:
        p = on_floor(((b["x0"] + b["x1"]) / 2, b["y1"]))
        if all(np.linalg.norm(p - q) > DUP_M for q in feet):
            feet.append(p)
            feet_box.append({k: round(float(x)) for k, x in b.items()})
    cam = max((x for x in dets if x["label"].strip() == "camera"), key=lambda x: x["confidence"])
    cx = (cam["box"]["x0"] + cam["box"]["x1"]) / 2
    sighted = on_floor((cx, max(b["y1"] for b in boxes if b["x0"] - 5 <= cx <= b["x1"] + 5)))
    others_idx = [k for k, p in enumerate(feet) if np.linalg.norm(p - sighted) > DUP_M]
    others = [feet[k] for k in others_idx]
    ac = float(np.linalg.norm(C - A))
    pairs = sorted(((abs(float(np.linalg.norm(p - q)) - ac), i, j) for i, p in enumerate(others) for j, q in enumerate(others) if i < j))
    if not pairs:
        raise SystemExit(f"{ep}: fewer than two tripods besides the sighted one")
    _, i, j = pairs[0]
    if pair_file is not None:  # keep a pairing decided before (10-17: the user's 10-12 A/C pair, re-solved under new intrinsics)
        want = json.loads(pair_file.read_text())["pair_boxes"]
        hit = [k for k, oi in enumerate(others_idx) if any(abs(feet_box[oi]["x0"] - w["x0"]) <= 2 and abs(feet_box[oi]["y1"] - w["y1"]) <= 2 for w in want)]
        if len(hit) != 2:
            raise SystemExit(f"{ep}: the given pair boxes match {len(hit)} feet, want 2")
        i, j = hit
    pl, pr = sorted((others[i], others[j]), key=lambda p: np.arctan2(p[1], p[0]), reverse=True)  # larger bearing = further left

    def solve(left_is_a: bool):
        a, c = (A, C) if left_is_a else (C, A)
        phi = np.arctan2(*(c - a)[::-1]) - np.arctan2(*(pr - pl)[::-1])
        t = ((a + c) - rot(phi) @ (pl + pr)) / 2
        return {"left": "A" if left_is_a else "C", "yaw_deg": round(float(np.degrees(phi)) % 360, 2), "t_m": t.round(4).tolist(),
                "pair_residual_m": round(float(np.linalg.norm(rot(phi) @ pl + t - a)), 3),
                "sighted_lands_m": (rot(phi) @ sighted + t).round(3).tolist(),
                "others_land_m": [(rot(phi) @ p + t).round(3).tolist() for p in others]}

    chosen, mirrored = solve(left == "A"), solve(left != "A")
    res = {"episode": ep, "group": group, "feet_m": [p.round(3).tolist() for p in feet], "sighted_m": sighted.round(3).tolist(),
           "pair_boxes": [feet_box[others_idx[i]], feet_box[others_idx[j]]],
           "pair_m": [pl.round(3).tolist(), pr.round(3).tolist()], "pair_separation_m": round(float(np.linalg.norm(pr - pl)), 3),
           "ac_m": round(ac, 3), "chosen": chosen, "mirrored": mirrored}
    print(json.dumps(res))
    if reg_path is not None:
        spec = json.loads(reg_path.read_text())
        spec["groups"][str(group)] = {"to_group": 0, "yaw_deg": chosen["yaw_deg"], "t_m": chosen["t_m"], "plane": second["plane"],
                                      "how": f"t3_corner_register.py: side corner camera; two-point fit of its tripod sightings of the main "
                                             f"and second cameras (left = {chosen['left']}), {ep}",
                                      "pair_separation_m": res["pair_separation_m"], "ac_m": res["ac_m"],
                                      "sighted_lands_m": chosen["sighted_lands_m"], "mirrored": {k: mirrored[k] for k in ("yaw_deg", "t_m")}}
        reg_path.write_text(json.dumps(spec, indent=1))
        print("wrote", reg_path)


if __name__ == "__main__":
    main()
