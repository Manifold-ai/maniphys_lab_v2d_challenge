# 计划：参考回放会不会在同样的帧摔——分清“参考本身跟不住”与“训出的残差带偏”（t12replay，10/20 傍晚，第 1 版）

2026-10-20 17:4x MDT 写定第 1 版，分支 track2/p1-training。起因：`agent-doc/plan-t12fall-2026-10-20.md` 按登记的读法分不出摔之前先坏的一项，登记的下一步（查看器逐帧看）
要 rxzhou 在场；ml40 17:40 空着（`results/ops/status_ml40_1020_1740.txt`）。这一份先回答一个更上游的问题，不用人看。只用 Tier 2 的参考与策略；只诊断，不训练、不提交。

## 0. 事实（都有记录）

1. **训好的策略都摔**：ep4 的 1024 个世界都在第 92–96 帧摔（躯干对参考的倾斜误差 > 0.6 rad），ep25 摔倒帧中位 183（`results/ml40/t12fall/mech_ep{4,25}_w1024.txt`）；
   手臂不去够物体的保底策略也摔（Tier 2 ep25 第 195 帧、ep28 第 204 帧，`results/ml40/t12lift/contact_window_ho_ml40.txt`）。
2. **参考回放的 checkpoint 在 mf4090 上**：`smoke-t2-ep{4,25,1}-w2048-cap4m-r3a-sd-mf4090/policy_409600.safetensors`（各约 4.9 MB）。`zero_dense` 头初始残差为 0，
   第 409600 步（replay 最小量）最多更新过一批，基本就是 SONIC 解码器照参考的零残差动作（`agent-doc/plan-t2sd-2026-10-19.md` 事实 4）。
   4096 世界 MPPE：ep4 111.48、ep1 57.27、ep25 72.65（`results/t2rp/near_miss_mf4090.txt`、`agent-doc/plan-t2sd-2026-10-19.md`）。
3. **评测只要 policy 文件**：checkpoint 带自己解析过的配置（`evaluation/harness.py` 文件头），参考 parquet 在 ml40 上路径相同（`/repo/runs/motion/tier2/…`）。
4. **工具**：`diag_rollout.py --palms --bodies` 与 `fall_mechanism.py`（t12fall 用过，G0 与同步闸都过）；服务器之间搬文件走私有 HF 中转仓（`tools/hf_transfer.py`）。

## 1. 做什么

1. mf4090 上 `hf_transfer.py push --tag t12replay_1020 --dirs <三个 policy 文件所在的暂存目录>`（只放三个 policy 文件），ml40 上 `pull` 到 `runs/flash_chord/<同名 run>/`；sha256 逐个核。
2. ml40（用前查卡空；挂 fc_8c778f9，同那几份评测）：三条各 1024 个世界 `diag_rollout.py <policy_409600> … --worlds 1024 --palms --bodies`，再 `fall_mechanism.py`。约 10 分钟。

## 2. 判据（登记）

- R0：三条的 G0 与同步闸照 t12fall 的门槛；G0 不过的那条只报数字（ep1 训好的那条右脚踝就差 2.9 cm）。
- R1（参考本身跟不住）：ep4 回放摔倒的世界 ≥ 50%，且摔倒帧中位 ≤ 133（参考第一次接触之前）：训出的残差没把它带偏，SONIC 照参考走就会摔；下一步改参考的走路段（另写计划）。
- R2（残差带偏）：ep4 回放摔倒的世界 ≤ 10%：零残差不摔，是训练把它带偏了；下一步看训练这一侧（另写计划）。
- 介于两者之间：记“看不清”，下一步查看器逐帧看。ep25 同样报，读法同 ep4（接触帧换成 102），只报，不单独定方向。

## 3. 风险

- 第 409600 步的策略可能已被一批更新改动了一点；与真正的零残差回放可能有小差别，读数只当近似。
- 回放时物体照样会被碰到，物体的动作会反过来影响平衡；只看躯干倾斜，物体的影响不单独分。

## 执行记录

（空）
