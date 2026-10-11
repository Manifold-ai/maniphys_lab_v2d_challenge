"""Probe for the Tier 3 ground-plane guard (t3_inputs.py). Exits non-zero on any failure.

  1. read_plane refuses a file shaped like the released one (plane + foot_plane_dist_stats) and reads a plane-only one;
  2. every file in <tier3 root>/input/ground_plane holds the plane only;
  3. no Tier 3 script reads a ground_plane file except through t3_inputs: a line that mentions ground_plane and parses
     JSON (json.load / json.loads / read_text) outside t3_inputs.py fails; an injected direct read must be caught.

    python probe_ground_plane_guard.py <tier3 root>
"""
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t3_inputs  # noqa: E402

DIRECT = re.compile(r"ground_plane.*(json\.loads?|read_text)|(json\.loads?|read_text).*ground_plane")


def direct_reads(paths) -> list[str]:
    hits = []
    for p in paths:
        if p.name in ("t3_inputs.py", "probe_ground_plane_guard.py"):
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if DIRECT.search(line) and not line.lstrip().startswith("#"):
                hits.append(f"{p.name}:{i}")
    return hits


def main() -> None:
    root = Path(sys.argv[1])
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        full, plain = Path(tmp) / "full.json", Path(tmp) / "plain.json"
        full.write_text(json.dumps({"plane": [0, -1, 0, 1.39], "foot_plane_dist_stats": {"median": 0.03}}))
        plain.write_text(json.dumps({"plane": [0, -1, 0, 1.39]}))
        try:
            t3_inputs.read_plane(full)
            bad.append("read_plane accepted a file with foot_plane_dist_stats")
        except t3_inputs.Tier3InputError:
            print("ok  released-shaped file refused")
        if t3_inputs.read_plane(plain) != [0.0, -1.0, 0.0, 1.39]:
            bad.append("read_plane misread a plane-only file")
        else:
            print("ok  plane-only file read")
        injected = Path(tmp) / "t3_injected.py"
        injected.write_text('gp = json.loads((root / "input" / m["ground_plane"]).read_text())["plane"]\n')
        if direct_reads([injected]):
            print("ok  injected direct read caught by the scan")
        else:
            bad.append("the scan missed an injected direct read")
    files = sorted((root / "input" / "ground_plane").glob("*.json"))
    extra = [f.name for f in files if set(json.loads(f.read_text())) != {"plane"}]
    (bad.append(f"input/ground_plane not plane-only: {extra[:3]}... ({len(extra)} of {len(files)})") if extra
     else print(f"ok  {len(files)} input ground plane files hold the plane only"))
    hits = direct_reads(sorted(HERE.glob("*.py")))
    (bad.append("direct ground_plane reads: " + ", ".join(hits)) if hits else print("ok  no Tier 3 script reads ground_plane files directly"))
    for b in bad:
        print("FAIL", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
