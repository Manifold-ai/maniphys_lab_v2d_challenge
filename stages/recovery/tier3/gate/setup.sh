#!/usr/bin/env bash
# Build the gate env on a CPU machine: rxzhou's code at one commit + upstream video_to_data v0.4.0 + a py3.11 venv with
# his image's versions. Run on the gate machine; his code comes on stdin as a tar (git archive):
#   git archive <commit> libs stages scripts tools third_party | ssh <host> "<this dir>/setup.sh <commit>"
# Env: T3_GATE (default /lab_data/yqchen/v2d/gate), SOMA_ASSETS (default /lab_data/yqchen/v2d/soma_assets).
set -euo pipefail
COMMIT=${1:?usage: setup.sh <rxzhou commit>  (tar of his tree on stdin)}
HERE=$(cd "$(dirname "$0")" && pwd)
G=${T3_GATE:-/lab_data/yqchen/v2d/gate}; A=${SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
[ -e "$G/repo" ] && { echo "$G/repo exists"; exit 1; }
mkdir -p "$G/repo" "$G/logs"
tar -x -C "$G/repo"
echo "$COMMIT" > "$G/repo/.v2d-source-commit"
cp "$G/repo/scripts/dev/incontainer" "$G/incontainer.orig"
cp "$HERE/incontainer" "$G/repo/scripts/dev/incontainer"
git clone -q --depth 1 --branch v0.4.0 https://github.com/nvidia-isaac/video_to_data "$G/repo/third_party/video_to_data"  # git-lfs needed
for x in "$A"/*; do ln -sfn "$x" "$G/repo/third_party/video_to_data/robotic_grounding/source/robotic_grounding/robotic_grounding/assets/body_models/soma/"; done
command -v ~/.local/bin/uv >/dev/null || python3 -m pip install --user -q uv
export UV_PYTHON_INSTALL_DIR=$G/.py UV_CACHE_DIR=$G/.uvcache
~/.local/bin/uv venv -q -p 3.11 "$G/venv"
# Versions of robotic-grounding:latest (pip list, 10-13); numpy is 2.x here because the pin 3.7.0 wheel requires it
# (the image has 1.26), and its cmeel deps are pinned back to the sonames that wheel links against.
~/.local/bin/uv pip install -q -p "$G/venv/bin/python" --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  "torch==2.7.0" "scipy==1.15.3" "trimesh==4.5.1" "pyarrow==25.0.1" "pin==3.7.0" "pin-pink==4.2.0" "viser==1.0.15" \
  "loop-rate-limiters==1.2.0" "qpsolvers==4.9.0" "daqp==0.7.2" "proxsuite==0.7.3" "osqp==1.1.3" "clarabel==0.11.1" \
  "usd-core==26.8" "py-soma-x==0.2.1" "cmeel-urdfdom>=4,<5" "cmeel-tinyxml2>=10,<11" tqdm \\
  h5py opencv-python-headless fast-simplification  # t3_align_check.py (masks, silhouettes, mesh decimation)
"$G/venv/bin/python" -c "import pinocchio, pink, soma, pxr, torch; print('gate env ok', pinocchio.__version__, torch.__version__)"
