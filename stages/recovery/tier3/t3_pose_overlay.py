"""Orientation review sheets: each version's object pose rendered over the exo video frame, coloured by body coordinates.

Silhouette IoU (t3_align_check.py) cannot see a turn about an object's long axis: the outline barely changes while the
spray bottle's nozzle points elsewhere. Here each face is painted with the colour of its body-frame position (x, y, z
of the mesh bounding box -> R, G, B), so the nozzle, a mug's handle or a can's spout keeps its own colour; a panel
whose coloured feature sits away from the same feature in the video has the wrong orientation. Faces are drawn far to
near (painter's order), blended half over the frame, cropped around the object mask.

Frames: by default the N frames where the versions disagree most (largest distance any surface point lands between the
first version's pose and another's, about the centre of mass removed or not), plus the first and the last frame.

    python t3_pose_overlay.py <tier3 root> <selection json> <out dir> <version>... only=<ep>[,<ep>] [frames=<f>,<f>] [n=6]
        [tex=1 [tint=<B>,<G>,<R>]] [alpha=<0..1>] [cell=<px>]
tex=1 paints the faces with the mesh's own texture instead (lid, handle and print look as in the video; added 10-16 when the
coordinate colours left it unclear which end of ep03's mug is the lid); tint keeps the texture's pattern but recolours its
brightness, stretched to its own range, in one colour (10-21: ep03's grey texture vanished over the grey mug in the video);
alpha is the render's weight over the frame (default 0.5), cell the panel size.
Writes <out dir>/epNN_<object>.png (rows: frames; columns: the video, then one panel per version). CPU only.
"""

import json
import sys
from pathlib import Path

import cv2
import h5py
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_align_check import MAX_FACES, WORK, similarity, world_pose  # noqa: E402

PAD = 0.35  # of the crop size, around the union of the mask and the panels' silhouettes
CELL = 360  # px, each panel


def frame_at(video: Path, f: int):
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ok, img = cap.read()
    cap.release()
    return img if ok else None


def render(img, V, F, col, Rw, pw, s, rot, t, K, alpha=0.5):
    """Faces painted far to near over a copy of img; returns (image, silhouette mask) or None behind the camera."""
    R_c = rot.T @ Rw
    p_c = rot.T @ (pw - t) / s
    X = V @ R_c.T + p_c
    if (X[:, 2] <= 0.05).any():
        return None
    uv = X @ K.T
    uv = uv[:, :2] / uv[:, 2:]
    depth = X[F].mean(1)[:, 2]
    layer = img.copy()
    sil = np.zeros(img.shape[:2], np.uint8)
    for i in np.argsort(-depth):
        poly = np.round(uv[F[i]]).astype(np.int32)
        cv2.fillPoly(layer, [poly], col[i].tolist())
        cv2.fillPoly(sil, [poly], 1)
    out = img.copy()
    m = sil.astype(bool)
    out[m] = ((1 - alpha) * img[m] + alpha * layer[m]).astype(np.uint8)
    return out, sil


