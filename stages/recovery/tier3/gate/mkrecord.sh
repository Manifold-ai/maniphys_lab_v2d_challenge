#!/usr/bin/env bash
# Assemble one gate set's per-episode results into the record p2_table.py reads (what eps.sh prints under his
# scripts/dev/record: command header, result rows, per-episode sole-Z lines, EPS_DONE).
#   mkrecord.sh <set> > record.txt;  python <gate repo>/stages/retarget/p2_table.py record.txt --no-contact 29
set -u
S=$1; B=${T3_GATE:-/lab_data/yqchen/v2d/gate}/repo/runs/logs/batch
EPS=$(seq 0 29 | tr '\n' ' ')
echo "# command  : stages/retarget/eps.sh 3 ${EPS% }"
echo "# note     : assembled by mkrecord.sh from parallel eps.sh workers"
echo "## 结果行（档位 ep 序列 帧数 fps 左手接触 右手接触 IK中位 间隙mm 支撑面 状态）"
for e in $EPS; do cat "$B/t3_${S}_ep$(printf %02d "$e").tsv"; done
for e in $EPS; do
  f="runs/logs/batch/t3_${S}_ep$(printf %02d "$e").log"; echo "## ${f}（脚底高度与最后 15 行）"
  grep -a "Saved robot sole Z range" "$B/${f##*/}" | tail -n 1 | cut -c1-300
done
echo EPS_DONE
