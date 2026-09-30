"""扫 FlashCHORD policy checkpoint 里的非有限参数（训练机上跑，只用标准库）。

safetensors 格式：8 字节小端头长度 + JSON 头（张量名 → dtype、shape、data_offsets）+ 数据。policy 文件是 31 个 F32 张量。
先确认文件完整（头能解析、文件大小 = 8 + 头长 + 数据末尾，且最后修改已过 10 秒，同 ckpt_latest.py 的判定再加写入余量），
不完整的报“不完整”、不计入。逐个张量用 array('f') 读数据，数 NaN 与 ±inf；非 F32 的张量报出名字、不扫。

用法（仓库根，或经 scripts/dev/pipe-py 在训练机上跑）：
  python3 stages/policy/ckpt_nonfinite.py <run>...          每个 run 的全部 policy_<步数>.safetensors，按步数排
  python3 stages/policy/ckpt_nonfinite.py --last <run>...   每个 run 只看步数最大的一份完整 checkpoint
  python3 stages/policy/ckpt_nonfinite.py --watch <run> [--interval 120] [--timeout 14400] [--stop-after 2]
      看守：每 interval 秒看一次新写完的 policy；按步数连续 stop-after 份完整 checkpoint 都含非有限参数，就调用
      stages/policy/fc_stop.sh <run> 并退出；run 目录已有 DONE 或 STOP 时只报告、不止损（DONE 优先）。到 timeout 秒也退出。
      另每轮数一次本地 .wandb 里的 NaN 字样，变了就报（只报警）。--tag 写部署时的 commit，启动时连同脚本 md5 打出。
      只有 fc_stop.sh 这一个写操作；计划 agent-doc/plan-ep1-ep7-divergence-2026-09-30.md 的 M1、M2。
时间一律丹佛时间（MDT，UTC−6）。类型注解用 typing，Mac 自带的 Python 3.9 也能跑。
"""
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
import time
from array import array
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MDT = timezone(timedelta(hours=-6))
SETTLE_S = 10


def now() -> str:
    return datetime.now(tz=MDT).strftime("%m-%d %H:%M:%S")


def header(path: Path) -> Optional[Tuple[dict, int]]:
    """(头, 数据起点)；文件不完整或还在写返回 None。"""
    try:
        st = path.stat()
        if time.time() - st.st_mtime < SETTLE_S:
            return None
        with path.open("rb") as f:
            raw = f.read(8)
            if len(raw) != 8:
                return None
            (n,) = struct.unpack("<Q", raw)
            if n <= 0 or 8 + n > st.st_size:
                return None
            h = json.loads(f.read(n))
        end = max((v["data_offsets"][1] for k, v in h.items() if k != "__metadata__"), default=0)
        return (h, 8 + n) if st.st_size == 8 + n + end else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def scan(path: Path) -> Optional[dict]:
    """{'total', 'nan', 'inf', 'skipped'}；不完整返回 None。"""
    got = header(path)
    if got is None:
        return None
    h, base = got
    total = nan = inf = 0
    skipped = []
    with path.open("rb") as f:
        for name, v in h.items():
            if name == "__metadata__":
                continue
            if v["dtype"] != "F32":
                skipped.append(name)
                continue
            start, end = v["data_offsets"]
            f.seek(base + start)
            a = array("f")
            a.frombytes(f.read(end - start))
            if sys.byteorder != "little":
                a.byteswap()
            total += len(a)
            for x in a:
                if x != x:
                    nan += 1
                elif math.isinf(x):
                    inf += 1
    return {"total": total, "nan": nan, "inf": inf, "skipped": skipped}


