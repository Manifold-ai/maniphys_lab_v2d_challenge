"""Per-episode choice of the selector's ROT_DEG (11-04, plan ~/v2d/synth-hoi/plan-tier3-rot5-submission-2026-11-04.md):
run t3_fp_select.py offline (--dry) at ROT_DEG 10 (the delivered value) and 5, every other parameter as delivered;
on the frames where the two selections differ (symmetry-aware rotation > 24 deg or translation > 5 cm), compare the
object silhouette of each against the SAM2 object mask, person pixels removed (t3_object_check.rasterise / visible_iou /
MIN_VISIBLE_PX, the measure of t3_sel_iou.py's "vis", the judge registered for the 10-20 BETA A/B, here at the FP layer).
5 is used when its mean IoU over the changed frames with a usable mask exceeds 10's by more than MIN_GAIN (0.02, the
frame-pair noise line of the 11-03 change audit); otherwise (no changed frame, no usable mask, within the line) 10. Tier 3 inputs only: video masks, FP candidates, the official mesh.
Writes the decision and its evidence to <out json> and prints the chosen ROT_DEG as the last line.
usage: t3_rot_rule.py <cari4d episode dir> <candidates.npz> <official mesh> <sam2 masks dir> <out json>
       (v2d_cari4d image; the selection itself is then written by t3_fp_select.py --rot-deg=<printed value>)"""
import json
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "gate"))
import trimesh  # noqa: E402
from t3_fp_select import sym_angle_deg  # noqa: E402
from t3_object_check import MIN_VISIBLE_PX, load_mesh, rasterise, visible_iou  # noqa: E402
from t3_symmetry import Shape, symmetries  # noqa: E402

BASE, CAND = 10.0, 5.0
ROT_CH, TR_CH = 24.0, 0.05
MIN_GAIN = 0.02


def select(ep_dir, cand, mesh, rot, out):
    r = subprocess.run([sys.executable, str(HERE / "t3_fp_select.py"), str(ep_dir), str(cand), str(mesh), "--dry",
                        f"--rot-deg={rot:g}", f"--poses-out={out}"], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"t3_fp_select.py --rot-deg={rot:g} failed: {r.stderr[-2000:]}")
    z = np.load(out)
    return z["poses_cam"], z["s2a"]


def main():
    ep_dir, cand, meshp, masks, dst = map(Path, sys.argv[1:6])
    with tempfile.TemporaryDirectory() as tmp:
        Cb, s2a = select(ep_dir, cand, meshp, BASE, Path(tmp) / "base.npz")
        Cc, s2a_c = select(ep_dir, cand, meshp, CAND, Path(tmp) / "cand.npz")
    assert np.array_equal(s2a, s2a_c)
    (pkl,) = sorted((ep_dir / "foundationpose").glob("episode_*.pkl"))
    ex = json.loads((ep_dir / "export" / pkl.stem / "wild_export.json").read_text())
    assert np.allclose(np.asarray(ex["source_object_mesh_to_aligned_transform"], np.float64), s2a), "s2a differs from the export"
    mesh = trimesh.load(meshp, force="mesh"); body = mesh if mesh.is_watertight else mesh.convex_hull
    G, axis = symmetries(Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)
    V, F = load_mesh(meshp)
    Mb, Mc = Cb @ s2a, Cc @ s2a
    n = len(Mb)
    drot = np.array([sym_angle_deg(Mb[f:f + 1, :3, :3], Mc[f:f + 1, :3, :3], G, axis)[0, 0] for f in range(n)])
    changed = (drot > ROT_CH) | (np.linalg.norm(Mb[:, :3, 3] - Mc[:, :3, 3], axis=1) > TR_CH)
    it = ex["intrinsics"]
    K = np.asarray(it, np.float64).reshape(3, 3) if np.size(it) == 9 else \
        np.array([[it["fx"], 0, it["cx"]], [0, it["fy"], it["cy"]], [0, 0, 1.0]])
    pairs, Ks = [], None
    for f in np.flatnonzero(changed):
        om = masks / "1" / f"{f:06d}.png"
        if not om.exists():
            continue
        obj = np.asarray(Image.open(om).convert("L")) > 0
        h, w = obj.shape
        if Ks is None:
            Ks = K.copy(); Ks[0] *= w / float(ex["width"]); Ks[1] *= h / float(ex["height"])
        pm = masks / "0" / f"{f:06d}.png"
        person = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros_like(obj)
        mv = obj & ~person
        io = []
        for M in (Mb[f], Mc[f]):
            rv = rasterise(V @ M[:3, :3].T + M[:3, 3], F, Ks, h, w) & ~person
            io.append(None if rv.sum() < MIN_VISIBLE_PX or mv.sum() < MIN_VISIBLE_PX else float(visible_iou(rv, mv)))
        if None not in io:
            pairs.append(io)
    a = np.array(pairs).reshape(-1, 2)
    mean_b, mean_c = (float(a[:, 0].mean()), float(a[:, 1].mean())) if len(a) else (None, None)
    rot = CAND if len(a) and mean_c - mean_b > MIN_GAIN else BASE
    dst.write_text(json.dumps({"rot_deg": rot, "base": BASE, "candidate": CAND, "min_gain": MIN_GAIN, "frames": n, "changed": int(changed.sum()),
                               "n_iou": int(len(a)), "iou_mean_base": mean_b, "iou_mean_candidate": mean_c}, indent=1))
    print(f"{rot:g}")


if __name__ == "__main__":
    main()
