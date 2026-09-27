"""用 jev 核对一组结论是否被证据支持（Mac 上执行：jev CLI 与 TypeSafe key 只在本机）。

规格文件（JSON）：
  {"model": "jev-1.13.0",
   "evidence": {"<名字>": {"file": "results/...", "grep": "可选，只取匹配的行"} | {"text": "逐字引用"}},
   "claims": [{"id": "...", "evidence": ["<名字>", ...], "claim": "...", "control": "true" | "false"（可选）}]}
每条 claim 的 source = 所列证据按顺序拼接（文件带路径标题）。数值比较不交给 jev（它不擅长算术）：
先由 stages/evaluate/verdict.py 之类的脚本算好、落进结果文件，再作为证据引用。
输出每条 P(支持)；< 0.7 标 UNVERIFIED，结论里要改口为“未核实”。对照组方向不对
（真对照 < 0.7 或假对照 >= 0.3）说明这次核对本身不可信，退出码 1。

用法：python3 tools/jev_claims.py agent-doc/experiments/2026-09-28-day1.claims.json
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUESTION = "Does `source` support `claim`?"


def evidence_text(spec: dict) -> dict[str, str]:
    out = {}
    for name, e in spec["evidence"].items():
        if "file" in e:
            text = (REPO / e["file"]).read_text()
            if "grep" in e:
                text = "\n".join(line for line in text.splitlines() if re.search(e["grep"], line))
            out[name] = f"[file {e['file']}]\n{text}"
        else:
            out[name] = e["text"]
    return out


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text())
    ev = evidence_text(spec)
    rows = "".join(
        json.dumps({"id": c["id"], "state": {"source": "\n\n".join(ev[n] for n in c["evidence"]), "claim": c["claim"]}},
                   ensure_ascii=False) + "\n"
        for c in spec["claims"])
    model = spec.get("model", "jev-1.13.0")
    r = subprocess.run(["jev", "batch", "--input", "-", "--state-key", "state", "--id-key", "id", "--model", model,
                        "--noul", "supported", QUESTION], input=rows, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        print(r.stdout, r.stderr, sep="\n")
        return r.returncode
    got = {}
    for line in r.stdout.splitlines():
        if line.strip().startswith("{"):
            o = json.loads(line)
            got[o["id"]] = o["answers"]["supported"]["noul"]
    print(f"model {model}; question: {QUESTION}")
    controls_ok = True
    for c in spec["claims"]:
        p = got.get(c["id"])
        if p is None:
            print(f"{c['id']:<20} NO ANSWER")
            controls_ok = False
            continue
        ctrl = c.get("control")
        if ctrl == "true":
            tag = "control(true) ok" if p >= 0.7 else "CONTROL(true) FAILED"
            controls_ok &= p >= 0.7
        elif ctrl == "false":
            tag = "control(false) ok" if p < 0.3 else "CONTROL(false) FAILED"
            controls_ok &= p < 0.3
        else:
            tag = "verified" if p >= 0.7 else "UNVERIFIED"
        print(f"{c['id']:<20} P(supported)={p:.2f}  {tag:<22} [{', '.join(c['evidence'])}]  {c['claim']}")
    print("controls behaved as expected" if controls_ok else "CONTROLS MISBEHAVED: do not rely on this batch")
    return 0 if controls_ok else 1


if __name__ == "__main__":
    sys.exit(main())
