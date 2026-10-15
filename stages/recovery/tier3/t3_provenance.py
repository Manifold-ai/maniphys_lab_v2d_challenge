"""Which code and which inputs produced a Tier 3 version, written next to it as runs/<version>.provenance.json.

Kaggle rule 2.9 lets the sponsor ask which input produced a submission and for a one-command reproduction. Until 10-15
neither could be answered for the dynamics versions: L40S's code/DEPLOYED still named the 10-13 commit while single
files had been rsynced over it since, and best_dyn4 ... best_dyn7 recorded no code at all.

deploy_l40s.sh deploys a clean commit and writes code/DEPLOYED (the commit) and code/MANIFEST.sha256 (every deployed
file). stamp() hashes the files this process actually loaded from the code tree (the running script and every imported
module under it) and checks them against the manifest; a file changed after the deploy, or a missing DEPLOYED, stops the
run unless T3_ALLOW_UNDEPLOYED=1, and then the record says so. The declared input paths are recorded resolved, and any
that resolves into a Tier 1 or Tier 2 release directory stops the run (tier_guard catches reads by path; a copied and
renamed directory is caught only here, by where the caller says its inputs came from).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

CODE = Path(__file__).resolve().parents[3]  # <code root>/stages/recovery/tier3/t3_provenance.py
LOWER = ("tier_1_multiview_caption", "tier_2_synthetic_noise")


class ProvenanceError(RuntimeError):
    pass


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stamp(inputs: list[str | Path]) -> dict:
    allow = os.environ.get("T3_ALLOW_UNDEPLOYED") == "1"
    deployed = (CODE / "DEPLOYED").read_text().strip() if (CODE / "DEPLOYED").exists() else None
    manifest = {}
    if (CODE / "MANIFEST.sha256").exists():
        for line in (CODE / "MANIFEST.sha256").read_text().splitlines():
            h, rel = line.split(maxsplit=1)
            manifest[rel.removeprefix("./")] = h
    used = {Path(sys.argv[0]).resolve()}
    used |= {Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, "__file__", None)}
    files = {}
    for p in sorted(used):
        try:
            rel = p.relative_to(CODE).as_posix()
        except ValueError:
            continue  # site-packages, the interpreter's own modules
        files[rel] = _sha(p)
    changed = sorted(r for r, h in files.items() if manifest.get(r) != h)
    problems = []
    if deployed is None or "dirty=0" not in deployed:
        problems.append(f"code/DEPLOYED is {deployed!r}, not a clean deploy")
    if changed:
        problems.append(f"files differ from code/MANIFEST.sha256: {changed}")
    resolved = [os.path.realpath(str(x)) for x in inputs]
    lower = [r for r in resolved if any(n in r for n in LOWER)]
    if lower:
        raise ProvenanceError(f"inputs resolve into a lower tier's release: {lower}")
    if problems and not allow:
        raise ProvenanceError("; ".join(problems) + " (deploy with deploy_l40s.sh, or T3_ALLOW_UNDEPLOYED=1 to record it)")
    return {"deployed": deployed, "code_files_sha256": files, "undeployed": problems, "argv": sys.argv,
            "inputs": resolved, "python": sys.version.split()[0], "time": time.strftime("%Y-%m-%d %H:%M:%S %Z")}


def write(path: Path, record: dict) -> None:
    Path(path).write_text(json.dumps(record, indent=1))
