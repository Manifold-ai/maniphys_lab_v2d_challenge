"""Texture orientation choice for symmetric and near-symmetric objects on a delivered Tier 3 version, t3fix part B1
(Tier 3 inputs only: the exo video, the SAM2 masks, the mesh and the delivered layer).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 3, section 1 B1 and criterion G0.

Per episode in scope (it has a non-identity symmetry, a continuous axis or a near-symmetry axis):
  candidates  the non-identity symmetry rotations, STEP_DEG steps about the continuous axis and about the
              near-symmetry axis (t3_fix_units.candidates' turnNNN), each turned about the centre of mass;
  gate        on GATE_FRAMES evidence frames, the point-splat silhouette against t3_object_check.rasterise (IoU median);
  distinct    (a) on DISTINCT_FRAMES evidence frames, the NCC of the current render and each candidate's render on
              their common covered pixels (both variants); median >= DISTINCT_NCC marks the candidate "not distinct";
  scores      (b) every stride-th evidence frame: NCC of render and video frame on render & object mask & not person,
              variant i (no blur) and ii (sigma BLUR_SIGMA, the render blurred by normalised convolution); a pose
              with fewer than MIN_TEX_PX region pixels gets nan; the null pose "shift1" is the current render moved by 1 px;
  decisions   (c) one per segment between single-frame turns above JUMP_DEG (t3_tex.segments), on frames where every
              pose of the set has a score; fewer than MIN_EVIDENCE frames: refuse "evidence". Real set: current and the
              distinct candidates. Null set (d): current, shift1 and the candidates that are not distinct.
Nothing is written into the version.

    python t3_fix_tex.py <tier3 root> <selection json> <version> <out dir> [stride=3] [only=<ep>,..] [stage=gate|full]
Writes <out>/epNN.json (and epNN.npz, epNN_debug.png with stage=full); one json line per episode on stdout. CPU only.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "gate"), str(HERE.parents[2] / "libs" / "v2d_infra")]

GATE_FRAMES = 20
DISTINCT_FRAMES = 30
GATE_IOU = 0.95
N_MIN, N_MAX = 400_000, 3_000_000


def main() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import cv2
    import h5py
    import trimesh
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    from t3_align_check import WORK, similarity, world_pose
    from t3_fix_units import JUMP_DEG, MIN_EVIDENCE, STEP_DEG, about_com, candidates, principal, rot, turn_deg
    from t3_object_check import rasterise
    from t3_symmetry import SYM_M, Shape, symmetries
    from t3_tex import (BLUR_SIGMA, DISTINCT_NCC, MIN_TEX_PX, SPLAT_PER_PX, blur, decide_segment, ncc, segments, splat,
                        surface_samples, ycrcb)
    from t3_track_check import MIN_MASK_PX

    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, version, out = Path(args[0]), Path(args[1]), args[2], Path(args[3])
    stride, stage = int(kv.get("stride", 3)), kv.get("stage", "full")
    only = {int(x) for x in kv.get("only", "").split(",") if x}
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    for r in json.loads(sel.read_text()):
        ep, name, conv = r["episode_index"], r["episode"], r["convert"]
        if only and ep not in only:
            continue
        t0 = time.time()
        m = metas[ep]
        s, rot_, t, k, _ = similarity(root / "runs" / conv / name)
        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh", process=False)
        verts, faces = np.asarray(mesh.vertices, np.float64), np.asarray(mesh.faces, np.int64)
        body = mesh if mesh.is_watertight else mesh.convex_hull
        com_b = np.asarray(body.center_mass, np.float64)
        group, cont = symmetries(Shape(mesh, com_b), body.moment_inertia)
        moments, axes = principal(body.moment_inertia)
        cand = {f"sym_g{i}": np.asarray(g, np.float64) for i, g in enumerate(group) if i > 0}
        if cont is not None:
            cand.update({f"cont{d:03d}": rot(cont, d) for d in range(STEP_DEG, 360, STEP_DEG)})
        cand.update({x: g for x, g in candidates(moments, axes, Shape(mesh, com_b).shift, SYM_M, group, cont).items() if x.startswith("turn")})
        row = {"episode": name, "stage": stage, "symmetries": len(group), "continuous_axis": cont is not None, "candidates": sorted(cand)}
        if not cand:
            row["skip"] = "not-in-scope"
            (out / f"ep{ep:02d}.json").write_text(json.dumps(row, indent=1))
            print(json.dumps(row), flush=True)
            continue
        image = mesh.visual.material.baseColorTexture
        uv = np.asarray(mesh.visual.uv, np.float64)
        G = {"current": np.eye(4), **{x: about_com(g, com_b) for x, g in cand.items()}}
        Tw = world_pose(root, version, ep)
        n = len(Tw)
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]

        def masks(f):
            ok, pk = f"{f:06d}-k0.obj_rend_mask.png", f"{f:06d}-k0.person_mask.png"
            if ok not in H:
                return None, None
            obj = H[ok][()] > 0
            return obj, (H[pk][()] > 0 if pk in H else np.zeros_like(obj))

        ev = [f for f in range(0, n, stride) if (mk := masks(f))[0] is not None and (mk[0] & ~mk[1]).sum() >= MIN_MASK_PX]
        hh, ww = masks(ev[0])[0].shape if ev else (0, 0)
        max_px = max(int(masks(f)[0].sum()) for f in ev[:: max(1, len(ev) // 30)]) if ev else 0
        n_pts = int(np.clip(SPLAT_PER_PX * 2.5 * max_px, N_MIN, N_MAX))
        pts, col = surface_samples(verts, faces, uv, image, n_pts, seed=ep)
        rad = float(np.linalg.norm(verts - com_b, axis=1).max())

        def crop(T):
            """(x0, y0, x1, y1): the image box of the bounding sphere about the centre of mass, any turn about it."""
            c = rot_.T @ (T[:3, :3] @ com_b + T[:3, 3] - t) / s
            if c[2] <= 1e-3:
                return None
            r = rad / s / c[2] * k[0, 0] + 5
            u, v = c[0] / c[2] * k[0, 0] + k[0, 2], c[1] / c[2] * k[1, 1] + k[1, 2]
            x0, y0, x1, y1 = int(max(0, u - r)), int(max(0, v - r)), int(min(ww, u + r + 1)), int(min(hh, v + r + 1))
            return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

        def render(T, box):
            x0, y0, x1, y1 = box
            R_c = rot_.T @ T[:3, :3]
            p_c = rot_.T @ (T[:3, 3] - t) / s
            kk = k.copy()
            kk[0, 2] -= x0
            kk[1, 2] -= y0
            return splat(pts @ R_c.T + p_c, col, kk, y1 - y0, x1 - x0), (R_c, p_c, kk)

        # renderer gate
        gate = []
        for f in ev[:: max(1, len(ev) // GATE_FRAMES)][:GATE_FRAMES]:
            box = crop(Tw[f])
            if box is None:
                continue
            (img, cov), (R_c, p_c, kk) = render(Tw[f], box)
            ras = rasterise(verts @ R_c.T + p_c, faces, kk, box[3] - box[1], box[2] - box[0])
            gate.append(float((cov & ras).sum()) / max(1.0, float((cov | ras).sum())))
        row.update(points=n_pts, max_mask_px=max_px, evidence_frames=len(ev),
                   gate_iou_p50=round(float(np.median(gate)), 4) if gate else None)
        row["gate_ok"] = bool(gate) and row["gate_iou_p50"] >= GATE_IOU
        if stage == "gate" or not row["gate_ok"]:
            (out / f"ep{ep:02d}.json").write_text(json.dumps(row, indent=1))
            print(json.dumps(row), flush=True)
            continue

        def blur_render(img, cov):
            w = blur(cov.astype(np.float32))
            return blur(img * cov[..., None]) / np.maximum(w, 1e-6)[..., None]

        # (a) texture distinctness
        dist = {x: {"i": [], "ii": []} for x in cand}
        for f in ev[:: max(1, len(ev) // DISTINCT_FRAMES)][:DISTINCT_FRAMES]:
            box = crop(Tw[f])
            if box is None:
                continue
            (ic, cc), _ = render(Tw[f], box)
            for x in cand:
                (ix, cx), _ = render(Tw[f] @ G[x], box)
                reg = cc & cx
                if reg.sum() < MIN_TEX_PX:
                    continue
                dist[x]["i"].append(ncc(ycrcb(ic), ycrcb(ix), reg))
                dist[x]["ii"].append(ncc(ycrcb(blur_render(ic, cc)), ycrcb(blur_render(ix, cx)), reg))
        dmed = {x: {v: (round(float(np.nanmedian(d[v])), 4) if np.isfinite(d[v]).any() else None) for v in d} for x, d in dist.items()}
        distinct = {v: [x for x in cand if dmed[x][v] is not None and dmed[x][v] < DISTINCT_NCC] for v in ("i", "ii")}

        # (b) scores against the video
        poses = ["current", *cand, "shift1"]
        sc = {v: {x: np.full(n, np.nan) for x in poses} for v in ("i", "ii")}
        vis = []
        cap = cv2.VideoCapture(str(root / "input" / "videos" / f"episode_{ep:06d}.mp4"))
        want, f_now, debug_done = set(ev), 0, False
        while f_now < n:
            ok, frame = cap.read()
            if not ok:
                break
            f = f_now
            f_now += 1
            if f not in want:
                continue
            box = crop(Tw[f])
            if box is None:
                continue
            x0, y0, x1, y1 = box
            obj, person = masks(f)
            ev_mask = (obj & ~person)[y0:y1, x0:x1]
            vid = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)[y0:y1, x0:x1].astype(np.float32)
            vy, vyb = ycrcb(vid), ycrcb(blur(vid))
            rend = {}
            for x in poses:
                if x == "shift1":
                    img, cov = rend["current"]
                    rend[x] = (np.roll(img, 1, axis=1), np.roll(cov, 1, axis=1))
                else:
                    rend[x] = render(Tw[f] @ G[x], box)[0]
            for x, (img, cov) in rend.items():
                reg = cov & ev_mask
                if x == "current":
                    vis.append(int(reg.sum()))
                if reg.sum() < MIN_TEX_PX:
                    continue
                sc["i"][x][f] = ncc(ycrcb(img), vy, reg)
                sc["ii"][x][f] = ncc(ycrcb(blur_render(img, cov)), vyb, reg)
            if not debug_done:
                img = rend["current"][0]
                cv2.imwrite(str(out / f"ep{ep:02d}_debug.png"), cv2.cvtColor(np.concatenate([vid, img], axis=1).astype(np.uint8), cv2.COLOR_RGB2BGR))
                debug_done = True
        cap.release()

        # (c), (d) decisions per segment
        segs = segments(turn_deg(Tw[:, :3, :3]), JUMP_DEG)

        def decide(v, names):
            rows = []
            for a, b in segs:
                fr = [f for f in range(a, b) if all(np.isfinite(sc[v][x][f]) for x in names)]
                if len(fr) < MIN_EVIDENCE:
                    rows.append({"start": a, "end": b, "evidence": len(fr), "decision": "refuse", "reason": "evidence"})
                    continue
                res = decide_segment({x: [float(sc[v][x][f]) for f in fr] for x in names})
                rows.append({"start": a, "end": b, "evidence": len(fr), **res})
            return rows

        dec = {v: {"real": decide(v, ["current", *distinct[v]]) if distinct[v] else [],
                   "null": decide(v, ["current", "shift1", *[x for x in cand if x not in distinct[v]]])} for v in ("i", "ii")}
        np.savez_compressed(out / f"ep{ep:02d}.npz", **{f"{v}__{x}": a for v, d in sc.items() for x, a in d.items()})
        row.update(distinct_ncc=dmed, distinct=distinct, visible_px_p50=int(np.median(vis)) if vis else 0,
                   scored={v: int(np.isfinite(sc[v]["current"]).sum()) for v in sc}, segments=len(segs),
                   accepts={v: {kind: sum(rw["decision"] == "accept" for rw in d[kind]) for kind in d} for v, d in dec.items()},
                   blur_sigma=BLUR_SIGMA, min_tex_px=MIN_TEX_PX, seconds=round(time.time() - t0, 1))
        (out / f"ep{ep:02d}.json").write_text(json.dumps({**row, "decisions": dec}, indent=1, default=float))
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