def main() -> None:
    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, out, versions = Path(args[0]), Path(args[1]), Path(args[2]), args[3:]
    only = {int(x) for x in kv["only"].split(",")}
    n_pick = int(kv.get("n", 6))
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    for r in json.loads(sel.read_text()):
        ep, name = r["episode_index"], r["episode"]
        if ep not in only:
            continue
        conv = r["convert"]
        s, rot, t, K, _ = similarity(root / "runs" / conv / name)
        mesh = trimesh.load(root / "input" / metas[ep]["mesh"], force="mesh")
        tex = None
        if kv.get("tex") == "1":  # texture colours per face of the full mesh, carried to the decimated faces by nearest centre
            cv = mesh.visual.to_color()
            cv.mesh = mesh  # to_color() leaves it unset, and face_colors are derived from the vertex colours through it
            full_fc = np.asarray(cv.face_colors)[:, :3].astype(np.uint8)
            full_c = np.asarray(mesh.triangles_center)
        if len(mesh.faces) > MAX_FACES:
            mesh = mesh.simplify_quadric_decimation(face_count=MAX_FACES)
        V, F = np.asarray(mesh.vertices), np.asarray(mesh.faces)
        lo, hi = V.min(0), V.max(0)
        c = (V[F].mean(1) - lo) / np.maximum(hi - lo, 1e-9)
        col = (40 + 215 * c[:, ::-1]).astype(np.uint8)  # BGR from body z, y, x
        if kv.get("tex") == "1":
            from scipy.spatial import cKDTree
            col = full_fc[cKDTree(full_c).query(V[F].mean(1))[1]][:, ::-1].copy()  # RGB -> BGR
            if "tint" in kv:  # the texture's brightness, stretched to its own range, in one colour
                lum = col.astype(float).mean(1)
                lum = (lum - lum.min()) / max(np.ptp(lum), 1e-9)
                tint = np.array([float(x) for x in kv["tint"].split(",")])
                col = (30 + lum[:, None] * (tint - 30)).clip(0, 255).astype(np.uint8)
        poses = {v: world_pose(root, v, ep) for v in versions}
        n = min(len(p) for p in poses.values())
        if "frames" in kv:
            frames = [int(x) for x in kv["frames"].split(",")]
        else:
            pts = V[np.random.default_rng(0).choice(len(V), min(len(V), 500), replace=False)]
            P = {v: np.einsum("tij,kj->tki", p[:n, :3, :3], pts) + p[:n, None, :3, 3] for v, p in poses.items()}
            base = P[versions[0]]
            dis = np.max([np.linalg.norm(P[v] - base, axis=2).max(1) for v in versions[1:]], 0) if len(versions) > 1 else np.zeros(n)
            order = [int(f) for f in np.argsort(-dis)]
            frames = []
            for f in order:  # spread the picks: at least 15 frames apart
                if all(abs(f - g) >= 15 for g in frames):
                    frames.append(f)
                if len(frames) == n_pick:
                    break
            frames = sorted(set(frames) | {0, n - 1})
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]
        video = root / "runs" / WORK[conv] / name / f"episode_{ep:06d}.0.color.mp4"
        rows = []
        for f in frames:
            img = frame_at(video, f)
            if img is None:
                continue
            key = f"{f:06d}-k0.obj_rend_mask.png"
            om = (H[key][()] > 0) if key in H else np.zeros(img.shape[:2], bool)
            if om.shape != img.shape[:2]:
                om = cv2.resize(om.astype(np.uint8), (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
            panels, box = [], om.copy()
            for v in versions:
                pw = poses[v][f]
                res = render(img, V, F, col, pw[:3, :3], pw[:3, 3], s, rot, t, K, float(kv.get("alpha", 0.5)))
                panels.append(res[0] if res else np.zeros_like(img))
                if res:
                    box |= res[1].astype(bool)
            ys, xs = np.nonzero(box)
            if not len(xs):
                continue
            size = max(np.ptp(xs), np.ptp(ys)) * (1 + 2 * PAD) + 20
            cx, cy = xs.mean(), ys.mean()
            x0, y0 = int(max(0, cx - size / 2)), int(max(0, cy - size / 2))
            x1, y1 = int(min(img.shape[1], cx + size / 2)), int(min(img.shape[0], cy + size / 2))
            raw = img.copy()
            cnts, _ = cv2.findContours(om.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(raw, cnts, -1, (0, 255, 255), 1)
            cells = []
            for label, im in [(f"video f{f}", raw)] + list(zip(versions, panels)):
                cell = cv2.resize(im[y0:y1, x0:x1], (int(kv.get("cell", CELL)),) * 2)
                cv2.putText(cell, label.replace("tier3_cari4d_f830_", ""), (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cells.append(cell)
            rows.append(np.hstack(cells))
        if rows:
            dst = out / f"ep{ep:02d}_{metas[ep]['object']}{'_tex' if kv.get('tex') == '1' else ''}.png"
            cv2.imwrite(str(dst), np.vstack(rows))
            print(dst, "frames", frames, flush=True)


if __name__ == "__main__":
    main()
