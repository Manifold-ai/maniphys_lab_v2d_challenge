#!/usr/bin/env bash
# FlashCHORD G1 训练（在 FlashCHORD 容器内执行，经 scripts/dev/in-flash-chord 调用）。
# 用法：stages/policy/fc_train.sh <parquet> <world_count> <total_env_steps> <输出目录> [额外 hydra 覆盖...]
# parquet 路径含 '='（sequence_id=/robot_name= 分区），Hydra 要求整体加单引号，写在脚本里免得多层转义吃掉。
set -euo pipefail
PARQ=$1; W=$2; STEPS=$3; OUT=$4; shift 4
cd /workspace
exec python scripts/train_flash_sac.py experiment=g1_recon_body_flash_sac \
  "task.parquet='${PARQ}'" "scene.world_count=${W}" "training.total_environment_steps=${STEPS}" \
  reset.seed=42 logging.mode=disabled "output_dir=${OUT}" "$@"
