#!/usr/bin/env bash
# 11-04: a Tier 3 version <V> from a delivered version <BASE> with the selector's ROT_DEG chosen per episode by
# t3_rot_rule.py (plan ~/v2d/synth-hoi/plan-tier3-rot5-submission-2026-11-04.md). One command, on L40S:
#   1. on each FoundationPose-selected episode of <BASE> (the episodes of runs/$ROT_BASE_WORK), the rule from the
#      pre-selection copy runs/work_fp (read-only, CPU): its json into runs/rot_rule_<V>/, the chosen ROT_DEG printed;
#      an episode that keeps 10 must select exactly as <BASE> did (dry run at 10 against the base work pkl, bit for bit);
#   2. the episodes that take 5: work_fp copied into runs/work_rot_<V>, stages 06-08 cleared, the selection written
#      (t3_fp_select.py --rot-deg=5), then, with the whole GPU (rxzhou's chain and every flash_chord gone, >= 44000 MiB
#      free, QUIET_MIN minutes in a row), CARI4D 06-08 (T3_SKIP_RENDER=1) and convert (decode, soma, residual, focal,
#      world, as t3_sel_full.sh) into runs/convert_fp_<V>;
#   3. every other convert dir of <V> COPIED from <BASE> (cp -a, never hard links: no later step may write into <BASE>'s
#      files), floor fit and camera registration under the <V> names, then t3_gb_chain.sh <V> (its chain_check.sh also
#      appends the lean supports, gate/t3_lean_support.py since bc1d566, as added to <BASE>'s set in place on 10-21);
#   4. every episode that kept 10: its parquet and support usda byte-identical to <BASE>'s delivered ones; one differing
#      file stops the run (the version is then not used: it would not be what this command makes).
#   setsid nohup stages/recovery/tier3/t3_rot_full.sh gb6 gb5 > $T/logs/rot_full_gb6.log 2>&1 &
# ROT_BASE_WORK (default work_b050): the base's selection work dir. QUIET_MIN (default 30): the GPU wait (10-10 rule).
# ROT_STOP=$T/runs/ROT_STOP stops it while waiting for the GPU. Last line ROT_FULL_DONE or ROT_FULL_FAILED <step>.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
G=${T3_GATE:-/lab_data/yqchen/v2d/gate}
PY=/lab_data/yqchen/v2d/venv/bin/python
WEIGHTS=/lab_data/yqchen/v2d/weights
A=/lab_data/yqchen/v2d/soma_assets
RX_RUNS=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs
V=${1:?usage: t3_rot_full.sh <version> <base version>}; BASE=${2:?base version}
BW=${ROT_BASE_WORK:-work_b050}
QUIET_MIN=${QUIET_MIN:-30}
WORK=work_rot_$V
RULE=$T/runs/rot_rule_$V
BV=tier3_cari4d_${BASE}_best_dr2s_dyn7
D=(docker run --rm --cpus 6 -e OMP_NUM_THREADS=6 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
log() { echo "$(date '+%m-%d %T') $*"; }
fail() { log "ROT_FULL_FAILED $*"; exit 1; }
mesh_of() { "$PY" -c "import json; print(next(m['mesh'] for m in map(json.loads, open('$T/input/meta/episodes_metadata.jsonl')) if m['episode_index']==$1))"; }
seq_of() { printf episode_%06d "$((10#${1:2:2}))"; }
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
cd "$T" || exit 1
log "deployed: $(cat code/DEPLOYED)"
for v in tier3_cari4d_${V}_best tier3_cari4d_${V}_best_dr2s tier3_cari4d_${V}_best_dr2s_dyn7 $WORK rot_rule_$V \
         convert_$V convert_v2_$V convert_pivot_$V convert_fp_$V; do [ -e "runs/$v" ] && fail "runs/$v exists"; done
[ -d "runs/$BV" ] || fail "no runs/$BV"
mkdir -p "$RULE" "runs/$WORK" "runs/convert_fp_$V"

# 1. the rule on every FP-selected episode of the base
FIVE=()
for name in $(ls "runs/$BW"); do
  ep=$((10#${name:2:2})); seq=$(seq_of "$name"); c=$T/runs/work_fp/$name/cari4d/$seq
  args=("$c" "$T/runs/work_dump/$name/$seq.candidates.npz" "$T/input/$(mesh_of "$ep")")
  r=$("${D[@]}" -v "$T:$T:ro" -v "$RULE:$RULE" -v "$S:/s:ro" v2d_cari4d:latest \
      python /s/t3_rot_rule.py "${args[@]}" "$T/runs/work_fp/$name/sam2_masks" "$RULE/$name.json" 2> "$RULE/$name.err" | tail -1) \
      || fail "rule $name ($RULE/$name.err)"
  case "$r" in
    5) FIVE+=("$name") ;;
    10) "${D[@]}" -v "$T:$T:ro" -v "$RULE:$RULE" -v "$S:/s:ro" v2d_cari4d:latest \
          python /s/t3_fp_select.py "${args[@]}" --dry --rot-deg=10 --poses-out="$RULE/r10_$name.npz" > /dev/null 2>> "$RULE/$name.err" \
          || fail "dry select 10 $name"
        "$PY" -c "
import pickle, sys, numpy as np, glob
(pk,) = glob.glob('$T/runs/$BW/$name/cari4d/$seq/foundationpose/episode_*.pkl')
b = np.asarray(pickle.load(open(pk, 'rb'))['fp_poses_cam'], np.float64)[:, 0]
a = np.load('$RULE/r10_$name.npz')['poses_cam']
sys.exit(0 if a.shape == b.shape and np.array_equal(a, b) else 1)" || fail "$name keeps 10 but does not select as $BW" ;;
    *) fail "rule $name printed '$r'" ;;
  esac
  log "$name: ROT_DEG $r ($(tr -d '\n ' < "$RULE/$name.json" | cut -c1-200))"
