#!/usr/bin/env bash
# Tier 3 queue up to (not including) CARI4D: per episode, automatic masks -> mesh (t3_mesh_ep.sh).
# Serial; before each GPU step waits until the L40S has at least MIN_FREE_MIB free, so it yields to a
# FlashCHORD run (peak ~40 GB of 46 GB) instead of competing with it. Skips episodes already done.
#   setsid nohup t3_queue_mesh.sh [episodes...] > /dev/null 2>&1 &      (default: all 30)
# Progress: logs/t3_queue.log. Stop: kill the process group (pkill -g <pgid>).
set -u
T=/lab_data/yqchen/v2d/tier3
PY=/lab_data/yqchen/v2d/venv/bin/python
MIN_FREE_MIB=${MIN_FREE_MIB:-20000}
QLOG=$T/logs/t3_queue.log
say() { echo "$(date +%m-%d_%T) $*" >> "$QLOG"; }
wait_gpu() {
  while true; do
    free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
    [ "$free" -ge "$MIN_FREE_MIB" ] && return
    say "waiting for GPU: ${free} MiB free < ${MIN_FREE_MIB}"
    sleep 300
  done
}
cd "$T"
eps=${*:-$(seq 0 29)}
for ep in $eps; do
  name=$(python3 -c "import json
for l in open('input/meta/episodes_metadata.jsonl'):
    m=json.loads(l)
    if m['episode_index']==$ep: print('ep%02d_%s' % ($ep, m['object']))")
  W=runs/work/$name
  if [ -f "$W/sam3d_out/scale_report.json" ] && python3 -c "import json,sys; sys.exit(0 if json.load(open('$W/sam3d_out/scale_report.json'))['ok'] else 1)"; then
    say "$name skip: mesh done"; continue
  fi
  wait_gpu
  $PY scripts/t3_masks.py --input input --work runs/work --weights /lab_data/yqchen/v2d/weights --episodes "$ep" > "logs/masks_$name.log" 2>&1
  rc=$?
  if [ -e "$W/NO_AUTO_PROMPT" ]; then say "$name masks rc=$rc NO_AUTO_PROMPT"; continue; fi
  if [ -e "$W/MASK_SUSPECT" ]; then say "$name masks rc=$rc MASK_SUSPECT: $(cat "$W/MASK_SUSPECT")"; continue; fi
  [ "$rc" = 0 ] || { say "$name masks rc=$rc"; continue; }
  say "$name masks ok"
  wait_gpu
  scripts/t3_mesh_ep.sh "$name"
  rc=$?
  rep=$(python3 -c "import json;r=json.load(open('$W/sam3d_out/scale_report.json'));print('ok=%s extents=%s iou=%s depth_ratio=%s %s' % (r['ok'], r['extents_m'], r['projected_box_iou'], r['depth_ratio'], r['why']))" 2>/dev/null)
  say "$name mesh rc=$rc $rep"
done
say "QUEUE DONE"
