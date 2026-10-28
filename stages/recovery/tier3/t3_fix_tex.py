"""Texture orientation choice for symmetric and near-symmetric objects on a delivered Tier 3 version, t3fix part B1
(Tier 3 inputs only: the exo video, the SAM2 masks, the mesh and the delivered layer).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 3.1, section 1 B1 and criterion G0.

Per episode in scope (it has a non-identity symmetry, a continuous axis or a near-symmetry axis):
  candidates  180 deg about each principal axis, the non-identity symmetry rotations, CONT_STEP_DEG steps about the
              continuous axis and STEP_DEG steps about the near-symmetry axis, each turned about the centre of mass;
              duplicates and the identity are dropped (no filter on the surface shift: a flip the shape hides is
              exactly what the texture may show);
  gate        on GATE_FRAMES evidence frames, the point-splat silhouette against t3_object_check.rasterise (IoU median);
              the sample count doubles up to N_MAX while the gate fails;
  distinct    (a) on DISTINCT_FRAMES evidence frames, per variant: NCC of the current render and each candidate's
              render on their common covered pixels, and the self control (the current pose rendered from a second
              sample set). A candidate is not distinct if its median is >= DISTINCT_NCC or >= self median - SELF_MARGIN;
              it is distinct only if it is distinct in both variants;
  scores      (b) every stride-th evidence frame: NCC of render and video frame on render & object mask & not person,
              variants i and ii (t3_tex); fewer than MIN_TEX_PX region pixels gives nan;
  nulls       (d) "shift1" (the current render moved by 1 px), "reseed" (the current pose from the second sample set),
              "null_5deg" (NULL_DEG about the axis of least inertia) and the candidates that are not distinct;
  positive    the most distinct candidate's second-sample render with Gaussian noise pasted into the masked region
              of the frame; the real set is scored against that synthetic frame (report: the method must find it);
  decisions   (c) one per segment (t3_tex.segments with the unheld flags), on frames where every pose of the set has a
              score in the variant; t3_tex.decide_segment per variant, t3_tex.merge_variants across them.
Nothing is written into the version.

    python t3_fix_tex.py <tier3 root> <selection json> <version> <physics dir> <out dir> [stride=3] [only=<ep>,..] [stage=gate|full]
                         [gap=0.05] [nulls=tilt] [inject=<a>:<b>]
  gap     MIN_GAP override (plan-t3flip13: 0.27);  nulls=tilt adds +-5 and +-10 deg about each principal axis to the null set;
  inject  positive control: the first distinct candidate is applied to the pose on frames [a*n, b*n) (fractions) before
          scoring, and the report says whether the real set accepts that candidate back on those frames (positive_inject).
Writes <out>/epNN.json (and epNN.npz with stage=full); one json line per episode on stdout. CPU only.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "gate"), str(HERE.parents[2] / "libs" / "v2d_infra")]

GAP = 5  # frames, as t3_dynamics_post.GAP
GATE_FRAMES = 20
DISTINCT_FRAMES = 30
GATE_IOU = 0.95
CONT_STEP_DEG = 10
CONT_NEAR_DEG = 30
N_MIN, N_MAX = 1_000_000, 4_000_000
POS_NOISE = 6.0
DEBUG_EPS = {11, 13, 26}
VARIANTS = ("i", "ii")


def angle_deg(a, b) -> float:
    return float(np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1))))


def main() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import cv2
    import h5py
    import trimesh
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    from t3_align_check import WORK, similarity, world_pose
    from t3_fix_units import JUMP_DEG, MIN_EVIDENCE, NULL_DEG, STEP_DEG, about_com, candidates, principal, rot, turn_deg
    from t3_object_check import rasterise
    from t3_symmetry import SYM_M, Shape, symmetries
    from t3_tex import (DISTINCT_NCC, MIN_GAP, MIN_TEX_PX, SELF_MARGIN, SPLAT_PER_PX, band, decide_segment, merge_variants, ncc,
                        segments, splat, surface_samples, ycrcb)
    from t3_track_check import MIN_MASK_PX

    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, version, phys, out = Path(args[0]), Path(args[1]), args[2], Path(args[3]), Path(args[4])
    stride, stage = int(kv.get("stride", 3)), kv.get("stage", "full")
    gap_override = float(kv["gap"]) if "gap" in kv else None
    tilt_nulls = kv.get("nulls") == "tilt"
    inject = tuple(float(x) for x in kv["inject"].split(":")) if "inject" in kv else None
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
        shape = Shape(mesh, com_b)
        group, cont = symmetries(shape, body.moment_inertia)
        moments, axes = principal(body.moment_inertia)
        turns = {x: g for x, g in candidates(moments, axes, shape.shift, SYM_M, group, cont).items() if x.startswith("turn")}
        row = {"episode": name, "stage": stage, "symmetries": len(group), "continuous_axis": cont is not None}
        if len(group) == 1 and cont is None and not turns:
            row["skip"] = "not-in-scope"
            (out / f"ep{ep:02d}.json").write_text(json.dumps(row, indent=1))
            print(json.dumps(row), flush=True)
            continue
        raw = {f"flip_a{i}": rot(axes[:, i], 180) for i in range(3)}
        raw.update({f"sym_g{i}": np.asarray(g, np.float64) for i, g in enumerate(group) if i > 0})
        if cont is not None:
            raw.update({f"cont{d:03d}": rot(cont, d) for d in range(CONT_STEP_DEG, 360, CONT_STEP_DEG)})
        raw.update(turns)
        cand = {}
        for x, g in raw.items():
            if angle_deg(g, np.eye(3)) > 1 and all(angle_deg(g, h) > 1 for h in cand.values()):
                cand[x] = g
        near = {}
        for x in cand:
            for fam, lim in (("cont", CONT_NEAR_DEG), ("turn", STEP_DEG)):
                if x.startswith(fam):
                    near[x] = {y for y in cand if y != x and y.startswith(fam) and angle_deg(cand[x], cand[y]) <= lim + 1e-6}
        row["candidates"] = sorted(cand)
        if mesh.visual.kind != "texture" or getattr(mesh.visual.material, "baseColorTexture", None) is None:
            row["skip"] = "no-texture"
            (out / f"ep{ep:02d}.json").write_text(json.dumps(row, indent=1))
            print(json.dumps(row), flush=True)
            continue
        image = mesh.visual.material.baseColorTexture
        uv = np.asarray(mesh.visual.uv, np.float64)
        G = {"current": np.eye(4), **{x: about_com(g, com_b) for x, g in cand.items()},
             "null_5deg": about_com(rot(axes[:, 0], NULL_DEG), com_b)}
        tilt = {}
        if tilt_nulls:
            for i in range(3):
                for d in (5, -5, 10, -10):
                    tilt[f"tilt_a{i}_{d:+d}"] = about_com(rot(axes[:, i], d), com_b)
        G.update(tilt)
        Tw = world_pose(root, version, ep)
        n = len(Tw)
        inj_name, inj_frames = None, None
        held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
        if len(held) != n:
            raise SystemExit(f"{name}: {len(held)} held flags for {n} frames")
        held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
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

        def render(T, box, sample=0):
            x0, y0, x1, y1 = box
            R_c = rot_.T @ T[:3, :3]
            p_c = rot_.T @ (T[:3, 3] - t) / s
            kk = k.copy()
            kk[0, 2] -= x0
            kk[1, 2] -= y0
            p, c = samples[sample]
            return splat(p @ R_c.T + p_c, c, kk, y1 - y0, x1 - x0), (R_c, p_c, kk)

        # renderer gate; the sample count doubles (up to N_MAX) while the gate fails
        gate_frames = ev[:: max(1, len(ev) // GATE_FRAMES)][:GATE_FRAMES]
        while True:
            samples = [surface_samples(verts, faces, uv, image, n_pts, seed=ep)]
            gate = []
            for f in gate_frames:
                box = crop(Tw[f])
                if box is None:
                    continue
                (img, cov), (R_c, p_c, kk) = render(Tw[f], box)
                ras = rasterise(verts @ R_c.T + p_c, faces, kk, box[3] - box[1], box[2] - box[0])
                gate.append(float((cov & ras).sum()) / max(1.0, float((cov | ras).sum())))
            if not gate or np.median(gate) >= GATE_IOU or n_pts >= N_MAX:
                break
            n_pts = min(2 * n_pts, N_MAX)
        row.update(points=n_pts, max_mask_px=max_px, evidence_frames=len(ev),
                   gate_iou_p50=round(float(np.median(gate)), 4) if gate else None)
        row["gate_ok"] = bool(gate) and row["gate_iou_p50"] >= GATE_IOU
        if stage == "gate" or not row["gate_ok"]:
            (out / f"ep{ep:02d}.json").write_text(json.dumps(row, indent=1))
            print(json.dumps(row), flush=True)
            continue
        samples.append(surface_samples(verts, faces, uv, image, n_pts, seed=ep + 1000))

        def feats(img, cov=None):
            """Per variant: (image, contrast reference)."""
            y = ycrcb(img)
            return {"i": (y, y), "ii": (band(y, cov), y)}

        # (a) texture distinctness, with the self control
        dist = {x: {v: [] for v in VARIANTS} for x in ["reseed", *cand]}
        for f in ev[:: max(1, len(ev) // DISTINCT_FRAMES)][:DISTINCT_FRAMES]:
            box = crop(Tw[f])
            if box is None:
                continue
            (ic, cc), _ = render(Tw[f], box)
            fc = feats(ic, cc)
            for x in dist:
                (ix, cx), _ = render(Tw[f], box, 1) if x == "reseed" else render(Tw[f] @ G[x], box)
                reg = cc & cx
                if reg.sum() < MIN_TEX_PX:
                    continue
                fx = feats(ix, cx)
                for v in VARIANTS:
                    dist[x][v].append(ncc(fc[v][0], fx[v][0], reg, ref=fc[v][1]))
        dmed = {x: {v: (round(float(np.nanmedian(d[v])), 4) if np.isfinite(d[v]).any() else None) for v in VARIANTS} for x, d in dist.items()}

        def distinct_in(x, v):
            a, me = dmed[x][v], dmed["reseed"][v]
            return a is not None and me is not None and a < DISTINCT_NCC and a < me - SELF_MARGIN

        distinct = [x for x in cand if all(distinct_in(x, v) for v in VARIANTS)]
        hidden = [x for x in cand if x not in distinct]
        positive = min(distinct, key=lambda x: dmed[x]["i"]) if distinct else None
        if inject is not None and distinct:
            inj_name = next((x for x in distinct if x.startswith("flip_")), distinct[0])
            a_, b_ = int(inject[0] * n), int(inject[1] * n)
            inj_frames = (a_, b_)
            Tw = Tw.copy()
            Tw[a_:b_] = Tw[a_:b_] @ G[inj_name]  # a 180 deg flip is its own inverse: the method should accept it back

        # (b) scores against the video, the nulls and the positive control
        poses = ["current", *cand, "null_5deg", *tilt, "reseed", "shift1"]
        sc = {v: {x: np.full(n, np.nan) for x in poses} for v in VARIANTS}
        pc = {v: {x: np.full(n, np.nan) for x in ["current", *distinct]} for v in VARIANTS}
        vis = []
        rng = np.random.default_rng(ep)
        cap = cv2.VideoCapture(str(root / "input" / "videos" / f"episode_{ep:06d}.mp4"))
        want, f_now, debug_done = set(ev), 0, ep not in DEBUG_EPS
        while f_now < n:
            ok, frame = cap.read()
            if not ok:
                break
            f = f_now
            f_now += 1
            if f not in want or (box := crop(Tw[f])) is None:
                continue
            x0, y0, x1, y1 = box
            obj, person = masks(f)
            ev_mask = (obj & ~person)[y0:y1, x0:x1]
            vid = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)[y0:y1, x0:x1].astype(np.float32)
            fv = feats(vid)
            rend = {}
            for x in poses:
                if x == "shift1":
                    img, cov = rend["current"]
                    rend[x] = (np.roll(img, 1, axis=1), np.roll(cov, 1, axis=1))
                elif x == "reseed":
                    rend[x] = render(Tw[f], box, 1)[0]
                else:
                    rend[x] = render(Tw[f] @ G[x], box)[0]
            fr = {x: feats(img, cov) for x, (img, cov) in rend.items()}
            for x, (img, cov) in rend.items():
                reg = cov & ev_mask
                if x == "current":
                    vis.append(int(reg.sum()))
                if reg.sum() < MIN_TEX_PX:
                    continue
                for v in VARIANTS:
                    sc[v][x][f] = ncc(fr[x][v][0], fv[v][0], reg, ref=fr[x][v][1])
            if positive is not None:
                (pimg, pcov), _ = render(Tw[f] @ G[positive], box, 1)
                paste = pcov & ev_mask
                syn = vid.copy()
                syn[paste] = np.clip(pimg[paste] + rng.normal(0, POS_NOISE, (int(paste.sum()), 3)), 0, 255)
                fs = feats(syn)
                for x in pc["i"]:
                    img, cov = rend[x]
                    reg = cov & paste
                    if reg.sum() < MIN_TEX_PX:
                        continue
                    for v in VARIANTS:
                        pc[v][x][f] = ncc(fr[x][v][0], fs[v][0], reg, ref=fr[x][v][1])
            if not debug_done:
                img = rend["current"][0]
                cv2.imwrite(str(out / f"ep{ep:02d}_debug.png"), cv2.cvtColor(np.concatenate([vid, img], axis=1).astype(np.uint8), cv2.COLOR_RGB2BGR))
                debug_done = True
        cap.release()

        # (c), (d) decisions per segment
        segs = segments(turn_deg(Tw[:, :3, :3]), JUMP_DEG, ~held)

        def decide(table, names):
            rows = []
            for a, b in segs:
                per = {}
                for v in VARIANTS:
                    fr_ = [f for f in range(a, b) if all(np.isfinite(table[v][x][f]) for x in names)]
                    if len(fr_) < MIN_EVIDENCE:
                        per[v] = {"evidence": len(fr_), "decision": "refuse", "name": None, "reason": "evidence"}
                    else:
                        kw = {"min_gap": gap_override} if gap_override is not None else {}
                        per[v] = {"evidence": len(fr_), **decide_segment({x: [float(table[v][x][f]) for f in fr_] for x in names}, near, **kw)}
                rows.append({"start": a, "end": b, "unheld": bool((~held[a:b]).all()), "variants": per, **merge_variants(per)})
            return rows

        dec = {"real": decide(sc, ["current", *distinct]) if distinct else [],
               "null": decide(sc, ["current", "null_5deg", *tilt, "reseed", "shift1", *hidden]),
               "positive": decide(pc, ["current", *distinct]) if distinct else []}
        inj_rows = []
        if inj_frames is not None:
            a_, b_ = inj_frames
            for rw in dec["real"]:
                ov = max(0, min(rw["end"], b_) - max(rw["start"], a_))
                if ov >= 0.5 * (rw["end"] - rw["start"]):
                    inj_rows.append({"start": rw["start"], "end": rw["end"], "decision": rw["decision"], "name": rw["name"], "reason": rw["reason"]})
        null_any = sum(rw["variants"][v]["decision"] == "accept" for rw in dec["null"] for v in VARIANTS)
        pos_ok = [rw for rw in dec["positive"] if all(rw["variants"][v].get("evidence", 0) >= 30 for v in VARIANTS)]
        np.savez_compressed(out / f"ep{ep:02d}.npz", **{f"{v}__{x}": a for v, d in sc.items() for x, a in d.items()},
                            **{f"pos_{v}__{x}": a for v, d in pc.items() for x, a in d.items()})
        row.update(distinct_ncc=dmed, distinct=distinct, positive=positive, gap=gap_override if gap_override is not None else MIN_GAP,
                   tilt_nulls=sorted(tilt), inject=inj_name, inject_frames=inj_frames,
                   inject_found=(f"{sum(r['decision'] == 'accept' and r['name'] == inj_name for r in inj_rows)}/{len(inj_rows)}" if inj_frames else None),
                   inject_wrong=(sum(r['decision'] == 'accept' and r['name'] != inj_name for r in inj_rows) if inj_frames else None),
                   visible_px_p50=int(np.median(vis)) if vis else 0,
                   scored={v: int(np.isfinite(sc[v]["current"]).sum()) for v in VARIANTS}, segments=len(segs),
                   accepts={kind: sum(rw["decision"] == "accept" for rw in dec[kind]) for kind in dec},
                   null_variant_accepts=null_any,
                   positive_found=f"{sum(rw['decision'] == 'accept' and rw['name'] == positive for rw in pos_ok)}/{len(pos_ok)}",
                   seconds=round(time.time() - t0, 1))
        (out / f"ep{ep:02d}.json").write_text(json.dumps({**row, "decisions": dec}, indent=1, default=float))
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
