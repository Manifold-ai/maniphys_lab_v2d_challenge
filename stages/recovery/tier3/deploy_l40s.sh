#!/usr/bin/env bash
# Deploy the Tier 3 code to L40S from a clean commit (run locally), so every version can name the code that made it.
# Copies stages/recovery/tier3 and libs/v2d_infra into $T/code at the same relative paths, the gate checks into $G flat
# (where the gate environment runs them), and writes $T/code/DEPLOYED (commit) and $T/code/MANIFEST.sha256 (every file
# under $T/code), which t3_provenance.stamp() checks the loaded code against.
#   stages/recovery/tier3/deploy_l40s.sh
set -euo pipefail
HOST=${T3_HOST:-manifolds_l40s}
T=/lab_data/yqchen/v2d/tier3
G=/lab_data/yqchen/v2d/gate
cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain -- stages/recovery/tier3 libs/v2d_infra)" ]; then
  echo "uncommitted changes under stages/recovery/tier3 or libs/v2d_infra; commit first" >&2
  git status --short -- stages/recovery/tier3 libs/v2d_infra >&2
  exit 1
fi
SHA=$(git rev-parse HEAD)
rsync -a --exclude __pycache__ stages/recovery/tier3/ "$HOST:$T/code/stages/recovery/tier3/"
rsync -a --exclude __pycache__ libs/v2d_infra/ "$HOST:$T/code/libs/v2d_infra/"
rsync -a stages/recovery/tier3/gate/t3_dynamics_check.py stages/recovery/tier3/gate/t3_symmetry.py \
  stages/recovery/tier3/gate/t3_hand_object_check.py stages/recovery/tier3/gate/t3_contact_states.py "$HOST:$G/"
ssh "$HOST" "cd $T/code && echo '$SHA dirty=0 (deploy_l40s.sh: stages/recovery/tier3 libs/v2d_infra) $(date '+%F %T %Z')' > DEPLOYED \
  && find . -type f ! -name DEPLOYED ! -name MANIFEST.sha256 ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 \
  && echo deployed \$(cat DEPLOYED) files=\$(wc -l < MANIFEST.sha256)"
