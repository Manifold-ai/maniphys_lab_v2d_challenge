"""k-fix 方案 4 第 6、7 步的汇总（mf4090 上、仓库根执行，只用标准库；只读评测与导出的 JSON，不读真值）。
计划 agent-doc/plan-t3-kfix-2026-10-16.md 判据 5；清单格式见 stages/evaluate/kfix_reexport.sh。

逐行：
  - 新的 4096 世界指标：runs/flash_chord/<run>/export_8c778f9/s<步数>_w4096<后缀>/episode_<序号>.json（MP-SR = maniptrans_sr，
    SP-SR = spider_sr_uncentered，与 eval_table.py 相同），以及 JSON 里记的参考 parquet；
  - 旧的：runs/flash_chord/<run>/eval_<步数>_w4096.json；
  - idchk 行（恒等核对，跑之前定的）：MP-SR、SP-SR、ADD-AUC 的差都 ≤ 0.005、MPPE 的差 ≤ 0.05 cm，记“包装层恒等”，否则记“包装层不恒等”
    （不恒等时判据 5 的读数不可靠，结果表不写任何行）；
  - kfix 行（判据 5）：旧 MP-SR > 0 时，新 MP-SR ≥ 旧 − 0.05 且新 SP-SR ≥ 旧 − 0.05 记“换”；旧 MP-SR 为 0 时只看 SP-SR；否则“不换”。
    “换”且 1 世界导出的 JSON 与 parquet 都在的，写进结果表（--write-table，格式同 export_chain.sh：tier、episode、run、step、status、json、
    parquet、json_sha256、parquet_sha256），给 pull_submission.sh select 拉回 Mac。
用法：python3 stages/evaluate/kfix_reexport_table.py <清单> [--write-table <结果表>]；最后一行 KFIX_TABLE_DONE <换的集数>。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

COLS = ["tier", "episode", "run", "step", "status", "json", "parquet", "json_sha256", "parquet_sha256"]


def metrics(p: Path) -> dict:
    d = json.loads(p.read_text())
    m = d.get("metrics", d)
    # 评测器把参考 parquet 记在顶层 "parquet"（eval_playback_override.py 就核这一项）
    return {"MP-SR": m["maniptrans_sr"], "SP-SR": m["spider_sr_uncentered"], "ADD-AUC": m["add_auc"], "MPPE": m["mppe_cm"],
            "parquet": d.get("parquet"), "world_count": m.get("world_count", d.get("world_count"))}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("list", type=Path)
    ap.add_argument("--write-table", type=Path)
    a = ap.parse_args()
    rows = [ln.split("\t") for ln in a.list.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("run\t")]
    identity_ok, table = None, []
    for run, step, pq, suf, mode in rows:
        ep = int(re.match(r"t3-ep(\d+)-", run).group(1))
        base = Path("runs/flash_chord") / run
        new_j = base / "export_8c778f9" / f"s{step}_w4096{suf}" / f"episode_{ep:06d}.json"
        old_j = base / f"eval_{step}_w4096.json"
        if not new_j.exists() or not old_j.exists():
            print(f"{run} {mode}：缺 {'新' if not new_j.exists() else '旧'}的 4096 世界 JSON")
            if mode == "idchk":
                identity_ok = False
            continue
        n, o = metrics(new_j), metrics(old_j)
        diff = {k: n[k] - o[k] for k in ("MP-SR", "SP-SR", "ADD-AUC", "MPPE")}
        line = "，".join(f"{k} {o[k]:.3f}→{n[k]:.3f}" for k in ("MP-SR", "SP-SR", "ADD-AUC", "MPPE"))
        print(f"{run} {mode}（世界 {n['world_count']}；参考 {n['parquet']}）：{line}")
        if n["parquet"] and n["parquet"] != pq:
            print(f"  评测 JSON 里的参考不是清单给的那份：{n['parquet']} ≠ {pq}")
            if mode == "idchk":
                identity_ok = False
            continue
        if mode == "idchk":
            identity_ok = all(abs(diff[k]) <= 0.005 for k in ("MP-SR", "SP-SR", "ADD-AUC")) and abs(diff["MPPE"]) <= 0.05
            print(f"  恒等核对：{'包装层恒等' if identity_ok else '包装层不恒等'}（差 " + "、".join(f"{k} {v:+.4f}" for k, v in diff.items()) + "）")
            continue
        if o["MP-SR"] > 0:
            swap = n["MP-SR"] >= o["MP-SR"] - 0.05 and n["SP-SR"] >= o["SP-SR"] - 0.05
            rule = f"MP-SR ≥ {o['MP-SR'] - 0.05:.3f} 且 SP-SR ≥ {o['SP-SR'] - 0.05:.3f}"
        else:
            swap = n["SP-SR"] >= o["SP-SR"] - 0.05
            rule = f"旧 MP-SR 为 0，只看 SP-SR ≥ {o['SP-SR'] - 0.05:.3f}"
        print(f"  判据 5（{rule}）：{'换' if swap else '不换'}")
        exp_dir = base / "export_8c778f9" / f"s{step}_w1{suf}"
        jj, pp = exp_dir / f"episode_{ep:06d}.json", exp_dir / f"episode_{ep:06d}.parquet"
        if swap:
            if jj.exists() and pp.exists():
                table.append(["3", str(ep), run, step, "ok", str(jj), str(pp), sha(jj), sha(pp)])
            else:
                print(f"  1 世界导出不全（{jj.name}、{pp.name}），不写进结果表")
    if identity_ok is not True:
        print("恒等核对没过或没做：结果表不写任何行")
        table = []
    if a.write_table:
        a.write_table.parent.mkdir(parents=True, exist_ok=True)
        a.write_table.write_text("\t".join(COLS) + "\n" + "".join("\t".join(r) + "\n" for r in table), encoding="utf-8")
        print(f"结果表 {a.write_table}：{len(table)} 行")
    print(f"KFIX_TABLE_DONE {len(table)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
