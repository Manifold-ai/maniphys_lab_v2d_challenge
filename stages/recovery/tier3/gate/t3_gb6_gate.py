"""The registered gb5 machine gate (t3_gb5_gate.py, unchanged) applied to gb6 against gb4 or against gb5 (10-21; gb6
registration in agent-doc/handoff-tier3-rotation-2026-10-21-attr.md: "用 gb5 的登记闸门对 gb4 判一次，另报对 gb5 的同样数字").

Only the version names, the gate sets and the old side's CoCoNet work dir change; the criteria, thresholds and the
whole-batch revert rule are t3_gb5_gate.py's. Its output keeps the field names "gb4_gb5" and per-episode pairs, which
here read [old, new]; the json gains "compared": {"old": ..., "new": ...}.

    python t3_gb6_gate.py <tier3 root> <gate dir> <out json> <gb6 work dir> <gb4|gb5> <episode>...
Last line: GB5_GATE <verdict> (the gate's own line).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_gb5_gate as g  # noqa: E402

OLD = {"gb4": ("tier3_cari4d_gb4_best_dr2s_dyn7", "gb4dyn7", "work_fp"),
       "gb5": ("tier3_cari4d_gb5_best_dr2s_dyn7", "gb5dyn7", "work_b050")}


def main():
    root, gdir, dst, work, old, eps = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:]
    g.NEW, g.NEW_SET = "tier3_cari4d_gb6_best_dr2s_dyn7", "gb6dyn7"
    g.OLD, g.OLD_SET, old_work = OLD[old]
    g.jumps = lambda r, w, name: _jumps(r, w, name, old_work)  # t3_gb5_gate.jumps reads the old side from work_fp
    sys.argv = [sys.argv[0], root, gdir, dst, work, *eps]
    g.main()
    res = json.loads(Path(dst).read_text())
    res["compared"] = {"old": g.OLD, "new": g.NEW}
    Path(dst).write_text(json.dumps(res, indent=1))


def _jumps(root, work, name, old_work):
    """t3_gb5_gate.jumps with the old side's work dir as a parameter (same symmetry and threshold)."""
    import numpy as np
    import trimesh

    ep = int(name[2:4])
    meta = next(m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m and m["episode_index"] == ep)
    mesh = trimesh.load(root / "input" / meta["mesh"], force="mesh")
    body = mesh if mesh.is_watertight else mesh.convex_hull
    G, axis = g.symmetries(g.Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)
    seq = f"episode_{ep:06d}"
    out = {}
    for k, w in (("gb5", work), ("gb4", old_work)):
        R = g.rotations(root / "runs" / w / name / "cari4d" / seq)
        out[k] = int(sum(g.sym_angle_deg(R[f:f + 1], R[f + 1:f + 2], G, axis)[0, 0] > g.JUMP_DEG for f in range(len(R) - 1)))
    return out


if __name__ == "__main__":
    main()
