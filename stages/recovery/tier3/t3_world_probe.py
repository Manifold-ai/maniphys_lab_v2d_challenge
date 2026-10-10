"""How far is our Tier 3 frame (the exo camera's OpenCV frame) from the released Track 2 world, and how much of that does
a floor-only correction remove? Diagnostic; nothing in the Tier 3 data is derived from the references read here.

The correction under test (Tier 3 inputs only): rotate about the camera origin by the angle between our floor normal and
the released ground_plane normal, then scale about the camera origin by released plane offset / our plane offset (the
camera height ratio). Object: position rotated and scaled, orientation rotated, mesh size kept. Human: root (Hips)
position rotated and scaled, the body rotated rigidly about it, body size kept. Our floor comes from either
  - moge:  MoGe's camera-frame plane from moge_ground_probe.py, or
  - feet:  a plane through the lowest sole vertices of our own SOMA body on frames where that foot is still.
Variants per episode: W = I (as assembled today), tilt only, tilt + scale (both floor sources), and the reference upper
bound: a similarity world <- camera fitted to the human joints (against Tier 2's perturbed human) and applied to the
object, which that fit never saw.

Object reference: rxzhou's Tier 2 v5.4 denoised object poses (runs/recovery/tier2_v54, OpenCV world, wxyz); human
reference: the released Tier 2 human (perturbed; no denoised human exists).

    python t3_world_probe.py <tier3 root> <dir with tier2 episode_*.npz> <tier2_v54 dir> <soma assets> <out .json>
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.spatial.transform import Rotation

F = np.diag([1.0, -1.0, -1.0])
CHUNK = 64
STILL_M = 0.005  # sole vertex moves less than this between frames: foot planted
RANSAC_M = 0.02
HUMAN_KEYS = ("poses", "transl", "identity_coeffs", "scale_params", "bone_length_flexibles")


def soma_cv(sp: dict, layer) -> tuple[np.ndarray, np.ndarray]:
    """Joints and vertices in the OpenCV frame, the downstream's way (frame-0 identity and scale)."""
    n = len(sp["poses"])
    ident = torch.tensor(np.repeat(np.asarray(sp["identity_coeffs"]).reshape(n, -1)[:1], n, 0), dtype=torch.float32)
    scale = torch.tensor(np.repeat(np.asarray(sp["scale_params"]).reshape(n, -1)[:1], n, 0), dtype=torch.float32)
    joints, verts = [], []
    for s in range(0, n, CHUNK):
        sl = slice(s, min(n, s + CHUNK))
        with torch.no_grad():
            got = layer(torch.tensor(np.asarray(sp["poses"][sl]).reshape(-1, 77, 3), dtype=torch.float32), ident[sl], scale_params=scale[sl],
                        transl=torch.tensor(np.asarray(sp["transl"][sl]), dtype=torch.float32), apply_correctives=False,
                        kwargs={"bone_length_flexibles": torch.tensor(np.asarray(sp["bone_length_flexibles"][sl]), dtype=torch.float32)})
        joints.append(got["joints"].numpy())
        verts.append(got["vertices"].numpy())
    return np.concatenate(joints).astype(np.float64) @ F, np.concatenate(verts).astype(np.float64) @ F


def plane_up(n: np.ndarray, d: float) -> tuple[np.ndarray, float]:
    """Normalise n.x + d = 0 so that d > 0 (the origin, i.e. the camera, is on the normal's side: n points up)."""
    k = np.linalg.norm(n)
    n, d = n / k, d / k
    return (n, d) if d > 0 else (-n, -d)


def feet_plane(verts: np.ndarray, sole: dict, up: np.ndarray) -> tuple[np.ndarray, float, int]:
    pts = []
    for idx in sole.values():
        v = verts[:, idx]  # (n, k, 3)
        low = v[np.arange(len(v)), np.argmax(v @ -up, axis=1)]  # lowest along up, per frame
        still = np.r_[False, np.linalg.norm(np.diff(low, axis=0), axis=1) < STILL_M]
        pts.append(low[still])
    pts = np.concatenate(pts)
    rng = np.random.default_rng(0)
    best, best_in = None, -1
    for _ in range(500):
        a, b, c = pts[rng.choice(len(pts), 3, replace=False)]
        n = np.cross(b - a, c - a)
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        inl = np.abs((pts - a) @ n) < RANSAC_M
        if inl.sum() > best_in:
            best, best_in = inl, int(inl.sum())
    p = pts[best]
    c = p.mean(0)
    n = np.linalg.svd(p - c)[2][-1]
    n, d = plane_up(n, -n @ c)
    return n, d, best_in


