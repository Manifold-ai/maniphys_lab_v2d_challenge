"""Whether a candidate Tier 3 version may replace the delivered one: the three criteria registered 10-13 before results.

All on the 29 regular episodes (ep28, suspect, is left out); all three must hold.
  1 image   silhouette IoU against the SAM2 mask (t3_align_check.py): the mean of the per-episode medians at most
            IOU_DROP below the uncorrected `best`, and at most MAX_WORSE episodes more than EP_DROP below it.
  2 physics no object floor penetration; support penetration, unheld motion, pose jumps, acceleration spikes and feet
            penetration each no higher than the delivered version. Support penetration is counted as t3_support.py does
            (object centre over a support patch grown by PATCH_MARGIN_M, lowest point between FLOOR_TOL_M and
            SUP_PEN_BAND_M below it), against one set of supports for both versions. Feet floating is reported only.
  3 gate    rxzhou's gate against our supports: every |gap| <= 30 mm (support_recheck.sh); hand contact frames at
            least CONTACT_KEEP of the delivered version's.

    python t3_replace_check.py <tier3 root> <gate dir> <align json> <support dir> <candidate version> <candidate set>
        <delivered version> <delivered set> <out json>
The align json must hold `tier3_cari4d_f830_best` and the candidate. Prints PASS / FAIL and writes the numbers.
"""

import json
import sys
from pathlib import Path

import numpy as np

IOU_DROP = 0.01
EP_DROP = 0.02
MAX_WORSE = 3
CONTACT_KEEP = 0.95
GAP_MM = 30.0
BEST = "tier3_cari4d_f830_best"
SKIP = "ep28"
PHYS = ("unheld_motion", "pose_jump", "acceleration_spike", "feet_penetration")


def need(files: list, n: int, what: str) -> list:
    """A missing directory reads as zero counts and would pass every 'no higher than' check: refuse instead."""
    if len(files) != n:
        raise SystemExit(f"{what}: {len(files)} files, want {n}")
    return files


def physics(root: Path, version: str) -> dict:
    tot = {}
    for f in need(sorted((root / "runs/physics" / version / "out").glob("ep*.json")), 30, f"physics {version}"):
        if SKIP in f.name:
            continue
        for x in json.loads(f.read_text())["findings"]:
            tot[x["check"]] = tot.get(x["check"], 0) + x["frames"]
    return tot


def support_pen(root: Path, version: str, sup_dir: Path) -> int:
    import pyarrow.parquet as pq

    sys.path.insert(0, str(root / "code/stages/recovery/tier3"))
    from t3_support import FLOOR_TOL_M, PATCH_MARGIN_M, SUP_PEN_BAND_M, inside, main_basis

    o_m, u_m, v_m = main_basis(root)
    n = 0
    for f in need(sorted((root / "runs/physics" / version / "out").glob("ep*.npz")), 30, f"physics npz {version}"):
        name = f.stem
        if SKIP in name or not (sup_dir / f"{name}.json").exists():
            continue
        ep = int(name[2:4])
        par = next(p for p in (root / "runs" / (version + s) / "data/chunk-000" / f"episode_{ep:06d}.parquet" for s in ("", "_suspect")) if p.exists())
        pos = np.stack(pq.read_table(par).column("observation.object.pose").to_numpy(zero_copy_only=False))[:, :3].astype(float)
        low = np.load(f)["obj_low"]
        xy = np.c_[(pos - o_m) @ u_m, (pos - o_m) @ v_m]
        pen = np.zeros(len(low), bool)
        for s in json.loads((sup_dir / f"{name}.json").read_text())["supports"]:
            poly = np.asarray(s["patch_xy_m"], float)
            if len(poly) >= 3:
                h = s["height_m"]
                pen |= inside(poly, xy, PATCH_MARGIN_M) & (low < h - FLOOR_TOL_M) & (low > h - SUP_PEN_BAND_M)
        n += int(pen.sum())
    return n


def contact(gate: Path, gset: str) -> int:
    t = 0
    for f in need(sorted((gate / "repo/runs/logs/batch").glob(f"t3_{gset}_ep*.tsv")), 30, f"gate {gset}"):
        if f.stem.endswith("ep28"):
            continue
        c = f.read_text().rstrip("\n").split("\t")
        t += int(c[5]) + int(c[6])
    return t


def gaps(gate: Path, gset: str) -> dict:
    out = {}
    for line in (gate / "logs" / f"oursup_{gset}.txt").read_text().splitlines():
        if "gap_mm=" in line:
            out[int(line.split()[0])] = float(line.split("gap_mm=")[1].split()[0])
    return out


def main() -> None:
    root, gate, align, sup_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    cand, cset, deliv, dset, out = sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], Path(sys.argv[9])
    rows = [r for r in json.loads(align.read_text()) if SKIP not in r["episode"]]
    if len(rows) != 29 or any(cand not in r for r in rows):
        raise SystemExit(f"{align}: {len(rows)} regular episodes, or no {cand}")
    ib = np.array([r[BEST]["iou_p50"] for r in rows])
    ic = np.array([r[cand]["iou_p50"] for r in rows])
    worse = [r["episode"] for r in rows if r[BEST]["iou_p50"] - r[cand]["iou_p50"] > EP_DROP]
    c1 = {"iou_best": round(float(ib.mean()), 4), "iou_candidate": round(float(ic.mean()), 4), "worse_episodes": worse,
          "pass": bool(ib.mean() - ic.mean() <= IOU_DROP and len(worse) <= MAX_WORSE)}
    pc, pd = physics(root, cand), physics(root, deliv)
    sc, sd = support_pen(root, cand, sup_dir), support_pen(root, deliv, sup_dir)
    items = {k: [pd.get(k, 0), pc.get(k, 0)] for k in PHYS} | {"support_penetration": [sd, sc]}
    c2 = {"delivered_vs_candidate": items, "object_floor_penetration": pc.get("object_floor_penetration", 0),
          "feet_floating_reported": [pd.get("feet_floating", 0), pc.get("feet_floating", 0)],
          "pass": bool(pc.get("object_floor_penetration", 0) == 0 and all(v[1] <= v[0] for v in items.values()))}
    g = gaps(gate, cset)
    kc, kd = contact(gate, cset), contact(gate, dset)
    c3 = {"gap_pass": sum(abs(v) <= GAP_MM for v in g.values()), "gap_episodes": len(g), "max_abs_gap_mm": max(abs(v) for v in g.values()),
          "contact_delivered": kd, "contact_candidate": kc,
          "pass": bool(len(g) == 30 and all(abs(v) <= GAP_MM for v in g.values()) and kc >= CONTACT_KEEP * kd)}
    res = {"candidate": cand, "delivered": deliv, "c1_image": c1, "c2_physics": c2, "c3_gate": c3,
           "pass": c1["pass"] and c2["pass"] and c3["pass"]}
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, ensure_ascii=False))
    print("PASS" if res["pass"] else "FAIL")


if __name__ == "__main__":
    main()
