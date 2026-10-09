"""Apply the silhouette quality gate to episodes already assembled: any episode whose object_check.json says ok=false
(or has no verdict yet) is moved from runs/tier3_cari4d/ to runs/tier3_cari4d_suspect/, parquet and metadata together.
Used once for episodes assembled before the gate existed; the queue routes new episodes itself.

    python t3_regate.py <tier3 root>
"""

import json
import shutil
import sys
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1])
    main_dir, suspect = root / "runs" / "tier3_cari4d", root / "runs" / "tier3_cari4d_suspect"
    for pq in sorted((main_dir / "data" / "chunk-000").glob("episode_*.parquet")):
        ep = int(pq.stem.split("_")[1])
        meta_path = main_dir / "meta" / f"episode_{ep:06d}.metadata.json"
        name = f"ep{ep:02d}_{json.loads(meta_path.read_text())['object']}"
        check = root / "runs" / "checks" / name / "object_check.json"
        verdict = json.loads(check.read_text()).get("ok") if check.exists() else None
        if verdict is True:
            print(f"{name}: keep (gate ok)")
            continue
        for src, sub in ((pq, "data/chunk-000"), (meta_path, "meta")):
            dst = suspect / sub / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), dst)
        print(f"{name}: moved to suspect (gate {verdict})")


if __name__ == "__main__":
    main()