def umeyama(a: np.ndarray, b: np.ndarray, with_scale: bool = True) -> tuple[float, np.ndarray, np.ndarray]:
    ca, cb = a.mean(0), b.mean(0)
    u, dd, vt = np.linalg.svd((a - ca).T @ (b - cb) / len(a))
    sgn = np.diag([1.0, 1.0, np.sign(np.linalg.det(vt.T @ u.T))])
    r = vt.T @ sgn @ u.T
    s = float(np.trace(np.diag(dd) @ sgn) / ((a - ca) ** 2).sum(1).mean()) if with_scale else 1.0
    return s, r, cb - s * r @ ca


def yaw_fit(a: np.ndarray, b: np.ndarray, up: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rotation about up and translation (rigid, a already tilted) best mapping a onto b."""
    e1 = np.cross(up, [1.0, 0.0, 0.0] if abs(up[0]) < 0.9 else [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    basis = np.stack([e1, e2])
    ah, bh = a @ basis.T, b @ basis.T
    ca, cb = ah.mean(0), bh.mean(0)
    m = (ah - ca).T @ (bh - cb)
    th = np.arctan2(m[0, 1] - m[1, 0], m[0, 0] + m[1, 1])
    r = Rotation.from_rotvec(th * up).as_matrix()
    return r, b.mean(0) - a.mean(0) @ r.T


def rot_deg(ra: np.ndarray, rb: np.ndarray) -> np.ndarray:
    return np.degrees(np.linalg.norm(Rotation.from_matrix(ra.transpose(0, 2, 1) @ rb).as_rotvec(), axis=1))


def angle(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))


def main() -> None:
    from soma import SOMALayer
    from soma.units import Unit

    root, t2dir, v54, assets, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    w = np.asarray(layer.skinning_weights, np.float64)
    wn = [str(x) for x in layer._public_joint_names]
    sole = {side: np.nonzero(w[:, [wn.index(f"{side}Foot"), wn.index(f"{side}ToeBase"), wn.index(f"{side}ToeEnd")]].sum(1) >= 0.5)[0]
            for side in ("Left", "Right")}
    metas = [json.loads(line) for line in (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines() if line.strip()]
    moge = {r["episode_index"]: r for r in json.loads((root / "runs/moge_ground/moge_ground_probe.json").read_text())}
    rows = []
    for m in metas:
        ep = m["episode_index"]
        name = f"ep{ep:02d}_{m['object']}"
        conv = root / "runs/convert" / name
        if not (conv / "soma_params.npz").exists():
            rows.append({"episode": name, "skipped": "no reconstruction"})
            print(json.dumps(rows[-1]), flush=True)
            continue
        ours = dict(np.load(conv / "soma_params.npz", allow_pickle=True))
        t2 = dict(np.load(t2dir / f"episode_{ep:06d}.npz"))
        ref = np.load(v54 / f"episode_{ep:06d}.npz", allow_pickle=True)
        cam = np.load(conv / "object_cam.npz")["T_cam_glb"]
        n = min(len(ours["poses"]), len(t2["poses"]), len(cam), len(ref["object_pose"]))
        ja, va = soma_cv({k: ours[k][:n] for k in HUMAN_KEYS}, layer)
        jb, _ = soma_cv({k: t2[k][:n] for k in HUMAN_KEYS}, layer)
        # our pose on Tier 2's body (identity / scale / bone lengths are not perturbed in Tier 2)
        jc, _ = soma_cv({**{k: ours[k][:n] for k in ("poses", "transl")},
                         **{k: t2[k][:n] for k in ("identity_coeffs", "scale_params", "bone_length_flexibles")}}, layer)
        vis = ref["visible"][:n].astype(bool)
        ot, orr = cam[:n, :3, 3][vis], cam[:n, :3, :3][vis]
        q = ref["object_pose"][:n][vis]
        rt, rr = q[:, :3], Rotation.from_quat(np.c_[q[:, 4:7], q[:, 3:4]]).as_matrix()
        gp = json.loads((root / "input" / m["ground_plane"]).read_text())["plane"]
        n_w, d_w = plane_up(np.asarray(gp[:3], np.float64), float(gp[3]))

        def score(rot: np.ndarray, s: float, t: np.ndarray | None = None, joints: np.ndarray | None = None) -> dict:
            """Rotate about the camera origin, scale positions; t only for the similarity reference."""
            t = np.zeros(3) if t is None else t
            o = s * ot @ rot.T + t
            jj = ja if joints is None else joints
            pelvis = jj[:, 0]
            jt = np.einsum("ij,nkj->nki", rot, jj - pelvis[:, None]) + (s * pelvis @ rot.T + t)[:, None]
            if t.any():  # similarity reference: scale the whole body, as fitted
                jt = s * jj @ rot.T + t
            e = np.linalg.norm(o - rt, axis=1)
            return {"obj_cm_p50": round(float(np.median(e)) * 100, 1), "obj_cm_p90": round(float(np.percentile(e, 90)) * 100, 1),
                    "obj_rot_deg_p50": round(float(np.median(rot_deg(np.einsum("ij,njk->nik", rot, orr), rr))), 1),
                    "human_joint_cm_p50": round(float(np.median(np.linalg.norm(jt - jb, axis=-1))) * 100, 1)}

        row = {"episode": name, "frames": int(n), "object_frames": int(vis.sum()), "w_eq_i": score(np.eye(3), 1.0)}
        floors = {}
        g = moge.get(ep)
        if g:
            floors["moge"] = plane_up(np.asarray(g["n_moge"], np.float64), float(g["d_moge_m"]))
        nf, df, inl = feet_plane(va, sole, floors["moge"][0] if "moge" in floors else np.array([0.0, -1.0, 0.0]))
        floors["feet"] = (nf, df)
        row["feet_plane_points"] = inl
        for src, (nc, dc) in floors.items():
            rot = Rotation.align_vectors([n_w], [nc])[0].as_matrix()
            row[f"{src}_floor"] = {"tilt_deg": round(angle(nc, n_w), 2), "height_ratio": round(d_w / dc, 4)}
            row[f"{src}_tilt"] = score(rot, 1.0)
            row[f"{src}_tilt_scale"] = score(rot, d_w / dc)
        s, r, t = umeyama(ja.reshape(-1, 3), jb.reshape(-1, 3))
        row["human_fit_reference"] = {"scale": round(s, 4), "rotation_deg": round(float(np.degrees(np.linalg.norm(Rotation.from_matrix(r).as_rotvec()))), 2),
                                      "translation_m": [round(float(x), 3) for x in t], **score(r, s, t)}

        def fit_row(r: np.ndarray, s: float, t: np.ndarray, joints: np.ndarray, **extra) -> dict:
            out = {"scale": round(s, 4), **extra, **score(r, s, t, joints)}
            if "moge" in floors:  # independent check: our MoGe floor mapped into the world vs the released plane
                nc, dc = floors["moge"]
                nm = r @ nc
                out["floor_tilt_deg"] = round(angle(nm, n_w), 2)
                out["floor_height_cm"] = round(float(d_w - (s * dc - nm @ t)) * 100, 1)  # + : our mapped floor sits above the released one
            return out

        for tag, jj in (("ours", ja), ("t2id", jc)):
            a, b = jj.reshape(-1, 3), jb.reshape(-1, 3)
            s7, r7, t7 = umeyama(a, b)
            row[f"{tag}_sim7"] = fit_row(r7, s7, t7, jj)
            _, r6, t6 = umeyama(a, b, with_scale=False)
            row[f"{tag}_rigid6"] = fit_row(r6, 1.0, t6, jj)
        k = min(30, n)
        _, re, te = umeyama(jc[:k].reshape(-1, 3), jb[:k].reshape(-1, 3), with_scale=False)
        row["t2id_rigid6_early30"] = fit_row(re, 1.0, te, jc)
        if "moge" in floors:
            nc, dc = floors["moge"]
            r0 = Rotation.align_vectors([n_w], [nc])[0].as_matrix()
            a, b = jc.reshape(-1, 3) @ r0.T, jb.reshape(-1, 3)
            ry, ty = yaw_fit(a, b, n_w)
            row["floor_tilt_human"] = fit_row(ry @ r0, 1.0, ty, jc)  # yaw + full translation from the human
            th = ty - n_w * (n_w @ ty) + n_w * (dc - d_w)  # height from the two floors instead
            row["floor_full_human"] = fit_row(ry @ r0, 1.0, th, jc)
        rows.append(row)
        print(json.dumps(row), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
