#!/usr/bin/env bash
# All checks of one depth_post version: alignment (against the given others), physics, rxzhou's gate, our supports.
#   chain_check.sh <version> <gate set> <alignment versions...>
set -u
V=$1; S=$2; shift 2
T=/lab_data/yqchen/v2d/tier3; G=/lab_data/yqchen/v2d/gate; C=$T/code/stages/recovery/tier3/gate
cd $T
nice -n 10 $G/venv/bin/python code/stages/recovery/tier3/t3_align_check.py $T runs/tier3_cari4d_f830_best.selection.json dev/depth_diag/align_$S.json "$@" $V > dev/depth_diag/align_$S.log 2>&1 &
nice -n 10 code/stages/recovery/tier3/t3_physics_all.sh $V
export T3_GATE=$G
cd $G && venv/bin/python $C/mkroot.py $G/repo $S - $T/runs/$V,$T/runs/${V}_suspect | tail -1
bash $C/run_parallel.sh $S 6
while [ $(ls $G/repo/runs/logs/batch/t3_${S}_ep*.tsv 2>/dev/null | wc -l) -lt 30 ]; do sleep 30; done
while pgrep -f "V2D_T3_SET=$S" > /dev/null; do sleep 10; done
bash $C/mkrecord.sh $S > $G/logs/rec_$S.txt
$G/venv/bin/python $G/repo/stages/retarget/p2_table.py $G/logs/rec_$S.txt --no-contact 29 > $G/logs/p2_$S.txt 2>&1
PYTHONPATH=$G/repo/third_party/video_to_data/robotic_grounding/source/robotic_grounding OMP_NUM_THREADS=4 nice -n 10 \
  $G/venv/bin/python $C/t3_support_usda.py $G/repo $S $T/runs/support/tier3_cari4d_f830_best_v2 $T $G/support_usda_$S > $G/logs/support_usda_$S.txt 2>&1
OMP_NUM_THREADS=2 nice -n 10 bash $C/support_recheck.sh $S $G/support_usda_$S > $G/logs/oursup_$S.txt 2>&1
wait
echo CHAIN_DONE
