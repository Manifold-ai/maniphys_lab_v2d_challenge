"""Tier 3 readers for released per-episode files that carry more than Tier 3 may use.

ground_plane/*.json holds the floor plane (`plane`, a static scene calibration like the object meshes) and
`foot_plane_dist_stats`, statistics of the clean multi-view human's feet against that floor: a summary of a clean
trajectory, so not Tier 3 input (Kaggle rule 2.8.c). Two layers keep it out:
  - data: `sanitize` rewrites $T3_ROOT/input/ground_plane/*.json to `{"plane": [...]}` (the copies are byte-identical
    to the released Tier 2 files, checked against them before rewriting);
  - code: every Tier 3 script reads the plane through `ground_plane` / `read_plane`, which refuse a file holding any
    other field, so a fresh copy of the released files stops the pipeline instead of being read.
probe_ground_plane_guard.py checks both, and that no Tier 3 script reads ground_plane files another way.

    python t3_inputs.py sanitize <tier3 root> <released tier 2 dir>
"""
import json
import sys
from pathlib import Path

ALLOWED = {"plane"}


class Tier3InputError(RuntimeError):
    pass


def read_plane(path: Path) -> list[float]:
    d = json.loads(Path(path).read_text())
    extra = set(d) - ALLOWED
    if extra:
        raise Tier3InputError(f"{path} holds {sorted(extra)} besides the plane; run t3_inputs.py sanitize (Tier 3 reads the plane only)")
    return [float(x) for x in d["plane"]]


def ground_plane(root: Path, meta: dict) -> list[float]:
    """The released floor plane of an episode, from its episodes_metadata.jsonl entry."""
    return read_plane(Path(root) / "input" / meta["ground_plane"])


def sanitize(root: Path, released: Path) -> None:
    files = sorted((root / "input" / "ground_plane").glob("*.json"))
    for f in files:
        d = json.loads(f.read_text())
        if set(d) == ALLOWED:
            continue
        src = released / "ground_plane" / f.name
        if not src.exists() or src.read_bytes() != f.read_bytes():
            raise SystemExit(f"{f} is not the released {src}; not rewriting it")
        tmp = f.with_suffix(".json.new")
        tmp.write_text(json.dumps({"plane": d["plane"]}, indent=2) + "\n")
        tmp.replace(f)
    left = [f.name for f in files if set(json.loads(f.read_text())) != ALLOWED]
    print(f"{len(files)} ground plane files, plane only: {len(files) - len(left)}", "| not sanitized: " + ", ".join(left) if left else "")
    if left:
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "sanitize":
        raise SystemExit(__doc__)
    sanitize(Path(sys.argv[2]), Path(sys.argv[3]))
