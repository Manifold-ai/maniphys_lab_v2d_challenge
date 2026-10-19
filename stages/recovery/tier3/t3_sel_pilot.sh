#!/usr/bin/env bash
# 10-19: pilot of the timeline selection (t3_fp_select.py) on episodes with checked frames, ending in an automatic gate
# (t3_sel_gate.py; criteria registered in the Tier 3 handoff before the run). Unattended:
#   1. waits for each episode's stage-05 dump (runs/work_dump/<ep>/check.json identical, from t3_fp_dump.sh);
#   2. copies runs/work_fp/<ep> to runs/work_sel/<ep> (the source is not touched), clears stages 06-08, rewrites the
#      stage-05 pkl with the selection (stage 05 itself is reused, checked in the CARI4D log);
#   3. holds the GPU (runs/work_dump/GPU_HOLD, set at the start so the dump streams stop right after the pilot
#      episodes' dumps instead of starting their next ~1-2 h episode; stage 07 peaks near 44 GB), waits until no dump container runs, >= 44 GB are free and rxzhou's chain is idle (10-10 rule), runs CARI4D
#      06-08 for all pilot episodes, releases the hold;
#   4. object-only chain for ctrl (convert_fp) and sel as the 10-19 position check (gb4: intrinsics_gb3 focal with the
#      body refit, floor_fit_gb4 + camera_register_gb4, gb4_best supports, dr2s --move-human=3d, dyn7), under $M;
#   5. silhouette IoU every 2nd frame, then the gate.
#   setsid nohup stages/recovery/tier3/t3_sel_pilot.sh ep04_baseball_bat ep03_contigo_coffee_mug > $T/logs/sel_pilot.log 2>&1 &
# Last line: SEL_GATE_PASS, SEL_GATE_FAIL <criteria> or SEL_PILOT_FAILED <step>.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
M=${SEL_REVIEW:-$T/dev/sel_pilot}
P=$M/root
PY=/lab_data/yqchen/v2d/venv/bin/python
GPY=/lab_data/yqchen/v2d/gate/venv/bin/python
A=/lab_data/yqchen/v2d/soma_assets
RX_RUNS=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs
HOLD=$T/runs/work_dump/GPU_HOLD
# SEL_WORK names the selection's work dir (default work_sel; 10-20 work_anchor for the ctrl-anchored rerun, with SEL_REVIEW);
# its CARI4D log is logs/cari4d_<ep>_<SEL_WORK without work_>.log. SEL_FROM_STEP=4 skips steps 1-3 (a test of the chain, gate
# and their hand-offs on an existing work dir, e.g. SEL_WORK=work_init SEL_REVIEW=$T/dev/sel_test).
SEL_WORK=${SEL_WORK:-work_sel}
TAG=${SEL_WORK#work_}
FROM=${SEL_FROM_STEP:-1}
EPS="$*"
KINDS="ctrl sel"
D=(docker run --rm --cpus 8 -e OMP_NUM_THREADS=8 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
log() { echo "$(date '+%m-%d %T') $*"; }
fail() { rm -f "$HOLD"; log "SEL_PILOT_FAILED $*"; exit 1; }
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
dumps_running() { docker ps --filter ancestor=v2d_cari4d:latest --format '{{.Command}}' --no-trunc | grep -c run_foundationpose_mhr_export; }
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
mesh_of() { "$PY" -c "import json; print(next(m['mesh'] for m in map(json.loads, open('$T/input/meta/episodes_metadata.jsonl')) if m['episode_index']==$1))"; }
log "deployed: $(cat "$T/code/DEPLOYED" 2>/dev/null)"
mkdir -p "$M/logs" "$M/report" "$T/runs/$SEL_WORK"
if [ "$FROM" -le 3 ]; then
touch "$HOLD"
log "GPU hold set: the dump streams stop before their next episode"

# 1-2. selection on copies
for name in $EPS; do
  ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep"); c=$T/runs/$SEL_WORK/$name/cari4d/$seq
  until [ -f "$T/runs/work_dump/$name/check.json" ]; do
    pgrep -f "[t]3_fp_dump.sh" > /dev/null || [ -f "$T/runs/work_dump/$name/check.json" ] || fail "$name: no dump stream left and no dump"
    sleep 60
  done
  grep -q '"identical": true' "$T/runs/work_dump/$name/check.json" || fail "$name: dump check not identical"
  if [ ! -f "$c/foundationpose/fp_select.json" ]; then
    rm -rf "$T/runs/$SEL_WORK/$name"; cp -a "$T/runs/work_fp/$name" "$T/runs/$SEL_WORK/$name" || fail "$name: copy"
    rm -f "$c"/.stages/0[678]_*.json "$c"/inference/coconet.pth "$c"/inference/materialized_inputs.h5 \
      "$c"/inference/refined.pth "$c"/inference/refinement_checkpoint.pth "$c"/inference/*.mp4 "$c"/pipeline_report.json
    r=$("${D[@]}" -v "$c":/c -v "$S":/s:ro -v "$T/runs/work_dump/$name":/d:ro -v "$T/input":/in:ro v2d_cari4d:latest \
      python /s/t3_fp_select.py /c "/d/$seq.candidates.npz" "/in/$(mesh_of "$ep")" 2>&1) || fail "$name: t3_fp_select.py: $r"
    log "$name selected: $r"
  fi
done

# 3. CARI4D 06-08 with the whole GPU
log "waiting for the dump streams to finish their current episodes"
while [ "$(dumps_running)" -gt 0 ] || [ "$(free_mib)" -lt 44000 ] || rx_busy; do sleep 60; done
for name in $EPS; do
  ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep")
  [ -f "$T/runs/$SEL_WORK/$name/cari4d/$seq/inference/refined.pth" ] && { log "$name: refined already"; continue; }
  log "$name: CARI4D 06-08"
  T3_WORK=runs/$SEL_WORK T3_FP_MODE=register-every-frame T3_LOG_TAG=_$TAG "$S/t3_cari4d_ep.sh" "$name" || fail "$name: CARI4D (logs/cari4d_${name}_$TAG.log)"
  rerun=$(grep -h -o '0[1-5]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_$TAG.log" | grep -v 'elapsed_seconds=0\.0$' | tr '\n' ' ')
  [ -z "$rerun" ] || fail "$name: CARI4D re-ran earlier stages ($rerun), the selection was overwritten"
  log "$name: $(grep -h -o '0[678]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_$TAG.log" | tr '\n' ' ')"
done
rm -f "$HOLD"
log "GPU hold released"
fi

# 4. object-only chain, ctrl and sel
mkdir -p "$P/runs/physics"
ln -sfn "$T/input" "$P/input"
for e in "$T"/runs/*; do b=$(basename "$e"); [ "$b" = physics ] && continue; [ -e "$P/runs/$b" ] || ln -s "$e" "$P/runs/$b"; done
for name in $EPS; do
  ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep"); mesh=$(mesh_of "$ep")
  for kind in $KINDS; do
    c=$M/conv_$kind/$name
    rm -rf "$c"; mkdir -p "$(dirname "$c")"; cp -a "$T/runs/convert_fp/$name" "$c"
    if [ "$kind" = sel ]; then
      "${D[@]}" -v "$S":/s:ro -v "$T/runs/$SEL_WORK/$name/cari4d/$seq":/e:ro -v "$c":/o v2d_cari4d:latest \
        python /s/t3_sel_decode_object.py /e /o > "$M/logs/decode_$name.log" 2>&1 || fail "$name decode"
    fi
    "${D[@]}" -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$A":/a:ro -v "$T/input":/in:ro -v "$c":/o/"$name" v2d_cari4d:latest \
      python /s/t3_convert_ep.py focal /o/"$name" /f/intrinsics_gb3.json /a "/in/$mesh" > "$M/logs/focal_${kind}_$name.log" 2>&1 || fail "$name $kind focal"
    "${D[@]}" -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$A":/a:ro -v "$c":/o/"$name" v2d_cari4d:latest \
      python /s/t3_convert_ep.py world /o/"$name" /f/floor_fit_gb4.json /a /f/camera_register_gb4.json > "$M/logs/world_${kind}_$name.log" 2>&1 || fail "$name $kind world"
    "$PY" "$S/t3_convert_ep.py" assemble "$c" "$T/input" "$ep" "$P/runs/A_$kind" > "$M/logs/assemble_${kind}_$name.log" 2>&1 || fail "$name $kind assemble"
  done
  log "$name converted"
done
for kind in $KINDS; do
  ln -sfn "$M/conv_$kind" "$P/runs/conv_$kind"
  "$PY" - "$T/runs/tier3_cari4d_gb4_best.selection.json" "$M/sel_$kind.json" "conv_$kind" $EPS <<'EOF' || fail "selection json"
import json, sys
src, dst, conv, eps = sys.argv[1], sys.argv[2], sys.argv[3], set(sys.argv[4:])
rows = [r | {"convert": conv} for r in json.load(open(src)) if r["episode"] in eps]
assert len(rows) == len(eps), rows
json.dump(rows, open(dst, "w"), indent=1)
EOF
done
physics() {
  local v=$1 out=$P/runs/physics/$1
  mkdir -p "$out"
  "$PY" "$S/t3_physics_check.py" extract "$P" "$P/runs/$v" "$out/npz" > "$M/logs/physics_$v.log" 2>&1 || return 1
  "${D[@]}" -v "$S":/s:ro -v "$T":"$T":ro -v "$P":"$P" -v "$A":/a:ro v2d_cari4d:latest \
    python /s/t3_physics_check.py check "$P" "$out/npz" /a "$out/out" >> "$M/logs/physics_$v.log" 2>&1
}
for kind in $KINDS; do
  physics "A_$kind" || fail "physics A_$kind"
  (cd "$P" && "$GPY" "$S/t3_depth_post.py" "$P" "A_$kind" "$M/sel_$kind.json" runs/support/tier3_cari4d_gb4_best \
    "runs/physics/A_$kind" "D_$kind" --move-human=3d) > "$M/logs/depth_post_$kind.log" 2>&1 || fail "depth post $kind"
  physics "D_$kind" || fail "physics D_$kind"
  (cd "$P" && "$GPY" "$S/t3_dynamics_post.py" "$P" "D_$kind" "$P/runs/physics/D_$kind" "Y_$kind") > "$M/logs/dynamics_post_$kind.log" 2>&1 || fail "dynamics post $kind"
  log "post $kind done"
done

# 5. IoU and gate
for name in $EPS; do
  ep=$((10#${name:2:2}))
  docker run --rm --cpus 8 -e OMP_NUM_THREADS=8 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp \
    -e PYTHONPATH=$T/dev/init_pilot/pydeps_cari4d -v "$T":"$T" -v "$S":"$S":ro v2d_cari4d:latest \
    python "$S/t3_sel_iou.py" "$P" "$ep" "$name" 2 A_ctrl A_sel Y_ctrl Y_sel > "$M/report/iou_$name.jsonl" 2> "$M/logs/iou_$name.err" || fail "iou $name"
  log "iou $name done"
done
docker run --rm --cpus 8 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -v "$T":"$T" -v "$S":"$S":ro \
  v2d_cari4d:latest python "$S/t3_sel_gate.py" "$T" "$M" "$SEL_WORK" $EPS 2>&1 | tee "$M/gate.log"
grep -q -E "^SEL_GATE_(PASS|FAIL)" "$M/gate.log" || fail "gate did not finish ($M/gate.log)"
