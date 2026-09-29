"""按 episode 序号生成一段批量训练的期望表与冒烟 / 正式队列（逐帧回放、官方 G1 配方；只用标准库，Mac 上跑）。

序列号取自 results/batch_summary_v040.tsv（Tier 1 行），源帧数取自 results/day2/sequence_stats_tier1.txt，
只有地面的序列（results/day2/empty_support_tier1.txt）加 scene.support=false。格式与 Day 2 / 今晚的队列相同：
冒烟 4,096,000 步、W&B project v2d-selftest、tag smoke；正式 349,999,104 步、tag batch；都带
V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0。ml40 用配方默认的 1000 万 buffer（不写覆盖），mf4090 写 400 万覆盖。
用法：python3 stages/policy/make_batch_queue.py <ml40|mf4090> <段名，如 batch1a> <计划文件> <ep 序号…>
  写出 stages/policy/queues/<机器>_<段名>.expect.tsv、…_smoke.txt、….txt；已存在就拒绝覆盖。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = {"ml40": (10000000, "cap10m", None), "mf4090": (4000000, "cap4m", "training.replay.capacity=4000000")}
SMOKE_ENV = "V2D_WANDB_PROJECT=v2d-selftest V2D_WANDB_TAG=smoke V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0"
FULL_ENV = "V2D_WANDB_TAG=batch V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0"


def main() -> int:
    machine, label, plan, *eps = sys.argv[1:]
    if machine not in CAP or not eps:
        raise SystemExit(__doc__)
    capacity, tag, cap_override = CAP[machine]
    seq_of = {}
    for line in (ROOT / "results/batch_summary_v040.tsv").read_text().splitlines()[1:]:
        f = line.split("\t")
        if f[0] == "1":
            seq_of[int(f[1])] = f[2]
    frames = {}
    for line in (ROOT / "results/day2/sequence_stats_tier1.txt").read_text().splitlines():
        f = line.split("\t")
        if len(f) >= 12 and f[1].isdigit():
            frames[f[0]] = int(f[1])
    empty = {l.strip() for l in (ROOT / "results/day2/empty_support_tier1.txt").read_text().splitlines() if l.strip()}
    q = ROOT / "stages/policy/queues"
    out = {k: q / f"{machine}_{label}{k}" for k in (".expect.tsv", "_smoke.txt", ".txt")}
    for p in out.values():
        if p.exists():
            raise SystemExit(f"{p} 已存在，拒绝覆盖")
    header = (f"# Tier 1 批量 {label}（计划 {plan}）：官方 G1 配方、逐帧回放、{capacity // 10000} 万 buffer（{machine}）；"
              "只有地面的序列 scene.support=false。\n")
    expect = ["run\tsmoke\tsequence_id\tplayback\tsrc_frames\tsupport\tpos_tol\tori_tol\tcapacity\tseed\txeval"]
    smoke_lines, full_lines = [header.rstrip("\n")], [header.rstrip("\n")]
    for ep in (int(e) for e in eps):
        seq = seq_of[ep]
        floor = seq in empty
        run = f"t1-ep{ep}-w2048-{tag}-{machine}"
        parquet = f"/repo/runs/motion/tier1/whole_body/soma/sequence_id={seq}/robot_name=g1/data.parquet"
        extra = " ".join(x for x in (cap_override, "scene.support=false" if floor else None) if x)
        expect.append(f"{run}\tsmoke-{run}\t{seq}\tframe\t{frames[seq]}\t{'false' if floor else 'true'}\t0.015\t0.086\t{capacity}\t42\tno")
        smoke_lines.append(f"{SMOKE_ENV} smoke-{run} {parquet} 2048 4096000" + (f" {extra}" if extra else ""))
        full_lines.append(f"{FULL_ENV} {run} {parquet} 2048 349999104" + (f" {extra}" if extra else ""))
    out[".expect.tsv"].write_text("\n".join(expect) + "\n")
    out["_smoke.txt"].write_text("\n".join(smoke_lines) + "\n")
    out[".txt"].write_text("\n".join(full_lines) + "\n")
    for p in out.values():
        print(f"写出 {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
