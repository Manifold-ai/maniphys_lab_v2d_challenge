#!/usr/bin/env bash
# 10-19: re-run CARI4D stage 05 (FoundationPose, register every frame, as work_fp) with the candidate dump
# (third_party/patches/cari4d-fp-candidate-dump.patch), so the branch can be chosen over the whole timeline afterwards.
# Only stage 05: the exporter is called directly on work_fp's export and aligned depth; work_fp is read only. Output per
# episode in runs/work_dump/<name>/: <seq>.pkl (must equal work_fp's, checked) and <seq>.candidates.npz.
# One stream per call; run two for two jobs on the GPU (~17 GB each):
#   setsid nohup stages/recovery/tier3/t3_fp_dump.sh A ep03_contigo_coffee_mug ep02_blue_easter_basket > $T/logs/fp_dump_A.log 2>&1 &
# Before each episode the stream waits while rxzhou's chain is busy (10-10 rule), while $T/runs/work_dump/GPU_HOLD
# exists (a job that needs the whole GPU, e.g. stage 07 at ~44 GB, asks for it) or while < 20 GB are free.
# touch $T/runs/work_dump/STOP stops every stream between episodes. Last line: FP_DUMP_STREAM_DONE <stream> or
# FP_DUMP_FAILED <stream> <episode>.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
OUT=$T/runs/work_dump
RX_RUNS=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs
MOD=/lab_data/yqchen/v2d/video_to_data/reconstruction/modules
WEIGHTS=/lab_data/yqchen/v2d/weights/cari4d
UP=/workspace/v2d_cari4d/lib/cari4d/prep/run_foundationpose_mhr_export.py
BASE=$T/patched/run_foundationpose_mhr_export.py
DUMP=$T/patched/run_foundationpose_mhr_export_dump.py
BASE_MD5=556a32239f14f8b87a137f1edec26514
DUMP_MD5=b54ca7dd78a90b9d61e1193e006bdc7f
stream=$1; shift
say() { echo "$(date '+%m-%d %T') [$stream] $*"; }
fail() { say "FP_DUMP_FAILED $stream $*"; exit 1; }
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
mkdir -p "$OUT" "$T/logs"

# the dump variant of the exporter, built once from the deployed patched file (both md5-pinned)
(
  flock 9
  if [ "$(md5sum < "$DUMP" 2>/dev/null | cut -c1-32)" != $DUMP_MD5 ]; then
    [ "$(md5sum < "$BASE" | cut -c1-32)" = $BASE_MD5 ] || { echo "$BASE is not the patched file the dump patch expects"; exit 2; }
    patch -s -o "$DUMP.tmp" "$BASE" < "$S/../../../third_party/patches/cari4d-fp-candidate-dump.patch" || exit 2
    [ "$(md5sum < "$DUMP.tmp" | cut -c1-32)" = $DUMP_MD5 ] || { echo "dump exporter md5 mismatch"; exit 2; }
    mv "$DUMP.tmp" "$DUMP"
  fi
) 9> "$T/patched/.dump.lock" || fail "building the dump exporter"

for name in "$@"; do
  seq=$(printf episode_%06d "$((10#${name:2:2}))")
  src=$T/runs/work_fp/$name/cari4d/$seq
  dst=$OUT/$name
  if [ -f "$dst/check.json" ] && grep -q '"identical": true' "$dst/check.json"; then say "$name: done before, skipped"; continue; fi
  waited=""
  while :; do
    [ -e "$OUT/STOP" ] && { say "STOP file, stopping before $name"; say "FP_DUMP_STREAM_DONE $stream (stopped)"; exit 0; }
    why=""
    rx_busy && why="rxzhou's chain"
    [ -z "$why" ] && [ -e "$OUT/GPU_HOLD" ] && why="GPU_HOLD"
    [ -z "$why" ] && [ "$(free_mib)" -lt 20000 ] && why="$(free_mib) MiB free"
    [ -z "$why" ] && break
    [ "$waited" = "$why" ] || say "$name waits: $why"
    waited=$why; sleep 60
  done
  [ -f "$src/foundationpose/$seq.pkl" ] || fail "$name: no work_fp stage-05 output to compare against"
  rm -rf "$dst"; mkdir -p "$dst"
  say "$name start ($(free_mib) MiB free)"
  docker run --rm --runtime=nvidia --gpus all --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$MOD":/workspace -v "$DUMP":"$UP":ro -v "$WEIGHTS":/data/weights_path:ro -v "$src":/e:ro -v "$dst":/t \
    -e PYTHONPATH=/workspace/v2d_cari4d/lib/cari4d:/workspace/v2d_sam3d_body/lib:/workspace/v2d_foundation_pose/lib/FoundationPose \
    -e FOUNDATIONPOSE_WEIGHTS_DIR=/data/weights_path/foundationpose/nvlabs_pytorch -e PYOPENGL_PLATFORM=egl \
    -e HDF5_USE_FILE_LOCKING=FALSE -e PYTHONUNBUFFERED=1 -w /workspace/v2d_cari4d/lib/cari4d --entrypoint "" v2d_cari4d:latest \
    python prep/run_foundationpose_mhr_export.py /e/export/$seq --depth-root /e/depth/moge2/aligned.h5 --out-file /t/$seq.pkl \
      --camera-id 0 --iteration 5 --max-attempts 5 --register-every-frame --no-first-usable-frame-gt-rotation-oracle \
    > "$T/logs/fp_dump_$name.log" 2>&1 || fail "$name: exporter failed (logs/fp_dump_$name.log)"
  docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$src":/e:ro -v "$dst":/t --entrypoint "" v2d_cari4d:latest \
    python - "/e/foundationpose/$seq.pkl" "/t/$seq.pkl" "/t/$seq.candidates.npz" > "$dst/check.json" <<'EOF' || fail "$name: check failed"
import json, pickle, sys
import numpy as np
old, new = (pickle.load(open(p, "rb")) for p in sys.argv[1:3])
c = np.load(sys.argv[3])
keys = [k for k in old if k.startswith("fp_") and k in new]
same = {k: bool(np.array_equal(np.asarray(old[k]), np.asarray(new[k]), equal_nan=np.asarray(old[k]).dtype.kind == "f")) for k in keys}
out = {"identical": all(same.values()) and old["frames"] == new["frames"], "differing": [k for k, v in same.items() if not v],
       "frames": len(new["frames"]), "calls": int(len(c["call_frame"])), "candidates": int(len(c["scores"])),
       "frames_with_calls": int(len(np.unique(c["call_frame"])))}
print(json.dumps(out))
EOF
  say "$name done: $(cat "$dst/check.json")"
  grep -q '"identical": true' "$dst/check.json" || fail "$name: stage-05 output differs from work_fp"
done
say "FP_DUMP_STREAM_DONE $stream"
