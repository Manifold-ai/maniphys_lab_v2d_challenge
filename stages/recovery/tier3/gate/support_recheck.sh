#!/usr/bin/env bash
# Re-judge one gate set's gap against other supports without a new retarget (the retarget does not read them): rxzhou's
# check_support_alignment.py on each episode's retarget output with <usda dir>/<sequence>_support.usda.
#   support_recheck.sh <set> <usda dir>   (usda dir: t3_support_usda.py's output for the same set)
set -u
S=$1; U=$(cd "$2" && pwd); G=${T3_GATE:-/lab_data/yqchen/v2d/gate}
cd "$G/repo"
while read -r ep seq sup; do
  part="/repo/runs/motion/tier3_$S/whole_body/soma/sequence_id=$seq/robot_name=g1"
  echo "$ep $(OMP_NUM_THREADS=2 scripts/dev/incontainer stages/retarget/check_support_alignment.py "$part" "$U/$(basename "$sup")" 2>&1 | grep -a "^RESULT")"
done < <("$G/venv/bin/python" -c "import json,sys; [print(m['episode_index'], m['sequence_id'], m['support_surface']) for m in map(json.loads, open(sys.argv[1]))]" "$G/repo/runs/tier3/root_$S/meta/episodes_metadata.jsonl")
