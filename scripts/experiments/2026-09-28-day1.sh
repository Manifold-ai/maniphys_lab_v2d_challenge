#!/usr/bin/env bash
# 重新生成 agent-doc/experiments/2026-09-28-day1.md 引用的全部 results/day1 文件（在 Mac 上、仓库根执行）。
# 每个文件经 scripts/dev/record 落盘，头部带命令、脚本 md5、源码版本、机器与时间；最后回流到本地
# results/day1/（mf4090）与 results/ml40/day1/（ml40）。
# 评测本身不重跑：fc_eval.sh 见到已有的评测 JSON 只打印摘要。要重新评测，先移走对应的 eval_*.json，
# 再在 ml40 上跑 stages/policy/queues/ml40_day1_eval.sh。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -z "$(git status --porcelain -- . ':(exclude)results')" ] || { echo "工作区有未提交的改动，先提交再生成结果" >&2; exit 1; }
R=scripts/dev/remote; REC=scripts/dev/record
MF=runs/flash_chord/t1-ep20-w2048-cap1m-mf4090/policy_349999104.safetensors

# mf4090：不动基线与参考旋转（容器内，不占 GPU）；mf4090 policy 的输入清单；9/25 冒烟评测摘要
$R $REC day1/static_baseline_ep20 scripts/dev/in-flash-chord "python /repo/stages/evaluate/static_baseline.py /repo/$MF --tier1-episode 20"
$R $REC day1/policy_inputs_mf4090policy_on_mf4090 python3 stages/policy/policy_inputs.py "$MF"
$R $REC day1/eval_smoke_t1_ep20_w256_0925 python3 stages/policy/eval_summary.py runs/flash_chord/smoke_t1_ep20_w256/policy_3072000.safetensors.metrics.json

# ml40：三份评测摘要；同一个 mf4090 policy 在 ml40 上的输入清单（与上面那份 diff）；W&B 训练曲线
export V2D_ENV=ml40
$R $REC day1/eval_t1-ep20-w2048-cap10m-ml40 stages/policy/fc_eval.sh t1-ep20-w2048-cap10m-ml40 349999104
$R $REC day1/eval_t1-ep20-w2048-cap1m-mf4090 stages/policy/fc_eval.sh t1-ep20-w2048-cap1m-mf4090 349999104
$R $REC day1/eval_smoke-t1-ep20-w2048-cap10m-ml40_w256 env V2D_EVAL_WORLDS=256 stages/policy/fc_eval.sh smoke-t1-ep20-w2048-cap10m-ml40 4096000
$R $REC day1/policy_inputs_mf4090policy_on_ml40 python3 stages/policy/policy_inputs.py "$MF"
$R $REC day1/wb_summary stages/policy/wb_summary.sh t1-ep20-w2048-cap1m-mf4090-s1 t1-ep20-w2048-cap10m-ml40-s1
unset V2D_ENV

scripts/dev/pull-results
V2D_ENV=ml40 scripts/dev/pull-results
if diff <(grep -E '^sha |files hashed' results/day1/policy_inputs_mf4090policy_on_mf4090.txt) \
        <(grep -E '^sha |files hashed' results/ml40/day1/policy_inputs_mf4090policy_on_ml40.txt); then
  echo "输入清单：mf4090 与 ml40 逐字节一致"
else
  echo "输入清单：两台不一致（见上）" >&2; exit 1
fi
