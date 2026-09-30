"""扫训练日志末尾的 W&B 摘要，找训练发散（NaN）的 run（训练机上跑，只用标准库）。

FlashCHORD 训练结束时 wandb 在日志里打一段 "Run summary"：`wandb: <指标> <值>`。发散的 run 里动作均值、熵、回报变成 nan，
混合精度的 loss_scale 掉到 0。逐个看 runs/logs/*.s1.log，报出三项里有 nan 的 run，附 loss_scale 与回合平均长度。
还在跑的 run 没有摘要，不在此列（发散要看 checkpoint，见 ckpt_nonfinite.py）。

用法（仓库根）：python3 stages/policy/train_nan_scan.py
  Mac 上：scripts/dev/record <名字> scripts/dev/pipe-py stages/policy/train_nan_scan.py（V2D_ENV 选机器）
"""
import re
from pathlib import Path

NAN_KEYS = (
    "policy/action_abs_mean_per_env_action",
    "policy/entropy_mean_per_actor_update",
    "episode/return_mean_per_completed_episode",
)
EXTRA_KEYS = ("mixed_precision/loss_scale", "episode/length_mean_per_completed_episode")
LINE = re.compile(r"^wandb:\s+(\S+)\s+(\S+)\s*$")


def summary(path: Path) -> dict[str, str]:
    """最后一段 Run summary 里的 指标 → 值（字符串）。"""
    out: dict[str, str] = {}
    in_summary = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("wandb: Run summary:"):
            in_summary, out = True, {}
            continue
        if in_summary:
            m = LINE.match(line)
            if m:
                out[m.group(1)] = m.group(2)
            elif not line.startswith("wandb:") or line.strip() == "wandb:":
                in_summary = False
    return out


def main() -> None:
    logs = sorted(Path("runs/logs").glob("*.s1.log"))
    with_summary = 0
    hits = []
    for p in logs:
        s = summary(p)
        if not s:
            continue
        with_summary += 1
        nan = [k for k in NAN_KEYS if s.get(k, "").lower() == "nan"]
        if nan:
            hits.append((p, nan, s))
    for p, nan, s in hits:
        extra = "，".join(f"{k.split('/')[-1]}={s.get(k, '—')}" for k in EXTRA_KEYS)
        print(f"NaN：{p.name}  {len(nan)} 项（{'、'.join(k.split('/')[-1] for k in nan)}）；{extra}")
    print(f"训练日志 {len(logs)} 个，其中带 W&B 摘要 {with_summary} 个；摘要里有 NaN 的 {len(hits)} 个")


if __name__ == "__main__":
    main()
