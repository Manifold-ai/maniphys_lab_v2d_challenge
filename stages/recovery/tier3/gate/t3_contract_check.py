"""Data contract of a Tier 3 version against the version it was made from (self-check item 11, 10-16).

Per episode, both versions' parquet (main or _suspect): the same columns with the same types, the same frame count and
episode index; no NaN or infinite value in any numeric column; object quaternions of unit norm (within QUAT_TOL); and
which columns changed. A post-process states which columns it may change (the dynamics post-process: only
observation.object.pose); any other changed column is reported as unexpected and makes the exit status 1, as does any
of the above.

    python t3_contract_check.py <tier3 root> <base version> <version> [allowed column,...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

QUAT_TOL = 1e-3


def find(root: Path, v: str, ep_file: str):
    for sub in ("", "_suspect"):
        f = root / "runs" / (v + sub) / "data" / "chunk-000" / ep_file
        if f.exists():
            return f
    return None


def flat(col):
    """A column as a float array of shape (frames, -1), or None when it is not numeric."""
    vals = col.to_pylist()
    try:
        a = np.asarray(vals, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    return a.reshape(len(vals), -1)


def main():
    root, base, ver = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    allowed = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else {"observation.object.pose"}
    files = sorted({f.name for sub in ("", "_suspect") for f in (root / "runs" / (ver + sub) / "data" / "chunk-000").glob("episode_*.parquet")})
    bad, rows = [], []
    for name in files:
        fb, fv = find(root, base, name), find(root, ver, name)
        if fb is None:
            bad.append(f"{name}: not in {base}"); continue
        tb, tv = pq.read_table(fb), pq.read_table(fv)
        row = {"episode": name, "frames": tv.num_rows, "changed": [], "problems": []}
        if tb.schema.names != tv.schema.names or [str(t) for t in tb.schema.types] != [str(t) for t in tv.schema.types]:
            row["problems"].append("schema differs")
        if tb.num_rows != tv.num_rows:
            row["problems"].append(f"frames {tb.num_rows} -> {tv.num_rows}")
        for c in tv.schema.names:
            if c not in tb.schema.names:
                continue
            a, b = flat(tv.column(c)), flat(tb.column(c))
            if a is not None and not np.isfinite(a).all():
                row["problems"].append(f"{c}: {int((~np.isfinite(a)).sum())} non-finite values")
            if a is not None and b is not None and a.shape == b.shape:
                if not np.array_equal(a, b):
                    row["changed"].append(c)
            elif tv.column(c).to_pylist() != tb.column(c).to_pylist():
                row["changed"].append(c)
        pose = flat(tv.column("observation.object.pose"))
        qn = np.linalg.norm(pose[:, 3:7], axis=1)
        if np.abs(qn - 1).max() > QUAT_TOL:
            row["problems"].append(f"object quaternion norm off by {np.abs(qn - 1).max():.4f}")
        unexpected = [c for c in row["changed"] if c not in allowed]
        if unexpected:
            row["problems"].append(f"unexpected changed columns: {unexpected}")
        if row["problems"]:
            bad.append(f"{name}: {row['problems']}")
        rows.append(row)
    print(json.dumps({"base": base, "version": ver, "episodes": len(rows), "allowed": sorted(allowed),
                      "changed_columns": sorted({c for r in rows for c in r["changed"]}), "problems": bad}, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
