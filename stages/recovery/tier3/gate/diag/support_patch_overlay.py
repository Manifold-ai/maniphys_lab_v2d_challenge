"""Draw support patches over the exo video, to see whether a patch stays on the table (10-16, review only).

Patches (t3_support.py: plane coordinates of the main camera's world, height above the episode's floor) are lifted to
3-D on the episode's ground plane and projected with the world step's similarity and intrinsics, as t3_align_check.py.
Old patch yellow, new patch cyan, on the frames given.

    python support_patch_overlay.py <tier3 root> <selection json> <old support dir> <new support dir> <out dir> <ep>:<f>,<f> ...
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import t3_inputs  # noqa: E402
from t3_align_check import WORK, similarity  # noqa: E402
from t3_support import basis, main_basis  # noqa: E402


def main():
    root, sel, old, new, out = (Path(a) for a in sys.argv[1:6])
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    conv = {r["episode_index"]: (r["episode"], r["convert"]) for r in json.loads(sel.read_text())}
    o_m, u_m, v_m = main_basis(root)
    for arg in sys.argv[6:]:
        ep, frames = int(arg.split(":")[0]), [int(x) for x in arg.split(":")[1].split(",")]
        name, cv = conv[ep]
        s, rot, t, K, _ = similarity(root / "runs" / cv / name)
        n_e, d_e, _, _, _ = basis(t3_inputs.ground_plane(root, metas[ep]))
        polys = {}
        for tag, d in (("old", old), ("new", new)):
            rec = json.loads((d / f"{name}.json").read_text())
            pl = []
            for sp in rec["supports"]:
                xy = np.asarray(sp["patch_xy_m"], float)
                P = o_m + xy[:, :1] * u_m + xy[:, 1:2] * v_m
                P = P - (P @ n_e + d_e)[:, None] * n_e + sp["height_m"] * n_e  # onto the floor, then up to the support
                X = (P - t) @ rot / s  # rot.T @ (P - t) / s, row-wise
                uv = X @ np.asarray(K, float).reshape(3, 3).T
                pl.append(np.round(uv[:, :2] / uv[:, 2:]).astype(np.int32))
            polys[tag] = pl
        video = root / "runs" / WORK[cv] / name / f"episode_{ep:06d}.0.color.mp4"
        cap = cv2.VideoCapture(str(video))
        for f in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, img = cap.read()
            if not ok:
                continue
            for tag, col in (("old", (0, 255, 255)), ("new", (255, 255, 0))):
                cv2.polylines(img, polys[tag], True, col, 3)
            cv2.putText(img, f"{name} f{f}  yellow: rests only (v2)  cyan: with sliding (v3)", (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.imwrite(str(out / f"{name}_f{f}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print(out / f"{name}_f{f}.jpg", flush=True)


if __name__ == "__main__":
    main()
