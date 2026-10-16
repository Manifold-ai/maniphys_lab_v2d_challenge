"""kfix_reexport_table.py 的测试（暂无契约 ID：运行规范待成文；计划 agent-doc/plan-t3-kfix-2026-10-16.md 判据 5）。只用标准库，在 Mac 上跑。
临时目录里造 runs/flash_chord/<run>/ 的旧评测 JSON、新的 4096 世界 JSON 与 1 世界导出：
  1. 恒等核对过（差 0）：ep0 新分数在门槛内 → 换，写进结果表（sha256 对）；ep18 MP-SR 掉 0.06 → 不换；ep29 旧 MP-SR 为 0、SP-SR 只掉 0.04 → 换；
     ep24 判“换”但 1 世界导出缺 parquet → 不写表；ep26 评测 JSON 记的参考不是清单的 → 作废、不写表；
  2. 恒等核对不过（idchk 的 MP-SR 差 0.02）→ 结果表一行也不写；
  3. 没有 idchk 的 4096 世界 JSON → 同样一行也不写。
用法：python3 stages/evaluate/test_kfix_reexport_table.py；最后一行 ALL_OK。
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "kfix_reexport_table.py"
STEP = "349999104"


def wj(p: Path, mp: float, sp: float, auc: float = 0.5, mppe: float = 3.0, parquet: str | None = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    d = {"metrics": {"maniptrans_sr": mp, "spider_sr_uncentered": sp, "add_auc": auc, "mppe_cm": mppe, "world_count": 4096}}
    if parquet:
        d["parquet"] = parquet
    p.write_text(json.dumps(d))


def build(root: Path, idchk_mp: float = 0.999, with_idchk: bool = True) -> Path:
    rows = ["run\tstep\tparquet\tsuffix\tmode"]
    old = {0: (0.965, 0.992), 18: (0.862, 0.938), 24: (0.933, 0.995), 26: (0.999, 0.999), 29: (0.0, 0.713)}
    new = {0: (0.95, 0.99), 18: (0.80, 0.93), 24: (0.93, 0.99), 26: (0.99, 0.99), 29: (0.0, 0.673)}
    for e, (mp, sp) in old.items():
        run = f"t3-ep{e}-w2048-cap4m-r3a-v2-mf4090"
        base = root / "runs/flash_chord" / run
        wj(base / f"eval_{STEP}_w4096.json", mp, sp)
        pq = f"/repo/runs/motion/tier3_kfix/seq{e}/robot_name=g1/data.parquet"
        nm, ns = new[e]
        wj(base / "export_8c778f9" / f"s{STEP}_w4096_kfixgb" / f"episode_{e:06d}.json", nm, ns,
           parquet=("/repo/runs/motion/tier3_v2/wrong/data.parquet" if e == 26 else pq))
        exp = base / "export_8c778f9" / f"s{STEP}_w1_kfixgb"
        exp.mkdir(parents=True, exist_ok=True)
        (exp / f"episode_{e:06d}.json").write_text(f"json{e}")
        if e != 24:
            (exp / f"episode_{e:06d}.parquet").write_bytes(f"pq{e}".encode())
        rows.append(f"{run}\t{STEP}\t{pq}\t_kfixgb\tkfix")
    run26 = "t3-ep26-w2048-cap4m-r3a-v2-mf4090"
    oldpq = "/repo/runs/motion/tier3_v2/seq26/robot_name=g1/data.parquet"
    if with_idchk:
        wj(root / "runs/flash_chord" / run26 / "export_8c778f9" / f"s{STEP}_w4096_idchk" / "episode_000026.json", idchk_mp, 0.999, parquet=oldpq)
    rows.insert(1, f"{run26}\t{STEP}\t{oldpq}\t_idchk\tidchk")
    lst = root / "list.tsv"
    lst.write_text("\n".join(rows) + "\n")
    return lst


def run(root: Path, lst: Path) -> tuple:
    r = subprocess.run([sys.executable, str(TOOL), str(lst), "--write-table", "runs/exports/kfix.tsv"], cwd=root, capture_output=True, text=True, check=False)
    table = (root / "runs/exports/kfix.tsv").read_text().splitlines() if (root / "runs/exports/kfix.tsv").exists() else []
    return r, table


def test_normal() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        r, table = run(root, build(root))
        assert r.returncode == 0 and "包装层恒等" in r.stdout, r.stdout + r.stderr
        eps = sorted(int(ln.split("\t")[1]) for ln in table[1:])
        assert eps == [0, 29], (eps, r.stdout)
        row0 = next(ln.split("\t") for ln in table[1:] if ln.split("\t")[1] == "0")
        assert row0[7] == hashlib.sha256(b"json0").hexdigest() and row0[8] == hashlib.sha256(b"pq0").hexdigest()
        assert "参考不是清单给的那份" in r.stdout and "1 世界导出不全" in r.stdout
        assert r.stdout.strip().splitlines()[-1] == "KFIX_TABLE_DONE 2"
    print("  1. 恒等核对过：ep0、ep29 换并写表（sha256 对），ep18 不换，ep24 导出不全不写，ep26 参考不对作废")


def test_identity_fail() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        r, table = run(root, build(root, idchk_mp=0.979))
        assert "包装层不恒等" in r.stdout and len(table) == 1, r.stdout
    print("  2. 恒等核对不过：结果表只有表头")
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        r, table = run(root, build(root, with_idchk=False))
        assert len(table) == 1 and "结果表不写任何行" in r.stdout, r.stdout
    print("  3. 没有恒等核对的结果：结果表只有表头")


if __name__ == "__main__":
    test_normal()
    test_identity_fail()
    print("ALL_OK")