def policies(run: str) -> List[Tuple[int, Path]]:
    out = []
    for p in Path("runs/flash_chord", run).glob("policy_*.safetensors"):
        m = re.fullmatch(r"policy_(\d+)\.safetensors", p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def line(step: int, r: Optional[dict]) -> str:
    if r is None:
        return f"  {step:>11,d} 步：不完整或还在写，跳过"
    bad = r["nan"] + r["inf"]
    s = f"  {step:>11,d} 步：非有限 {bad} / {r['total']}（NaN {r['nan']}，inf {r['inf']}）"
    return s + (f"；未扫的非 F32 张量 {r['skipped']}" if r["skipped"] else "")


def report(runs: List[str], last_only: bool) -> None:
    for run in runs:
        items = policies(run)
        print(f"== {run}（policy {len(items)} 份）")
        if not items:
            print("  没有 policy checkpoint")
            continue
        if last_only:
            for step, p in reversed(items):
                r = scan(p)
                if r is not None:
                    print(line(step, r))
                    break
            else:
                print("  没有完整的 checkpoint")
            continue
        first_bad = None
        for step, p in items:
            r = scan(p)
            print(line(step, r))
            if r is not None and r["nan"] + r["inf"] and first_bad is None:
                first_bad = step
        print(f"  第一份含非有限参数：{first_bad:,d} 步" if first_bad else "  全部有限")


def wandb_nan_count(run: str) -> Optional[int]:
    """最新一个本地 .wandb 文件里 NaN 字样的个数（边训边写；只作报警，不作止损依据）。"""
    files = sorted(Path("runs/flash_chord", run, "wandb").glob("run-*/run-*.wandb"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    try:
        return files[-1].read_bytes().count(b"NaN")
    except OSError:
        return None


def watch(run: str, interval: int, timeout: int, stop_after: int, tag: str) -> int:
    d = Path("runs/flash_chord", run)
    md5 = hashlib.md5(Path(__file__).read_bytes()).hexdigest() if Path(__file__).is_file() else "?"
    print(f"=== {now()} MDT 开始看守 {run}：每 {interval} 秒；连续 {stop_after} 份非有限就 fc_stop；最长 {timeout} 秒；"
          f"脚本 md5 {md5}；{tag}", flush=True)
    seen: Dict[int, bool] = {}
    last_wandb = None
    t0 = time.time()
    while True:
        finished = (d / "DONE").exists() or (d / "STOP").exists()
        for step, p in policies(run):
            if step in seen:
                continue
            r = scan(p)
            if r is None:
                continue
            seen[step] = bool(r["nan"] + r["inf"])
            print(f"{now()} MDT {line(step, r).strip()}", flush=True)
        w = wandb_nan_count(run)
        if w is not None and w != last_wandb:
            print(f"{now()} MDT 报警信号：.wandb 里 NaN 字样 {w} 处（只报不停）", flush=True)
            last_wandb = w
        if finished:  # 已结束的 run 不再止损
            print(f"=== {now()} MDT run 已结束（{'DONE' if (d / 'DONE').exists() else 'STOP'}），扫过 {len(seen)} 份；NAN_WATCH_DONE", flush=True)
            return 0
        steps = sorted(seen)
        tail = [seen[s] for s in steps[-stop_after:]]
        if len(tail) == stop_after and all(tail):
            print(f"=== {now()} MDT 连续 {stop_after} 份非有限（{', '.join(f'{s:,d}' for s in steps[-stop_after:])} 步）：fc_stop {run}", flush=True)
            rc = subprocess.run(["stages/policy/fc_stop.sh", run]).returncode
            print(f"=== {now()} MDT fc_stop 退出码 {rc}；NAN_WATCH_STOPPED", flush=True)
            return 0
        if time.time() - t0 > timeout:
            print(f"=== {now()} MDT 到时，扫过 {len(seen)} 份；NAN_WATCH_TIMEOUT", flush=True)
            return 0
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--last", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=120)
    ap.add_argument("--timeout", type=int, default=14400)
    ap.add_argument("--stop-after", type=int, default=2)
    ap.add_argument("--tag", default="", help="启动时照打，记部署的 commit 等")
    a = ap.parse_args()
    for run in a.runs:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run):
            sys.exit(f"run 名非法：{run}")
    if a.watch:
        if len(a.runs) != 1 or a.stop_after < 1:
            sys.exit("--watch 只看一个 run，--stop-after ≥ 1")
        if not re.fullmatch(r"[A-Za-z0-9_.:=, -]*", a.tag):
            sys.exit("--tag 只能是字母数字与 _.:=, -")
        return watch(a.runs[0], a.interval, a.timeout, a.stop_after, a.tag)
    report(a.runs, a.last)
    return 0


if __name__ == "__main__":
    sys.exit(main())
