"""Apply one body-frame turn (a B1 candidate) to a frame range of a Tier 3 object trajectory, about the centre of mass (Tier 3 inputs only).

Plan: agent-doc/plan-t3flip13-2026-10-27.md on track2/p1-training, section 1 step 5.

The candidate names are t3_fix_tex.py's: flip_a<k> is 180 deg about the k-th principal axis of inertia of the body
(mesh if watertight, else its convex hull), computed as there. Frames [a, b) of the input version get pose @ about_com(g);
the centre of mass keeps its path. Other frames and other columns keep their bytes. Writes runs/<out version>{,_suspect}/
with the input's layout and meta, copies the input's depth_post.json under the output name, and runs/<out version>.apply_turn.json.

    python t3_apply_turn.py <tier3 root> <version> <out version> <episode> <candidate> <a> <b>
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh

    here = Path(__file__).resolve().parent
    sys.path[:0] = [str(here), str(here / "gate"), str(here.parents[2] / "libs" / "v2d_infra")]
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    import t3_provenance
    from t3_dynamics_post import to_q, to_R
    from t3_fix_units import about_com, principal, rot

    root, version, out_v = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    ep, cand, a, b = int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), int(sys.argv[7])
    rn = root / "runs"
    if (rn / out_v).exists() or (rn / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    prov = t3_provenance.stamp([root / "input", rn / version, rn / f"{version}_suspect"])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    report = []
    for src_v, dst_v in ((version, out_v), (f"{version}_suspect", f"{out_v}_suspect")):
        for f in sorted((rn / src_v / "data" / "chunk-000").glob("episode_*.parquet")):
            table = pq.read_table(f)
            e = int(table.column("episode_index")[0].as_py())
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{e:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())
            if e != ep:
                shutil.copy2(f, dst)
                continue
            m = metas[e]
            name = f"ep{e:02d}_{m['object']}"
            pose = np.stack(table.column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(np.float64)
            n = len(pose)
            if not (0 <= a < b <= n):
                raise SystemExit(f"{name}: frames [{a}, {b}) outside 0..{n}")
            mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
            body = mesh if mesh.is_watertight else mesh.convex_hull
            com_b = np.asarray(body.center_mass, np.float64)
            moments, axes = principal(body.moment_inertia)
            if not (cand.startswith("flip_a") and cand[6:].isdigit()):
                raise SystemExit(f"candidate {cand} is not a principal flip")
            g = rot(axes[:, int(cand[6:])], 180)
            G = about_com(g, com_b)
            T = np.tile(np.eye(4), (n, 1, 1))
            T[:, :3, :3] = to_R(pose[:, 3:7])
            T[:, :3, 3] = pose[:, :3]
            T2 = T.copy()
            T2[a:b] = T[a:b] @ G
            out = pose.copy()
            out[a:b, :3] = T2[a:b, :3, 3]
            out[a:b, 3:7] = to_q(T2[a:b, :3, :3])
            col = pa.FixedSizeListArray.from_arrays(pa.array(out.astype(np.float32).ravel(), pa.float32()), 7)
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), col)
            md = dict(out_t.schema.metadata or {})
            md[b"apply_turn"] = json.dumps({"from": version, "candidate": cand, "frames": [a, b]}).encode()
            pq.write_table(out_t.replace_schema_metadata(md), dst)
            com = pose[:, :3] + to_R(pose[:, 3:7]) @ com_b
            com2 = out[:, :3] + to_R(out[:, 3:7]) @ com_b
            row = {"episode": name, "tier": dst_v, "frames": n, "candidate": cand, "applied": [a, b],
                   "com_shift_max_m": round(float(np.linalg.norm(com2 - com, axis=1).max()), 6)}
            report.append(row)
            print(json.dumps(row), flush=True)
    rec = rn / f"{version}.depth_post.json"
    if rec.exists():
        shutil.copy2(rec, rn / f"{out_v}.depth_post.json")
    (rn / f"{out_v}.apply_turn.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(rn / f"{out_v}.provenance.json", prov | {"made_by": "t3_apply_turn.py", "from_version": version})


if __name__ == "__main__":
    main()
