"""Machine gate of the gb5 rollout against gb4 (10-20; criteria registered in the Tier 3 handoff, "gb5 推广", before the run).

Runs after t3_sel_full.sh gb5 and its self-check, in the v2d_cari4d image (torch, trimesh; pyarrow on PYTHONPATH).
  M1 the final versions: same episodes, schema, frame counts, finite values, unit quaternions (as t3_contract_check.py);
     the 17 episodes outside the rollout unchanged in every column; the 13 rollout episodes may change (CoCoNet
     re-optimizes the human with the object)
  M2 object dynamics violation frames <= gb4's        M3 IoU < 0.5 sampled frames <= gb4's
  M4 the training gate on our supports 30/30          M5 labelled-contact frames with the hand > 3 cm away, share <= gb4's
  M6 CoCoNet orientation jumps (symmetry-aware, > JUMP_DEG) over the 13 episodes <= gb4's, and every episode <= gb4's
M1/M4 failing is FAIL; M2/M3/M5/M6 over gb4 is ATTRIBUTE (the user decides after the cause is listed per episode and item).
Whole-batch revert (automatic): a rollout episode is "worse" when its violations, its IoU < 0.5 frames or its jumps exceed
gb4's; at least WORSE_SHARE of the rollout episodes worse means REVERT (gb4 stays for all 13).

    python t3_gb5_gate.py <tier3 root> <gate dir> <out json> <rollout work dir> <episode>...
Last line: GB5_GATE PASS | ATTRIBUTE <items> | FAIL <items> | REVERT <n>/<m> worse.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from t3_contract_check import QUAT_TOL, find, flat  # noqa: E402
from t3_delivery_report import dyn, gate, ho  # noqa: E402
from t3_fp_select import sym_angle_deg  # noqa: E402
from t3_sel_gate import rotations  # noqa: E402
from t3_symmetry import Shape, symmetries  # noqa: E402

JUMP_DEG = 24.0
WORSE_SHARE = 1 / 3
NEW, OLD = "tier3_cari4d_gb5_best_dr2s_dyn7", "tier3_cari4d_gb4_best_dr2s_dyn7"
NEW_SET, OLD_SET = "gb5dyn7", "gb4dyn7"


def contract(root, eps13):
    files = sorted({f.name for v in (NEW, OLD) for sub in ("", "_suspect") for f in (root / "runs" / (v + sub) / "data" / "chunk-000").glob("episode_*.parquet")})
    idx13 = {f"episode_{int(e[2:4]):06d}.parquet" for e in eps13}
    problems, changed13 = [], set()
    for name in files:
        fo, fn = find(root, OLD, name), find(root, NEW, name)
        if fo is None or fn is None:
            problems.append(f"{name}: missing in {'gb4' if fo is None else 'gb5'}")
            continue
        to, tn = pq.read_table(fo), pq.read_table(fn)
        if to.schema.names != tn.schema.names or [str(t) for t in to.schema.types] != [str(t) for t in tn.schema.types]:
            problems.append(f"{name}: schema differs")
            continue
        if to.num_rows != tn.num_rows:
            problems.append(f"{name}: frames {to.num_rows} -> {tn.num_rows}")
            continue
        changed = []
        for c in tn.schema.names:
            a, b = flat(tn.column(c)), flat(to.column(c))
            if a is not None and not np.isfinite(a).all():
                problems.append(f"{name} {c}: non-finite values")
            same = np.array_equal(a, b) if a is not None and b is not None and a.shape == b.shape else tn.column(c).to_pylist() == to.column(c).to_pylist()
            if not same:
                changed.append(c)
        q = flat(tn.column("observation.object.pose"))[:, 3:7]
        if np.abs(np.linalg.norm(q, axis=1) - 1).max() > QUAT_TOL:
            problems.append(f"{name}: object quaternion norm")
        if name in idx13:
            changed13 |= set(changed)
        elif changed:
            problems.append(f"{name}: outside the rollout but changed {changed}")
    return {"episodes": len(files), "changed_columns_in_rollout": sorted(changed13), "problems": problems}


def jumps(root, work, name):
    ep = int(name[2:4])
    meta = next(m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m and m["episode_index"] == ep)
    mesh = trimesh.load(root / "input" / meta["mesh"], force="mesh")
    body = mesh if mesh.is_watertight else mesh.convex_hull
    G, axis = symmetries(Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)
    seq = f"episode_{ep:06d}"
    out = {}
    for k, w in (("gb5", work), ("gb4", "work_fp")):
        R = rotations(root / "runs" / w / name / "cari4d" / seq)
        out[k] = int(sum(sym_angle_deg(R[f:f + 1], R[f + 1:f + 2], G, axis)[0, 0] > JUMP_DEG for f in range(len(R) - 1)))
    return out


def main():
    root, g, dst, work, eps13 = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5:]
    m1 = contract(root, eps13)
    D, DO = dyn(g, NEW_SET), dyn(g, OLD_SET)
    _, share = ho(g, NEW_SET)
    _, share_old = ho(g, OLD_SET)
    ours = gate(g, NEW_SET, True)
    align = lambda s, v: {e["episode"]: sum(1 for x in e[v]["per_frame"]["iou"] if x < 0.5)
                          for e in json.loads((root / "dev" / "audit" / f"align_{s}.json").read_text()) if v in e}
    L, LO = align(NEW_SET, NEW), align(OLD_SET, OLD)
    per = {}
    for name in eps13:
        k = name[:4]
        j = jumps(root, work, name)
        per[name] = {"violations": [DO[k]["object_any"], D[k]["object_any"]], "iou_lt_0.5": [LO[name], L[name]],
                     "jumps": [j["gb4"], j["gb5"]]}
        per[name]["worse"] = [m for m, (a, b) in per[name].items() if b > a]
    viol = [sum(e["object_any"] for e in DO.values()), sum(e["object_any"] for e in D.values())]
    low = [sum(LO.values()), sum(L.values())]
    jsum = [sum(p["jumps"][0] for p in per.values()), sum(p["jumps"][1] for p in per.values())]
    worse = [n for n, p in per.items() if p["worse"]]
    res = {
        "M1": {"ok": not m1["problems"], **m1},
        "M2": {"ok": viol[1] <= viol[0], "gb4_gb5": viol},
        "M3": {"ok": low[1] <= low[0], "gb4_gb5": low},
        "M4": {"ok": len(ours) == 30 and all(ours.values()), "passed": sum(ours.values()), "of": len(ours)},
        "M5": {"ok": share <= share_old, "gb4_gb5_percent": [round(100 * share_old, 3), round(100 * share, 3)]},
        "M6": {"ok": jsum[1] <= jsum[0] and all(p["jumps"][1] <= p["jumps"][0] for p in per.values()), "gb4_gb5": jsum,
               "episodes_over": [n for n, p in per.items() if p["jumps"][1] > p["jumps"][0]]},
        "per_episode": per, "worse": worse, "worse_share_limit": WORSE_SHARE,
    }
    fails = [m for m in ("M1", "M4") if not res[m]["ok"]]
    over = [m for m in ("M2", "M3", "M5", "M6") if not res[m]["ok"]]
    if fails:
        verdict = "FAIL " + " ".join(fails)
    elif len(worse) >= WORSE_SHARE * len(eps13):
        verdict = f"REVERT {len(worse)}/{len(eps13)} worse"
    elif over:
        verdict = "ATTRIBUTE " + " ".join(over)
    else:
        verdict = "PASS"
    res["verdict"] = verdict
    json.dump(res, open(dst, "w"), indent=1)
    for m in ("M1", "M2", "M3", "M4", "M5", "M6"):
        print(m, json.dumps({k: v for k, v in res[m].items() if k != "problems"}), "problems:" if res[m].get("problems") else "", res[m].get("problems", "") or "")
    for n, p in per.items():
        print(n, json.dumps(p))
    print("GB5_GATE", verdict)


if __name__ == "__main__":
    main()
