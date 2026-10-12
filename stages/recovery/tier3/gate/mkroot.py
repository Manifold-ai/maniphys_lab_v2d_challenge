"""Build a Tier 3 root for rxzhou's retarget gate: <gate repo>/runs/tier3/root_<set>/, laid out as his tier3_root.py does.

    python mkroot.py <gate repo> <set> <support dir | -> <version dir>[,<version dir>...] [ep ...] [--official-ground <dir>]
Metadata rows from the Tier 3 input; data parquets symlinked from the version dirs (the first holding the episode);
meshes from the Tier 3 input; support_surface from <support dir> (`-`, or an episode missing there: the released files'
empty stage, i.e. floor only); ground_plane from the Tier 3 input (plane only, t3_inputs.py). --official-ground <dir>
links released Tier 2 ground files instead, only to reproduce one of rxzhou's runs byte for byte (the retarget reads only
their `plane`, equal to ours; the rest of those files is clean-trajectory statistics Tier 3 must not read).
meta/provenance.json records each parquet's source and sha256 (his converter requires the file).
"""
import hashlib
import json
import os
import sys
from pathlib import Path

EMPTY = '#usda 1.0\n(\n    defaultPrim = "support_surfaces"\n    metersPerUnit = 1\n    upAxis = "Z"\n)\n\ndef Xform "support_surfaces"\n{\n}\n'

args = sys.argv[1:]
ground = None
if "--official-ground" in args:
    i = args.index("--official-ground")
    ground = Path(args[i + 1]).resolve()
    del args[i:i + 2]
repo, name, sup, datas = Path(args[0]), args[1], args[2], [Path(x) for x in args[3].split(",")]
want = {int(x) for x in args[4:]}
T = Path(os.environ.get("T3_ROOT", "/lab_data/yqchen/v2d/tier3"))
root = repo / "runs" / "tier3" / f"root_{name}"
if root.exists():
    raise SystemExit(f"{root} exists")
(root / "data/chunk-000").mkdir(parents=True)
(root / "meta").mkdir()
(root / "support_surface").mkdir()
(root / "mesh").symlink_to(T / "input/mesh")
(root / "ground_plane").symlink_to(ground or T / "input/ground_plane")
rows, prov = [], {}
for m in map(json.loads, (T / "input/meta/episodes_metadata.jsonl").read_text().splitlines()):
    ep = m["episode_index"]
    if want and ep not in want:
        continue
    src = next((d / "data/chunk-000" / f"episode_{ep:06d}.parquet" for d in datas
                if (d / "data/chunk-000" / f"episode_{ep:06d}.parquet").exists()), None)
    if src is None:
        print(f"ep{ep}: no parquet, skipped")
        continue
    (root / "data/chunk-000" / src.name).symlink_to(src.resolve())
    s = root / m["support_surface"]
    f = Path(sup).resolve() / Path(m["support_surface"]).name if sup != "-" else None
    if f is not None and f.exists():
        s.symlink_to(f)
    else:
        s.write_text(EMPTY)
    prov[str(ep)] = {"source_parquet": str(src.resolve()), "parquet_sha256": hashlib.sha256(src.read_bytes()).hexdigest()}
    rows.append(m)
(root / "meta/episodes_metadata.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sorted(rows, key=lambda r: r["episode_index"])))
(root / "meta/provenance.json").write_text(json.dumps({"note": "gate root built by mkroot.py, not tier3_root.py", "episodes": prov}, indent=1))
print(name, len(rows), "episodes:", " ".join(str(r["episode_index"]) for r in rows))
