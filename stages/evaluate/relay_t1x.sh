#!/usr/bin/env bash
# Tier 1 变体 A 补跑：把 mf4090 上导出 ok 的新候选经 Mac 管道集中到 ml40，并在 ml40 上拼出这一次逐条选的输入目录
# （Mac 上、仓库根执行；Mac 只转发，不计算）。计划 agent-doc/plan-t1-r3x-2026-10-08.md 第 3 节第 5 步。
#   1. mf4090：导出日志 runs/logs/cand_t1_r3x_mf4090.log 的最后一行是 EXPORT_CHAIN_DONE，结果表 runs/exports/cand_t1_r3x_mf4090.tsv 在；
#      stage_t1_candidates.sh 把状态 ok 的候选（1 世界导出的 json、parquet 与 4096 世界评测）抄到 runs/select_t1_r3x_stage/cand，结果表抄到 tables/
#   2. 经 Mac 管道 tar 到 ml40 的 runs/select_t1_r3x/（这个目录已存在就拒绝）
#   3. ml40：10/8 那一次的候选 runs/select_t1/cand/* 硬链接进 runs/select_t1_r3x/cand/，结果表 runs/select_t1/tables/*.tsv 抄进 tables/；
#      新旧候选重名就停；打印候选数与结果表数（10/8 是 48 个候选；新候选全部 ok 时应为 54）与 ep0、ep5、ep15 的新候选名
# 用法（经 record 落盘，审查 m2）：scripts/dev/record ops/relay_t1x_r3x stages/evaluate/relay_t1x.sh
# 中途失败后重跑：先删 mf4090 的 runs/select_t1_r3x_stage 与 ml40 的 runs/select_t1_r3x（只放抄来的副本与硬链接，删了不影响原件）。
set -euo pipefail
cd "$(dirname "$0")/../.."
MF=/home/rxzhou/v2d/maniphys_lab_v2d_challenge; ML=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20)
CLEAN="重跑前删 mf4090 的 runs/select_t1_r3x_stage 与 ml40 的 runs/select_t1_r3x"
stop() { echo "relay_t1x: $*，停" >&2; exit 1; }

"${SSH[@]}" mf4090 "cd $MF && tail -1 runs/logs/cand_t1_r3x_mf4090.log | grep -q EXPORT_CHAIN_DONE && test -f runs/exports/cand_t1_r3x_mf4090.tsv" \
  || stop "mf4090 的导出链还没结束或没有结果表"
"${SSH[@]}" ml40 "cd $ML && test ! -e runs/select_t1_r3x && test -d runs/select_t1/cand" || stop "ml40 上 runs/select_t1_r3x 已存在或缺 runs/select_t1/cand（上次没跑完的话：$CLEAN）"
"${SSH[@]}" mf4090 "cd $MF && test ! -e runs/select_t1_r3x_stage && stages/evaluate/stage_t1_candidates.sh runs/select_t1_r3x_stage/cand runs/exports/cand_t1_r3x_mf4090.tsv \
  && cut -f3,5 runs/exports/cand_t1_r3x_mf4090.tsv" || stop "mf4090 上抄候选失败或 runs/select_t1_r3x_stage 已存在（$CLEAN）"
"${SSH[@]}" mf4090 "cd $MF && tar -C runs/select_t1_r3x_stage -cf - cand tables" \
  | "${SSH[@]}" ml40 "cd $ML && mkdir runs/select_t1_r3x && tar -C runs/select_t1_r3x -xf -" || stop "转发失败（$CLEAN）"
"${SSH[@]}" ml40 "set -e; cd $ML/runs
for d in select_t1/cand/*/; do n=\$(basename \$d); if [ -e select_t1_r3x/cand/\$n ]; then echo 重名 \$n; exit 1; fi; done
cp -al select_t1/cand/. select_t1_r3x/cand/
cp -n select_t1/tables/*.tsv select_t1_r3x/tables/
echo 候选 \$(ls select_t1_r3x/cand | wc -l) 个，结果表 \$(ls select_t1_r3x/tables | wc -l) 张
echo ep0、ep5、ep15 的新候选：\$( (ls select_t1_r3x/cand | grep -E '^t1-ep(0|5|15)-w2048-cap4m-r3a-' || true) | tr '\n' ' ')" || stop "ml40 上拼目录失败（$CLEAN）"
echo RELAY_DONE