done
log "rule: ROT_DEG 5 on ${FIVE[*]:-none}"
for name in "${FIVE[@]}"; do  # the chain assembles from tier3_cari4d_f830_best.selection.json's convert dirs: it must read convert_fp
  "$PY" -c "import json,sys; sys.exit(0 if any(r['episode'] == '$name' and r['convert'] == 'convert_fp' for r in json.load(open('runs/tier3_cari4d_f830_best.selection.json'))) else 1)" \
    || fail "$name takes 5 but the assemble does not read convert_fp for it"
done

# 2. selection, 06-08 and convert of the episodes that take 5
convert_one() {  # as t3_sel_full.sh convert_one, with the base's floor fit and registration under the <V> names
  local name=$1 ep=$((10#${1:2:2})) c=$T/runs/$WORK/$1/cari4d/$(seq_of "$1")
  local o=$T/runs/convert_fp_$V/$name
  rm -rf "$o"; mkdir -p "$o"
  run_c() { "${D[@]}" $1 -v "$S":/s:ro -v "$c":/e:ro -v "$WEIGHTS/cari4d":/w:ro -v "$A":/a:ro -v "$T/runs/floor":/f:ro \
              -v "$T/input":/in:ro -v "$o":/o/"$name" v2d_cari4d:latest python /s/t3_convert_ep.py "${@:2}"; }
  run_c "" decode /e /w /o/"$name" && run_c "--gpus all" soma /o/"$name" /a && { run_c "" residual /o/"$name" /a || true; } \
    && run_c "" focal /o/"$name" /f/intrinsics_gb3.json /a "/in/$(mesh_of "$ep")" \
    && run_c "" world /o/"$name" /f/floor_fit_$V.json /a /f/camera_register_$V.json
}
for f in floor_fit camera_register; do
  cp -n "runs/floor/${f}_$BASE.json" "runs/floor/${f}_$V.json"
  cmp -s "runs/floor/${f}_$BASE.json" "runs/floor/${f}_$V.json" || fail "runs/floor/${f}_$V.json differs from $BASE's"
done
for name in "${FIVE[@]}"; do
  c=$T/runs/$WORK/$name/cari4d/$(seq_of "$name")
  cp -a "runs/work_fp/$name" "runs/$WORK/$name" || fail "$name: copy"
  rm -f "$c"/.stages/0[678]_*.json "$c"/inference/coconet.pth "$c"/inference/materialized_inputs.h5 \
    "$c"/inference/refined.pth "$c"/inference/refinement_checkpoint.pth "$c"/inference/*.mp4 "$c"/pipeline_report.json
  r=$("${D[@]}" -v "$c":/c -v "$S":/s:ro -v "$T/runs/work_dump/$name":/d:ro -v "$T/input":/in:ro v2d_cari4d:latest \
    python /s/t3_fp_select.py /c "/d/$(seq_of "$name").candidates.npz" "/in/$(mesh_of "$((10#${name:2:2}))")" --rot-deg=5 2>&1) \
    || fail "$name: select: $r"
  log "$name selected: $(echo "$r" | cut -c1-200)"
done
if [ ${#FIVE[@]} -gt 0 ]; then
  log "waiting for the GPU (rxzhou quiet, >= 44000 MiB free, $QUIET_MIN min in a row)"
  q=0
  while [ "$q" -lt "$QUIET_MIN" ]; do
    [ -e runs/ROT_STOP ] && fail "ROT_STOP"
    if rx_busy || [ "$(free_mib)" -lt 44000 ]; then q=0; else q=$((q + 1)); fi
    sleep 60
  done
  log "GPU free"
  for name in "${FIVE[@]}"; do
    log "$name: CARI4D 06-08"
    T3_WORK=runs/$WORK T3_FP_MODE=register-every-frame T3_SKIP_RENDER=1 T3_LOG_TAG=_rot_$V "$S/t3_cari4d_ep.sh" "$name" \
      || fail "$name: CARI4D (logs/cari4d_${name}_rot_$V.log)"
    rerun=$(grep -h -o '0[1-5]_[a-z_]* elapsed_seconds=[0-9.]*' "logs/cari4d_${name}_rot_$V.log" | grep -v 'elapsed_seconds=0\.0$' | tr '\n' ' ')
    [ -z "$rerun" ] || fail "$name: CARI4D re-ran earlier stages ($rerun)"
    for st in 06_coconet 07_refinement; do  # and the stages to redo did run (a marker left behind would skip them)
      grep -h -o "$st elapsed_seconds=[0-9.]*" "logs/cari4d_${name}_rot_$V.log" | tail -1 | grep -q -v -E 'elapsed_seconds=0(\.0*)?$' \
        || fail "$name: CARI4D did not run $st"
    done
    log "$name: convert"
    convert_one "$name" > "logs/rot_convert_${name}_$V.log" 2>&1 || fail "$name: convert (logs/rot_convert_${name}_$V.log)"
  done
  log "GPU steps done"
fi

# 3. the rest copied from the base, then the delivered chain (lean supports included)
for d in convert convert_v2 convert_pivot convert_fp; do
  for e in "runs/${d}_$BASE"/ep*; do
    b=$(basename "$e"); [ -e "runs/${d}_$V/$b" ] && continue
    mkdir -p "runs/${d}_$V"; cp -a "$e" "runs/${d}_$V/$b" || fail "copy ${d}_$BASE/$b"
  done
done
echo "$(date '+%m-%d %T') reused floor_fit_$BASE.json and camera_register_$BASE.json as the $V files (t3_rot_full.sh); GB3_REGISTER_DONE" > "logs/${V}_register.log"
"$S/t3_gb_chain.sh" "$V" > "logs/gb_chain_$V.log" 2>&1
grep -q GB_CHAIN_DONE "logs/gb_chain_$V.log" || fail "chain: $(tail -1 "logs/gb_chain_$V.log")"
log "chain done; lean supports: $(tail -1 "$G/logs/lean_support_${V}dyn7.txt" | cut -c1-200)"

# 4. the episodes that kept 10 are byte-identical to the base's delivered ones
"$PY" - "$T" "$G" "$V" "$BASE" "${FIVE[@]}" <<'EOF' || fail "unchanged episodes differ from the base (logs/rot_full_$V.log)"
import json, filecmp, sys
from pathlib import Path
t, g, v, base, five = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], set(sys.argv[5:])
def eps(ver):
    out = {}
    for sub in ("", "_suspect"):
        d = t / "runs" / f"tier3_cari4d_{ver}_best_dr2s_dyn7{sub}"
        for m in sorted((d / "meta").glob("episode_*.metadata.json")) if (d / "meta").is_dir() else []:
            meta = json.loads(m.read_text()); i = int(m.name.split("_")[1].split(".")[0])
            out[i] = (d / "data/chunk-000" / f"episode_{i:06d}.parquet", Path(meta["support_surface"]).name, sub)
    return out
new, old = eps(v), eps(base)
assert sorted(new) == sorted(old) and len(new) == 30, (len(new), len(old))
names = {int(r["episode_index"]): r["episode"] for r in json.loads((t / "runs" / f"tier3_cari4d_{v}_best.selection.json").read_text())}
bad = []
for i, (pq, usda, sub) in sorted(new.items()):
    if names[i] in five:
        if filecmp.cmp(pq, old[i][0], shallow=False):
            bad.append(names[i] + " (ROT_DEG 5 but its parquet equals the base's)")
        print(names[i], "ROT_DEG 5, parquet differs from the base:", not filecmp.cmp(pq, old[i][0], shallow=False)); continue
    same_pq = filecmp.cmp(pq, old[i][0], shallow=False) and sub == old[i][2]
    same_us = filecmp.cmp(g / f"support_usda_{v}dyn7" / usda, t / "runs" / f"tier3_cari4d_{base}_best_dr2s_dyn7{old[i][2]}" / "support_surface" / usda, shallow=False)
    if not (same_pq and same_us):
        bad.append(names[i])
    print(names[i], "parquet", "same" if same_pq else "DIFFERS", "usda", "same" if same_us else "DIFFERS")
if bad:
    raise SystemExit(f"differ: {bad}")
EOF
log ROT_FULL_DONE
