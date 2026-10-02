"""试跑用：读 diag_rollout.py --palms 存的 npz，打印手掌数据的形状与同步闸的最大差；同步差 < 1e-6 m 且手掌坐标全有限才退出码 0。
计划 agent-doc/plan-diag-mpsr0-2026-10-02.md 第 3.1 节、第 5 节第 4 步。只用 numpy（FlashCHORD 容器里跑）。
用法：python /repo/stages/evaluate/diag2_sync.py <npz>
"""
import sys

import numpy as np

d = np.load(sys.argv[1], allow_pickle=False)
if "robot_palm_pos" not in d.files:
    print("SYNC_FAIL：npz 里没有 robot_palm_pos（没加 --palms？）")
    sys.exit(1)
palm, sync = d["robot_palm_pos"], float(d["palm_object_sync_max_abs_m"])
ok = bool(np.isfinite(palm).all()) and np.isfinite(sync) and sync < 1e-6
print(f"robot_palm_pos {palm.shape}，手 {[str(s) for s in d['robot_palm_sides']]}，同步最大差 {sync:.3g} m；"
      f"第 0 帧世界 0 两只手掌 {np.round(palm[0, 0], 3).tolist()}")
print("SYNC_OK" if ok else "SYNC_FAIL")
sys.exit(0 if ok else 1)
