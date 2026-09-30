"""解析 FlashCHORD 训练在本地写的 W&B 记录（run-*.wandb），找各指标第一次出现非有限值的位置（Mac 上用 uv 带 wandb 跑）。

W&B 边训边把每一行 history 写进 run 目录的 run-<id>.wandb（protobuf 记录，LevelDB 日志格式），不需要 W&B API 与凭据。
读法：wandb.sdk.internal.datastore.DataStore 逐条取记录，解析成 wandb_internal_pb2.Record，只看 history 记录。
每个指标报：第一次非有限（nan / inf）的行号与环境步数、之前最后一个有限值、之后有没有恢复。环境步数取 --step-key 指定的指标
（默认 `_step`：FlashCHORD 把环境步数记成 W&B 的 step，每行约 2048 世界 × 25 步 = 51,200 步）。另把 --around 列出的指标在最早发散行前后几行的值打出来。

用法：uv run --no-project --with wandb==0.22.2 python stages/policy/wandb_local_history.py [--keys] [--around KEY ...] <run-*.wandb>...
  --keys：只列出指标名与行数（先看有哪些键）
计划 agent-doc/plan-ep1-ep7-divergence-2026-09-30.md 的 C3。
"""
import argparse
import json
import math
from pathlib import Path

from wandb.proto import wandb_internal_pb2
from wandb.sdk.internal import datastore

DEFAULT_AROUND = (
    "curriculum/stage_index",
    "curriculum/voc_scale",
    "mixed_precision/loss_scale",
    "episode/length_mean_per_completed_episode",
    "episode/return_mean_per_completed_episode",
    "policy/action_abs_mean_per_env_action",
)


def rows(path: Path) -> list[dict]:
    ds = datastore.DataStore()
    ds.open_for_scan(str(path))
    out = []
    while True:
        data = ds.scan_data()
        if data is None:
            break
        rec = wandb_internal_pb2.Record()
        rec.ParseFromString(data)
        if rec.WhichOneof("record_type") != "history":
            continue
        row = {}
        for item in rec.history.item:
            key = item.key or "/".join(item.nested_key)
            try:
                row[key] = json.loads(item.value_json)
            except json.JSONDecodeError:
                row[key] = item.value_json
        if rec.history.HasField("step"):
            row.setdefault("_step", rec.history.step.num)
        out.append(row)
    return out


def numeric(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt(v) -> str:
    if not numeric(v):
        return "—" if v is None else str(v)
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    return f"{v:.6g}"


def analyse(path: Path, around: list[str], step_key: str | None, list_keys: bool) -> None:
    hist = rows(path)
    keys = sorted({k for r in hist for k in r})
    print(f"== {path.name}：history {len(hist)} 行，指标 {len(keys)} 个")
    if list_keys:
        for k in keys:
            n = sum(1 for r in hist if k in r)
            print(f"  {k}  （{n} 行）")
        return
    if step_key is None:
        step_key = "_step" if "_step" in keys else None
    print(f"  环境步数取自：{step_key or '（没找到，只报行号）'}")

    def env_step(i: int):
        if step_key is None:
            return None
        for j in range(i, -1, -1):  # 这一行没记步数就往前找最近的一行
            v = hist[j].get(step_key)
            if numeric(v):
                return v
        return None

    first_bad = {}
    for k in keys:
        last_ok = None
        for i, r in enumerate(hist):
            v = r.get(k)
            if not numeric(v):
                continue
            if math.isfinite(v):
                last_ok = (i, v)
                continue
            later_ok = any(numeric(r2.get(k)) and math.isfinite(r2.get(k)) for r2 in hist[i + 1:])
            first_bad[k] = (i, v, last_ok, later_ok)
            break
    if not first_bad:
        print("  所有指标全程有限")
        return
    print(f"  出现过非有限值的指标 {len(first_bad)} 个（按第一次出现的行排序）：")
    for k, (i, v, last_ok, later_ok) in sorted(first_bad.items(), key=lambda kv: kv[1][0]):
        es = env_step(i)
        prev = f"之前最后有限值 {fmt(last_ok[1])}（第 {last_ok[0]} 行）" if last_ok else "之前没有有限值"
        print(f"    第 {i} 行{f'（环境步数 {es:,.0f}）' if numeric(es) else ''}：{k} = {fmt(v)}；{prev}；之后{'有' if later_ok else '没有'}恢复")
    onset = min(i for i, *_ in first_bad.values())
    lo, hi = max(0, onset - 4), min(len(hist), onset + 2)
    show = [k for k in around if k in keys]
    print(f"  最早发散在第 {onset} 行；第 {lo}–{hi - 1} 行的关键指标：")
    for i in range(lo, hi):
        es = env_step(i)
        vals = "；".join(f"{k.split('/')[-1]}={fmt(hist[i].get(k))}" for k in show)
        print(f"    第 {i} 行{f'（{es:,.0f} 步）' if numeric(es) else ''}：{vals}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--keys", action="store_true")
    ap.add_argument("--around", nargs="*", default=list(DEFAULT_AROUND))
    ap.add_argument("--step-key", default=None)
    a = ap.parse_args()
    for f in a.files:
        analyse(f, a.around, a.step_key, a.keys)


if __name__ == "__main__":
    main()
