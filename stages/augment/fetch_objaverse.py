"""Fetch public replacement assets for the asset-swap pilot from Objaverse (LVIS-labelled subset).

Only CC0 and CC BY objects are kept (Kaggle rule 2.7.a: external data must be public and free; non-commercial and
share-alike licences are excluded on purpose). Name, author, licence and viewer URL are recorded per object, because
CC BY requires attribution.

    python fetch_objaverse.py <out dir> <group=lvis_cat[,lvis_cat...][@name regex]>... [--per-group N] [--max-faces F]
    e.g. python fetch_objaverse.py objaverse_pilot stool=stool box=box,crate cooker=cooker
         python fetch_objaverse.py objaverse_stool stool=stool,music_stool 'barchair=chair@(?i)bar|stool|counter'
The optional regex keeps only objects whose Objaverse name matches it (LVIS categories such as chair are broad).
"""

import argparse
import json
import re
import shutil
from pathlib import Path

import objaverse

LICENCES = {"cc0", "by"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("groups", nargs="+")
    ap.add_argument("--per-group", type=int, default=8)
    ap.add_argument("--max-faces", type=int, default=300000)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lvis = objaverse.load_lvis_annotations()
    picked = {}
    for spec in a.groups:
        group, cats = spec.split("=", 1)
        cats, _, pattern = cats.partition("@")
        uids = list(dict.fromkeys(u for c in cats.split(",") for u in lvis[c]))
        ann = objaverse.load_annotations(uids)
        good = []
        for u in uids:
            meta = ann.get(u) or {}
            licence = (meta.get("license") or "").lower()
            faces = meta.get("faceCount") or 0
            if pattern and not re.search(pattern, meta.get("name") or ""):
                continue
            if licence in LICENCES and 0 < faces < a.max_faces:
                good.append({"uid": u, "licence": licence, "name": meta.get("name"),
                             "author": (meta.get("user") or {}).get("username"), "url": meta.get("viewerUrl"), "faces": faces,
                             "lvis": [c for c in cats.split(",") if u in lvis[c]]})
        picked[group] = good[: a.per_group]
        print(group, "cc0/by candidates:", len(good), "taking", len(picked[group]))
    paths = objaverse.load_objects(uids=[x["uid"] for g in picked.values() for x in g], download_processes=4)
    for group, items in picked.items():
        for x in items:
            src = paths.get(x["uid"])
            if src:
                dst = out / f"{group}_{x['uid']}.glb"
                shutil.copy(src, dst)
                x["file"] = dst.name
    (out / "manifest.json").write_text(json.dumps(picked, indent=1))
    print("downloaded", sum(1 for g in picked.values() for x in g if "file" in x))


if __name__ == "__main__":
    main()
