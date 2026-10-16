"""k-fix 方案 4 第 6、7 步的汇总（mf4090 上、仓库根执行，只用标准库；只读评测与导出的 JSON，不读真值）。
计划 agent-doc/plan-t3-kfix-2026-10-16.md 判据 5；清单格式见 stages/evaluate/kfix_reexport.sh。

为什么分两道核对：10/11 那次旧评测（stages/policy/fc_eval.sh）挂的是 third_party 的 flash_chord v0.4.0，现在的评测与导出走 fc_8c778f9
（v0.4.0 加补丁，改了 11 个文件）。把“包装层改不改结果”与“评测器版本改不改结果”分开：
  - 包装层恒等：同一个评测器（fc_8c778f9）上，idchk 行（这条 run 原来的参考经 eval_playback_override.py）与 plain 行（同一 run、不换参考的普通
    路径）比，两份 JSON 记的参考都要是清单给的那份，MP-SR、SP-SR、ADD-AUC 的差都 ≤ 0.005、MPPE 的差 ≤ 0.05 cm，记“包装层恒等”，否则
    “包装层不恒等”（结果表不写任何行）；
  - 评测器一致：plain 行与 10/11 的 eval_<步数>_w4096.json 比，同一套容差，记“评测器一致”或“评测器不一致”（10/11 那份记的参考不是清单给的，
    按不一致处理）；不一致时判据 5 的旧值改用同一评测器的 plain 评测，kfix_reexport.sh 会给每条 kfix 行先补一条 plain。
kfix 行（判据 5）：旧值优先取 s<步数>_w4096_plain 的 JSON（同一评测器），没有才取 10/11 的；旧 MP-SR > 0 时新 MP-SR ≥ 旧 − 0.05 且新 SP-SR ≥ 旧 − 0.05
记“换”，旧 MP-SR 为 0 时只看 SP-SR；“换”且 1 世界导出的 JSON 与 parquet 都在的，写进结果表（--write-table，格式同 export_chain.sh），给
pull_submission.sh select 拉回 Mac。新指标取 s<步数>_w4096<后缀>/episode_<序号>.json（MP-SR = maniptrans_sr，SP-SR = spider_sr_uncentered，同 eval_table.py），
并核 JSON 里记的参考 parquet 就是清单给的那份（plain 行除外）。
--check：只做两道核对、不判 kfix 行、不写表（kfix_reexport.sh 在 idchk 行评完后调），最后一行 KFIX_CHECK 恒等|不恒等 一致|不一致|缺。
用法：python3 stages/evaluate/kfix_reexport_table.py <清单> [--write-table <结果表>] [--check]；最后一行 KFIX_TABLE_DONE <换的集数>。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

COLS = ["tier", "episode", "run", "step", "status", "json", "parquet", "json_sha256", "parquet_sha256"]
KEYS = ("MP-SR", "SP-SR", "ADD-AUC", "MPPE")


def metrics(p: Path) -> dict:
    d = json.loads(p.read_text())
    m = d.get("metrics", d)
    # 评测器把参考 parquet 记在顶层 "parquet"（eval_playback_override.py 就核这一项）
    return {"MP-SR": m["maniptrans_sr"], "SP-SR": m["spider_sr_uncentered"], "ADD-AUC": m["add_auc"], "MPPE": m["mppe_cm"],
            "parquet": d.get("parquet"), "world_count": m.get("world_count", d.get("world_count"))}


def same(a: dict, b: dict) -> bool:
    return all(abs(a[k] - b[k]) <= 0.005 for k in ("MP-SR", "SP-SR", "ADD-AUC")) and abs(a["MPPE"] - b["MPPE"]) <= 0.05


def diffs(a: dict, b: dict) -> str:
    return "、".join(f"{k} {a[k] - b[k]:+.4f}" for k in KEYS)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def j4096(run: str, step: str, suf: str, ep: int) -> Path:
    return Path("runs/flash_chord") / run / "export_8c778f9" / f"s{step}_w4096{suf}" / f"episode_{ep:06d}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("list", type=Path)
    ap.add_argument("--write-table", type=Path)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    rows = [ln.split("\t") for ln in a.list.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("run\t")]
    ep_of = lambda run: int(re.match(r"t3-ep(\d+)-", run).group(1))
    plain = {r[0]: r for r in rows if r[4] == "plain"}
    idchk = [r for r in rows if r[4] == "idchk"]
    identity, drift = None, None
    for run, step, pq, suf, _ in idchk:
        ep = ep_of(run)
        pr = plain.get(run)
        jp = j4096(run, step, pr[3], ep) if pr else None
        ji, jo = j4096(run, step, suf, ep), Path("runs/flash_chord") / run / f"eval_{step}_w4096.json"
        if not (jp and jp.exists() and ji.exists()):
            print(f"{run}：缺 plain 或 idchk 的 4096 世界 JSON，恒等核对没法做")
            identity = False
            continue
        mp, mi = metrics(jp), metrics(ji)
        if mi["parquet"] != pq or mp["parquet"] != pq:
            print(f"  idchk 与 plain 的评测 JSON 记的参考（{mi['parquet']}、{mp['parquet']}）要都是清单给的 {pq}")
            identity = False
            continue
        identity = same(mi, mp)
        print(f"恒等核对：{'包装层恒等' if identity else '包装层不恒等'}（{run}，idchk − plain：{diffs(mi, mp)}）")
        if jo.exists():
            mo = metrics(jo)
            if mo["parquet"] != pq:
                drift = True  # 参考不同就不可比，按不一致处理：判据 5 的旧值都改用同一评测器的 plain
                print(f"评测器核对：10/11 的评测记的参考 {mo['parquet']} 不是 {pq}，不可比，按评测器不一致处理")
            else:
                drift = not same(mp, mo)
                print(f"评测器核对：{'评测器不一致' if drift else '评测器一致'}（plain − 10/11 的评测：{diffs(mp, mo)}）")
    if a.check:
        print(f"KFIX_CHECK {'恒等' if identity else '不恒等'} {'缺' if drift is None else ('不一致' if drift else '一致')}")
        return 0
    table = []
    for run, step, pq, suf, mode in rows:
        if mode != "kfix":
            continue
        ep = ep_of(run)
        new_j = j4096(run, step, suf, ep)
        old_plain = j4096(run, step, "_plain", ep)
        old_j = old_plain if old_plain.exists() else Path("runs/flash_chord") / run / f"eval_{step}_w4096.json"
        if not new_j.exists() or not old_j.exists():
            print(f"{run}：缺{'新' if not new_j.exists() else '旧'}的 4096 世界 JSON")
            continue
        n, o = metrics(new_j), metrics(old_j)
        print(f"{run}（旧值取 {'同一评测器的 plain' if old_j == old_plain else '10/11 的评测'}；新参考 {n['parquet']}）："
              + "，".join(f"{k} {o[k]:.3f}→{n[k]:.3f}" for k in KEYS))
        if n["parquet"] != pq:
            print(f"  评测 JSON 里的参考不是清单给的那份：{n['parquet']} ≠ {pq}")
            continue
        if drift and old_j != old_plain:
            print("  评测器不一致而这一集没有 plain 评测，不判")
            continue
        if o["MP-SR"] > 0:
            swap = n["MP-SR"] >= o["MP-SR"] - 0.05 and n["SP-SR"] >= o["SP-SR"] - 0.05
            rule = f"MP-SR ≥ {o['MP-SR'] - 0.05:.3f} 且 SP-SR ≥ {o['SP-SR'] - 0.05:.3f}"
        else:
            swap = n["SP-SR"] >= o["SP-SR"] - 0.05
            rule = f"旧 MP-SR 为 0，只看 SP-SR ≥ {o['SP-SR'] - 0.05:.3f}"
        print(f"  判据 5（{rule}）：{'换' if swap else '不换'}")
        exp_dir = Path("runs/flash_chord") / run / "export_8c778f9" / f"s{step}_w1{suf}"
        jj, pp = exp_dir / f"episode_{ep:06d}.json", exp_dir / f"episode_{ep:06d}.parquet"
        if swap:
            if jj.exists() and pp.exists():
                table.append(["3", str(ep), run, step, "ok", str(jj), str(pp), sha(jj), sha(pp)])
            else:
                print(f"  1 世界导出不全（{jj.name}、{pp.name}），不写进结果表")
    if identity is not True:
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
