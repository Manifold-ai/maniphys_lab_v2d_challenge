#!/usr/bin/env bash
# 10-19: after the selection pilot's gate passes (logs/sel_pilot.log: SEL_GATE_PASS), the timeline selection on every
# episode whose best pick is FoundationPose's (convert_fp), then a full version <V> through the delivered chain, up to the
# self-check; stops before delivery (delivery changes what rxzhou reads; the user looks first). Unattended:
#   1. per episode, as its stage-05 dump lands (t3_fp_dump.sh): copy work_fp -> work_sel, write the selection
#      (t3_fp_select.py); the pilot episodes are already there;
#   2. CARI4D 06-08 on the selected episodes with the whole GPU (runs/work_dump/GPU_HOLD), batched: the hold is set once
#      MIN_BATCH episodes wait, or when no dump stream is left; rxzhou's chain is waited for (10-10 rule);
#   3. per episode, in the background as soon as its 06-08 are done: decode, soma, residual, focal (intrinsics_gb3, body
#      refit), world into runs/convert_fp_<V>, with gb4's floor fit and camera registration (copied to the <V> names, so
#      the world frame is the delivered one);
#   4. the other convert dirs of <V> are hard-linked from gb4 (their episodes are unchanged), then t3_gb_chain.sh <V>
#      (assemble, physics, supports, dr2s, dyn7, checks), then the self-check ($G/dyn/<V>_selfcheck.sh, generated from
#      gb4's with the names swapped).
#   setsid nohup stages/recovery/tier3/t3_sel_full.sh gb5 ep01_vacuum ... > $T/logs/sel_full.log 2>&1 &
# Last line: SEL_FULL_DONE, SEL_FULL_SKIPPED (gate failed) or SEL_FULL_FAILED <step>.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
G=/lab_data/yqchen/v2d/gate
PY=/lab_data/yqchen/v2d/venv/bin/python
WEIGHTS=/lab_data/yqchen/v2d/weights
A=/lab_data/yqchen/v2d/soma_assets
RX_RUNS=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs
HOLD=$T/runs/work_dump/GPU_HOLD
MIN_BATCH=${MIN_BATCH:-4}
V=${1:?usage: t3_sel_full.sh <version> <episode>...}; shift
EPS="$*"
CONV=convert_fp_$V
D=(docker run --rm --cpus 6 -e OMP_NUM_THREADS=6 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
log() { echo "$(date '+%m-%d %T') $*"; }
fail() { rm -f "$HOLD"; log "SEL_FULL_FAILED $*"; exit 1; }
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
dumps_running() { docker ps --filter ancestor=v2d_cari4d:latest --format '{{.Command}}' --no-trunc | grep -c run_foundationpose_mhr_export; }
streams_left() { pgrep -f "[t]3_fp_dump.sh" | wc -l; }
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
mesh_of() { "$PY" -c "import json; print(next(m['mesh'] for m in map(json.loads, open('$T/input/meta/episodes_metadata.jsonl')) if m['episode_index']==$1))"; }
seq_of() { printf episode_%06d "$((10#${1:2:2}))"; }
cdir() { echo "$T/runs/work_sel/$1/cari4d/$(seq_of "$1")"; }
log "deployed: $(cat "$T/code/DEPLOYED")"
for v in tier3_cari4d_${V}_best tier3_cari4d_${V}_best_dr2s tier3_cari4d_${V}_best_dr2s_dyn7; do [ -e "$T/runs/$v" ] && fail "runs/$v exists"; done

until grep -q -E "SEL_GATE_PASS|SEL_GATE_FAIL|SEL_PILOT_FAILED" "$T/logs/sel_pilot.log" 2>/dev/null; do sleep 60; done
grep -q SEL_GATE_PASS "$T/logs/sel_pilot.log" || { log "gate: $(grep -E 'SEL_GATE_FAIL|SEL_PILOT_FAILED' "$T/logs/sel_pilot.log")"; log SEL_FULL_SKIPPED; exit 0; }
log "gate passed"

convert_one() {  # decode .. world of one episode into runs/$CONV (background; its own log)
  local name=$1 ep=$((10#${1:2:2})) c; c=$(cdir "$1")
  local o=$T/runs/$CONV/$name L=$T/logs/sel_convert_$name.log
  rm -rf "$o"; mkdir -p "$o"
  run_c() { "${D[@]}" $1 -v "$S":/s:ro -v "$c":/e:ro -v "$WEIGHTS/cari4d":/w:ro -v "$A":/a:ro -v "$T/runs/floor":/f:ro \
              -v "$T/input":/in:ro -v "$o":/o/"$name" v2d_cari4d:latest python /s/t3_convert_ep.py "${@:2}"; }
  {
    run_c "" decode /e /w /o/"$name" && run_c "--gpus all" soma /o/"$name" /a && { run_c "" residual /o/"$name" /a || true; } \
      && run_c "" focal /o/"$name" /f/intrinsics_gb3.json /a "/in/$(mesh_of "$ep")" \
      && run_c "" world /o/"$name" /f/floor_fit_$V.json /a /f/camera_register_$V.json \
      && echo CONVERT_OK || echo CONVERT_FAILED
  } > "$L" 2>&1
}

# gb4's floor fit and registration under the <V> names (the world frame stays the delivered one)
cp -n "$T/runs/floor/floor_fit_gb4.json" "$T/runs/floor/floor_fit_$V.json"
cp -n "$T/runs/floor/camera_register_gb4.json" "$T/runs/floor/camera_register_$V.json"
cmp -s "$T/runs/floor/floor_fit_gb4.json" "$T/runs/floor/floor_fit_$V.json" || fail "floor_fit_$V.json differs from gb4's"
cmp -s "$T/runs/floor/camera_register_gb4.json" "$T/runs/floor/camera_register_$V.json" || fail "camera_register_$V.json differs from gb4's"
mkdir -p "$T/runs/$CONV" "$T/runs/work_sel"

declare -A selected refined converting
while :; do
  # 1. select what has landed
  for name in $EPS; do
    [ -n "${selected[$name]:-}" ] && continue
    c=$(cdir "$name")
    if [ -f "$c/foundationpose/fp_select.json" ]; then selected[$name]=1; continue; fi
    if [ ! -f "$T/runs/work_dump/$name/check.json" ]; then
      [ "$(streams_left)" -eq 0 ] && [ ! -f "$T/runs/work_dump/$name/check.json" ] && fail "$name: no dump stream left and no dump"
      continue
    fi
    grep -q '"identical": true' "$T/runs/work_dump/$name/check.json" || fail "$name: dump check not identical"
    rm -rf "$T/runs/work_sel/$name"; cp -a "$T/runs/work_fp/$name" "$T/runs/work_sel/$name" || fail "$name: copy"
    rm -f "$c"/.stages/0[678]_*.json "$c"/inference/coconet.pth "$c"/inference/materialized_inputs.h5 \
      "$c"/inference/refined.pth "$c"/inference/refinement_checkpoint.pth "$c"/inference/*.mp4 "$c"/pipeline_report.json
    r=$("${D[@]}" -v "$c":/c -v "$S":/s:ro -v "$T/runs/work_dump/$name":/d:ro -v "$T/input":/in:ro v2d_cari4d:latest \
      python /s/t3_fp_select.py /c "/d/$(seq_of "$name").candidates.npz" "/in/$(mesh_of "$((10#${name:2:2}))")" 2>&1) || fail "$name: select: $r"
    selected[$name]=1
    log "$name selected: $r"
  done
  # 2. 06-08 in batches with the whole GPU
  waiting=()
  for name in $EPS; do
    [ -n "${selected[$name]:-}" ] || continue
    if [ -f "$(cdir "$name")/inference/refined.pth" ]; then refined[$name]=1; else waiting+=("$name"); fi
  done
  if [ ${#waiting[@]} -gt 0 ] && { [ ${#waiting[@]} -ge "$MIN_BATCH" ] || [ "$(streams_left)" -eq 0 ]; }; then
    wait  # background converts first: their soma step is on the GPU and stage 07 peaks near 44 GB
    touch "$HOLD"
    log "GPU hold for ${waiting[*]}"
    while [ "$(dumps_running)" -gt 0 ] || [ "$(free_mib)" -lt 44000 ] || rx_busy; do sleep 60; done
    for name in "${waiting[@]}"; do
      log "$name: CARI4D 06-08"
      T3_WORK=runs/work_sel T3_FP_MODE=register-every-frame T3_LOG_TAG=_sel "$S/t3_cari4d_ep.sh" "$name" || fail "$name: CARI4D (logs/cari4d_${name}_sel.log)"
      rerun=$(grep -h -o '0[1-5]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_sel.log" | grep -v 'elapsed_seconds=0\.0$' | tr '\n' ' ')
      [ -z "$rerun" ] || fail "$name: CARI4D re-ran earlier stages ($rerun)"
      refined[$name]=1
    done
    rm -f "$HOLD"
    log "GPU hold released"
  fi
  # 3. convert in the background
  for name in $EPS; do
    [ -n "${refined[$name]:-}" ] && [ -z "${converting[$name]:-}" ] || continue
    convert_one "$name" & converting[$name]=1
    log "$name: converting (logs/sel_convert_$name.log)"
  done
  n_ref=0; for name in $EPS; do [ -n "${refined[$name]:-}" ] && n_ref=$((n_ref + 1)); done
  [ "$n_ref" -eq "$(echo $EPS | wc -w)" ] && break
  sleep 60
done
wait
for name in $EPS; do tail -1 "$T/logs/sel_convert_$name.log" | grep -q CONVERT_OK || fail "$name: convert (logs/sel_convert_$name.log)"; done
log "all converted"

# 4. the version: unchanged convert dirs from gb4, then the delivered chain and the self-check
for d in convert convert_v2 convert_pivot convert_fp; do
  [ -e "$T/runs/${d}_$V" ] && [ "$d" != convert_fp ] && continue
  for e in "$T/runs/${d}_gb4"/ep*; do
    b=$(basename "$e"); [ -e "$T/runs/${d}_$V/$b" ] && continue
    mkdir -p "$T/runs/${d}_$V"; cp -al "$e" "$T/runs/${d}_$V/$b"
  done
done
echo "$(date '+%m-%d %T') reused floor_fit_gb4.json and camera_register_gb4.json as the $V files (t3_sel_full.sh); GB3_REGISTER_DONE" > "$T/logs/${V}_register.log"
"$S/t3_gb_chain.sh" "$V" > "$T/logs/gb_chain_$V.log" 2>&1
grep -q GB_CHAIN_DONE "$T/logs/gb_chain_$V.log" || fail "chain: $(tail -1 "$T/logs/gb_chain_$V.log")"
log "chain: $(grep -E '^.{14} 7 checks' "$T/logs/gb_chain_$V.log" | cut -c1-300)"
sed -e "s/tier3_cari4d_gb4_best/tier3_cari4d_${V}_best/g" -e "s/gb4dyn7/${V}dyn7/g" -e "s/gb_chain_gb4/gb_chain_$V/g" \
    -e "s/audit_gb4dr2s_to/audit_${V}dr2s_to/g" -e "s#tier3_cari4d_gb_best_dr2s_dyn7 \$V dev/audit/audit_gbdyn7_to#tier3_cari4d_gb4_best_dr2s_dyn7 \$V dev/audit/audit_gb4dyn7_to#" \
    -e "s/audit_gbdyn7_to/audit_gb4dyn7_to/g" -e "s/^# 10-18: self-check of .*/# generated by t3_sel_full.sh from gb4_selfcheck.sh for $V (names swapped, compared against gb4_best_dr2s_dyn7)/" \
    "$G/dyn/gb4_selfcheck.sh" > "$G/dyn/${V}_selfcheck.sh"
bash "$G/dyn/${V}_selfcheck.sh" > "$G/dyn/${V}_selfcheck.log" 2>&1
grep -q SELFCHECK_DONE "$G/dyn/${V}_selfcheck.log" || fail "selfcheck: $(tail -1 "$G/dyn/${V}_selfcheck.log")"
log SEL_FULL_DONE
