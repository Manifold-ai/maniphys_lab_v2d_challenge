#!/usr/bin/env bash
# 10-20: A/B of t3_fp_select.py's anchor weight BETA, judged by an automatic metric (registered in the Tier 3 handoff
# before the run; the checked frames only evaluate afterwards). Unattended:
#   1. per BETA and episode, runs/work_<tag> = copy of runs/work_fp with stages 06-08 cleared and the selection written
#      (t3_fp_select.py --beta); BETA 0 reuses runs/work_sel (the 10-19 pilot, the same selection) where it has 06-08;
#   2. one GPU hold for all CARI4D 06-08 runs (runs/work_dump/GPU_HOLD: the dump streams stop after their current
#      episode), each started only when rxzhou's chain is idle (10-10 rule) and >= 44 GB are free;
#   3. per BETA, t3_sel_pilot.sh from step 4 (object chain, IoU, gate) into $T/dev/beta_ab/<tag>;
#   4. t3_beta_ab_summary.py: the registered judge and the evaluation on the checked frames.
#   setsid nohup stages/recovery/tier3/t3_beta_ab.sh > $T/logs/beta_ab.log 2>&1 &
# Last line: BETA_AB_DONE or BETA_AB_FAILED <step>.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
R=$T/dev/beta_ab
HOLD=$T/runs/work_dump/GPU_HOLD
RX_RUNS=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs
BETAS=${BETAS:-"0 0.1 0.2 0.3 0.5"}
EPS=${EPS:-"ep03_contigo_coffee_mug ep04_baseball_bat ep13_snack_box"}
D=(docker run --rm --cpus 8 -e OMP_NUM_THREADS=8 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
log() { echo "$(date '+%m-%d %T') $*"; }
fail() { rm -f "$HOLD"; log "BETA_AB_FAILED $*"; exit 1; }
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
dumps_running() { docker ps --filter ancestor=v2d_cari4d:latest --format '{{.Command}}' --no-trunc | grep -c run_foundationpose_mhr_export; }
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
tag() { printf 'b%03d' "$(awk "BEGIN{printf \"%d\", $1 * 100 + 0.5}")"; }
mesh_of() { /lab_data/yqchen/v2d/venv/bin/python -c "import json; print(next(m['mesh'] for m in map(json.loads, open('$T/input/meta/episodes_metadata.jsonl')) if m['episode_index']==$1))"; }
log "deployed: $(cat "$T/code/DEPLOYED" 2>/dev/null)"
mkdir -p "$R"
touch "$HOLD"
log "GPU hold set"

# 1. selections
for b in $BETAS; do
  tg=$(tag "$b"); W=$T/runs/work_$tg; mkdir -p "$W"
  for name in $EPS; do
    ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep"); c=$W/$name/cari4d/$seq
    [ -f "$c/foundationpose/fp_select.json" ] && { log "$tg $name: selected already"; continue; }
    if [ "$tg" = b000 ] && [ -f "$T/runs/work_sel/$name/cari4d/$seq/inference/refined.pth" ]; then
      cp -a "$T/runs/work_sel/$name" "$W/$name" || fail "$tg $name: copy work_sel"
      log "$tg $name: from work_sel (10-19 pilot)"
      continue
    fi
    [ -f "$T/runs/work_dump/$name/check.json" ] && grep -q '"identical": true' "$T/runs/work_dump/$name/check.json" || fail "$name: no checked dump"
    rm -rf "$W/$name"; cp -a "$T/runs/work_fp/$name" "$W/$name" || fail "$tg $name: copy"
    rm -f "$c"/.stages/0[678]_*.json "$c"/inference/coconet.pth "$c"/inference/materialized_inputs.h5 \
      "$c"/inference/refined.pth "$c"/inference/refinement_checkpoint.pth "$c"/inference/*.mp4 "$c"/pipeline_report.json
    r=$("${D[@]}" -v "$c":/c -v "$S":/s:ro -v "$T/runs/work_dump/$name":/d:ro -v "$T/input":/in:ro v2d_cari4d:latest \
      python /s/t3_fp_select.py /c "/d/$seq.candidates.npz" "/in/$(mesh_of "$ep")" "--beta=$b" 2>&1) || fail "$tg $name: select: $r"
    log "$tg $name selected: $(echo "$r" | tail -1 | cut -c1-300)"
  done
done

# 2. CARI4D 06-08
log "waiting for the dump streams to finish their current episodes"
for b in $BETAS; do
  tg=$(tag "$b")
  for name in $EPS; do
    ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep")
    [ -f "$T/runs/work_$tg/$name/cari4d/$seq/inference/refined.pth" ] && { log "$tg $name: refined already"; continue; }
    while [ "$(dumps_running)" -gt 0 ] || [ "$(free_mib)" -lt 44000 ] || rx_busy; do sleep 60; done
    log "$tg $name: CARI4D 06-08"
    T3_WORK=runs/work_$tg T3_FP_MODE=register-every-frame T3_LOG_TAG=_$tg "$S/t3_cari4d_ep.sh" "$name" || fail "$tg $name: CARI4D (logs/cari4d_${name}_$tg.log)"
    rerun=$(grep -h -o '0[1-5]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_$tg.log" | grep -v 'elapsed_seconds=0\.0$' | tr '\n' ' ')
    [ -z "$rerun" ] || fail "$tg $name: CARI4D re-ran earlier stages ($rerun)"
    log "$tg $name: $(grep -h -o '0[678]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_$tg.log" | tr '\n' ' ')"
  done
done
rm -f "$HOLD"
log "GPU hold released"

# 3. object chain, IoU, gate per BETA
for b in $BETAS; do
  tg=$(tag "$b")
  SEL_FROM_STEP=4 SEL_WORK=work_$tg SEL_REVIEW=$R/$tg "$S/t3_sel_pilot.sh" $EPS > "$R/$tg.log" 2>&1
  grep -q -E "^SEL_GATE_(PASS|FAIL)" "$R/$tg/gate.log" 2>/dev/null || fail "$tg: chain or gate ($R/$tg.log)"
  log "$tg: $(tail -1 "$R/$tg/gate.log")"
done

# 4. judge and evaluation
docker run --rm --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -v "$T":"$T" -v "$S":/s:ro v2d_cari4d:latest \
  python /s/t3_beta_ab_summary.py "$R" $(for b in $BETAS; do echo "$b=$(tag "$b")"; done) > "$R/summary.txt" 2>&1 || fail "summary"
cat "$R/summary.txt"
log "BETA_AB_DONE"
