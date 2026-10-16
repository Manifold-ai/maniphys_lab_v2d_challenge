#!/usr/bin/env bash
# 10-17: the calibrated intrinsics (GB) on all three exo cameras, through the floor fit, both registrations and the world
# step, unattended. Waits for the focal step under intrinsics_gb3.json (logs/gb3_focal.out, four sources, 0 failures),
# then:
#   1. floor fit on convert_gb3: second camera scale 0.949 (1/1.053, t3_register_check.py), ep21's normal from its
#      ceiling horizon (runs/floor/ceiling_vp_other.json) -> runs/floor/floor_fit_gb3.json
#   2. second camera onto the main one by mutual sightings -> runs/floor/camera_register_gb3.json group 1
#   3. ep21 by its sightings of A and C, left = A, the pair of tripod boxes kept from the 10-12 registration
#      (dev/kgb/ep21_original_pair.json) -> camera_register_gb3.json group 2
#   4. world step for every episode of convert_gb3, convert_v2_gb3, convert_fp_gb3, convert_pivot_gb3
#   5. summary: floor-event contact heights over the released floor in the new world, per episode and camera, against the
#      f830 world (runs/convert); new against old registration -> dev/kgb/gb3_summary.txt
# Every step checks its output and stops with GB3_FAILED <step> on a miss; last line GB3_REGISTER_DONE.
#   setsid nohup stages/recovery/tier3/t3_gb3_register.sh > $T/logs/gb3_register.log 2>&1 &
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
A=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
JOBS=${JOBS:-3}
F=$T/runs/floor
D=(docker run --rm --cpus 4 -e OMP_NUM_THREADS=4 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
log() { echo "$(date '+%m-%d %T') $*"; }
fail() { log "GB3_FAILED $*"; exit 1; }

log "deployed: $(cat "$T/code/DEPLOYED")"
until grep -q GB3_FOCAL_DONE "$T/logs/gb3_focal.out" 2>/dev/null; do sleep 60; done
[ "$(grep -c 'failed=0' "$T/logs/gb3_focal.out")" = 4 ] || fail "focal: $(cat "$T/logs/gb3_focal.out")"
log "focal done: $(tr '\n' ' ' < "$T/logs/gb3_focal.out")"

for f in floor_fit_gb3.json camera_register_gb3.json; do [ -e "$F/$f" ] && fail "$f exists"; done
"${D[@]}" -v "$S":/s:ro -v "$T":/t:ro -v "$F":/t/runs/floor v2d_cari4d:latest python /s/t3_floor_fit.py /t /t/runs/floor/floor_fit_gb3.json \
  convert_gb3 scale=1:0.949 horizon=2:/t/runs/floor/ceiling_vp_other.json > "$T/logs/floor_fit_gb3.log" 2>&1 \
  && [ -f "$F/floor_fit_gb3.json" ] || fail "floor fit (logs/floor_fit_gb3.log)"
log "floor fit: $(grep -o '"group": [0-9], [^{]*"how": "[a-z_]*"' "$T/logs/floor_fit_gb3.log" | tr '\n' ' ')"

(cd "$S" && "$PY" t3_mutual_multi.py "$T" "$F/floor_fit_gb3.json" "$T/dev/walls" 0 1 "$F/camera_register_gb3.json" conv=convert_gb3) \
  > "$T/logs/mutual_gb3.log" 2>&1 && grep -q '"1"' "$F/camera_register_gb3.json" || fail "mutual (logs/mutual_gb3.log)"
log "second camera: $(grep yaw_deg "$T/logs/mutual_gb3.log" | head -1)"

(cd "$S" && "$PY" t3_corner_register.py "$T" "$F/floor_fit_gb3.json" "$T/dev/walls" "$T/dev/ep21/crops_det" ep21_tall_bar_stool 2 \
  --left=A "$F/camera_register_gb3.json" conv=convert_gb3 base="$F/camera_register_gb3.json" pair="$T/dev/kgb/ep21_original_pair.json") \
  > "$T/logs/corner_gb3.log" 2>&1 && grep -q '"2"' "$F/camera_register_gb3.json" || fail "corner (logs/corner_gb3.log)"
log "ep21: $(head -1 "$T/logs/corner_gb3.log" | cut -c1-400)"

world_one() {
  local dir=$1 name=$2
  "${D[@]}" -v "$S":/s:ro -v "$F":/f:ro -v "$A":/a:ro -v "$T/runs/$dir/$name":/o/"$name" v2d_cari4d:latest \
    python /s/t3_convert_ep.py world /o/"$name" /f/floor_fit_gb3.json /a /f/camera_register_gb3.json > "$T/logs/world_${dir}_$name.log" 2>&1 \
    && echo "$dir/$name ok" || echo "$dir/$name world FAILED (logs/world_${dir}_$name.log)"
}
export -f world_one
export T S F A
for dir in convert_gb3 convert_v2_gb3 convert_fp_gb3 convert_pivot_gb3; do
  ls "$T/runs/$dir" | grep '^ep' | xargs -P "$JOBS" -I{} bash -c "world_one $dir {}"
done | tee "$T/logs/world_gb3_all.log"
nf=$(grep -c FAILED "$T/logs/world_gb3_all.log")
log "world: $(grep -c ' ok$' "$T/logs/world_gb3_all.log") ok, $nf failed"
[ "$nf" = 0 ] || fail "world ($nf episodes, logs/world_gb3_all.log)"

"${D[@]}" -v "$S":/s:ro -v "$T":/t:ro v2d_cari4d:latest python - > "$T/dev/kgb/gb3_summary.txt" 2>&1 <<'EOF'
import json, sys
import numpy as np, trimesh
sys.path.insert(0, "/s")
import t3_inputs
T = "/t"
metas = {"ep%02d_%s" % (m["episode_index"], m["object"]): m for m in map(json.loads, open(T + "/input/meta/episodes_metadata.jsonl").read().splitlines()) if m}
print("== floor-event contact heights over the released floor in the world frame (cm): new (GB3) | old (f830, runs/convert)")
for g in ("main", "B", "C"):
    ev = json.load(open(T + "/runs/camera_groups/camera_height_%s.json" % g))["event_rows"]
    for ep in sorted({e["episode"] for e in ev}):
        gp = np.asarray(t3_inputs.ground_plane(T, metas[ep]), float)
        n, d = gp[:3] / np.linalg.norm(gp[:3]), gp[3] / np.linalg.norm(gp[:3])
        n, d = (n, d) if d > 0 else (-n, -d)
        hull = np.asarray(trimesh.load(T + "/input/" + metas[ep]["mesh"], force="mesh").convex_hull.vertices, float)
        fr = [e["frame"] for e in ev if e["episode"] == ep]
        out = []
        for conv in ("convert_gb3", "convert"):
            W = np.load(T + "/runs/%s/%s/object_world.npz" % (conv, ep))["T_world_glb"]
            h = [float(((hull @ W[f, :3, :3].T + W[f, :3, 3]) @ n).min() + d) for f in fr]
            out.append("%+.1f [%+.1f, %+.1f]" % (100 * np.median(h), 100 * np.percentile(h, 10), 100 * np.percentile(h, 90)))
        print("  %-5s %-26s %3d events  new %s | old %s" % (g, ep, len(fr), out[0], out[1]))
old = json.load(open(T + "/runs/floor/camera_register.json"))["groups"]
new = json.load(open(T + "/runs/floor/camera_register_gb3.json"))["groups"]
print("== registration: old (f830) -> new (GB3)")
for k in ("1", "2"):
    print("  group", k, "yaw %.2f -> %.2f, t %s -> %s" % (old[k]["yaw_deg"], new[k]["yaw_deg"], old[k]["t_m"], new[k]["t_m"]))
fit = json.load(open(T + "/runs/floor/floor_fit_gb3.json"))
for g in fit["groups"]:
    print("  floor fit group", g["group"], {k: g.get(k) for k in ("how", "tilt_deg", "scale", "shift_m", "d_ours_m", "scale_source")})
EOF
[ -s "$T/dev/kgb/gb3_summary.txt" ] && ! grep -q Traceback "$T/dev/kgb/gb3_summary.txt" || fail "summary (dev/kgb/gb3_summary.txt)"
cat "$T/dev/kgb/gb3_summary.txt"
log GB3_REGISTER_DONE
