#!/usr/bin/env bash
# r3o 的 G1 评测器兼容门（计划 agent-doc/plan-r3o-2026-10-15.md 2.1，审查第 1 条；训练机上、仓库根执行，放在 tmux 里）。
# 用 v040_p185_nfg_oo 训一条 r3o 冒烟（mf4090_t1oa 里 ep20 那一行的配置与环境变量，400 万步），再用与上游 8c778f9 逐字节相同的副本
# 跑 4096 世界评测（fc_eval.sh）与 kit 参数的 1 局导出（fc_export.sh）。run 名带 -g1-，不与链的冒烟同名。另核三件事：
#   1. 训练日志里有 “V2D object_orientation term: weight=1.0 std=0.4”（环境变量进了容器、副本读到了）；
#   2. checkpoint 元数据存的解析后配置里没有 object_orientation、V2D_OBJ_ORI（8c778f9 读的就是它）；
#   3. 评测与导出都成功（退出码 0、结果文件在）。任何一步不过就停，最后一行 R3O_G1_OK 或 R3O_G1_FAIL <步骤>。
# 用法：stages/policy/r3o_g1.sh            输出看 runs/logs/r3o_g1_mf4090.log（launch 时重定向）
set -uo pipefail
cd "$(dirname "$0")/../.."
R=t1-ep20-w2048-cap4m-r3o-g1-mf4090
FC=/home/rxzhou/v2d/fc_src
ROW="$(grep -v '^[[:space:]]*#' stages/policy/queues/mf4090_t1oa_smoke.txt | grep ' smoke-t1-ep20-w2048-cap4m-r3o-mf4090 ')"
[ -n "$ROW" ] || { echo "R3O_G1_FAIL 找不到 ep20 的冒烟行"; exit 1; }
read -r -a tok <<< "$ROW"; envs=(); i=0
while (( i < ${#tok[@]} )) && [[ ${tok[$i]} =~ ^[A-Z_][A-Z0-9_]*= ]]; do envs+=("${tok[$i]}"); i=$((i + 1)); done
args=("${tok[@]:$((i + 1))}")   # 去掉冒烟的 run 名，换成 $R
echo "=== $(date '+%F %T %Z') G1 开始：$R，环境 ${envs[*]}，来历 $(cat .v2d-source-commit 2>/dev/null)"
env "${envs[@]}" V2D_FC_SRC="$FC/v040_p185_nfg_oo" stages/policy/fc_run.sh "$R" "${args[@]}" < /dev/null \
  || { echo "R3O_G1_FAIL 训练"; exit 1; }
grep -h "V2D object_orientation term: weight=1.0 std=0.4" runs/logs/"$R".s*.log | head -1 | grep -q . \
  || { echo "R3O_G1_FAIL 训练日志里没有 r3o 的开关行"; exit 1; }
echo "=== $(date '+%F %T %Z') 训练完、日志里有 r3o 的开关行"
V2D_FC_SRC="$FC/fc_8c778f9" scripts/dev/in-flash-chord "python - <<'PY'
import json
from safetensors import safe_open
p = '/repo/runs/flash_chord/$R/policy_4096000.safetensors'
with safe_open(p, 'np') as f:
    md = f.metadata()
cfg = md['resolved_config_json']
bad = [k for k in ('object_orientation', 'V2D_OBJ_ORI') if k in cfg]
print('checkpoint 元数据的键：' + ', '.join(sorted(md)))
print('解析后配置里出现的 r3o 字样：' + (', '.join(bad) if bad else '无'))
raise SystemExit(1 if bad else 0)
PY" || { echo "R3O_G1_FAIL checkpoint 配置里带了 r3o 的键"; exit 1; }
V2D_FC_SRC="$FC/fc_8c778f9" stages/policy/fc_eval.sh "$R" 4096000 || { echo "R3O_G1_FAIL 8c778f9 评测"; exit 1; }
[ -f "runs/flash_chord/$R/eval_4096000_w4096.json" ] || { echo "R3O_G1_FAIL 评测结果文件不在"; exit 1; }
echo "=== $(date '+%F %T %Z') 8c778f9 的 4096 世界评测成功"
V2D_FC_SRC="$FC/fc_8c778f9" stages/evaluate/fc_export.sh "$R" 4096000 || { echo "R3O_G1_FAIL 8c778f9 导出"; exit 1; }
ls runs/flash_chord/"$R"/export_8c778f9/s4096000_w1/episode_000020.{json,parquet} > /dev/null || { echo "R3O_G1_FAIL 导出文件不在"; exit 1; }
sha256sum runs/flash_chord/"$R"/export_8c778f9/s4096000_w1/episode_000020.{json,parquet}
echo "=== $(date '+%F %T %Z') 8c778f9 的 1 局导出成功"
echo R3O_G1_OK
