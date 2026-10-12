#!/usr/bin/env bash
# Run rxzhou's eps.sh for the episodes of one gate set not yet finished, over W workers at nice 10 (CPU only).
#   run_parallel.sh <set> <W>
# Finished = an "one.sh 3 <ep> 退出码" line in logs/<set>.txt or logs/<set>_w<k>.txt; the others' partial outputs are
# removed first. OMP_NUM_THREADS=3 bounds his converter step, which sets no thread count (eight converters at full
# width once pushed a 28-core machine to load 60); his one.sh sets 4 for the retarget and 2 for the alignment check
# itself, so results are unchanged. Workers start 15 s apart.
set -u
G=${T3_GATE:-/lab_data/yqchen/v2d/gate}; R=$G/repo; S=$1; W=$2
done_eps=" $(grep -ho "one.sh 3 [0-9]* 退出码" "$G/logs/$S.txt" "$G"/logs/"${S}"_w[0-9].txt 2>/dev/null | awk '{print $3}' | tr '\n' ' ') "
todo=()
while read -r ep seq; do
  [[ "$done_eps" == *" $ep "* ]] && continue
  todo+=("$ep")
  rm -rf "$R/runs/motion_src/tier3_$S/$seq" "$R/runs/motion/tier3_$S/whole_body/soma/sequence_id=$seq"
  rm -f "$R/runs/logs/batch/t3_${S}_ep$(printf %02d "$ep")".{log,tsv}
done < <("$G/venv/bin/python" -c "import json,sys; [print(m['episode_index'], m['sequence_id']) for m in map(json.loads, open(sys.argv[1]))]" "$R/runs/tier3/root_$S/meta/episodes_metadata.jsonl")
echo "$S todo: ${todo[*]}"
cd "$R"
for ((k = 0; k < W; k++)); do
  mine=(); for ((i = k; i < ${#todo[@]}; i += W)); do mine+=("${todo[$i]}"); done
  [ ${#mine[@]} -eq 0 ] && continue
  OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 PATH=$G/venv/bin:$PATH V2D_T3_SET=$S setsid nohup nice -n 10 \
    stages/retarget/eps.sh 3 "${mine[@]}" > "$G/logs/${S}_w$k.txt" 2>&1 < /dev/null &
  echo "  worker $k: ${mine[*]}"; sleep 15
done
