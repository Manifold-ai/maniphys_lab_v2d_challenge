# 计划：参考回放会不会在同样的帧摔——分清“参考本身跟不住”与“训出的残差带偏”（t12replay，10/20 傍晚，第 2 版）

2026-10-20 17:4x MDT 写定第 1 版，18:1x MDT 按独立复核改成第 2 版（改了什么见文末），分支 track2/p1-training。起因：`agent-doc/plan-t12fall-2026-10-20.md` 按登记的读法分不出摔之前先坏的一项，登记的下一步（查看器逐帧看）
要 rxzhou 在场；ml40 17:40 空着（`results/ops/status_ml40_1020_1740.txt`）。这一份先回答一个更上游的问题，不用人看。只用 Tier 2 的参考与策略；只诊断，不训练、不提交。

## 0. 事实（都有记录）

1. **训好的策略都摔**：ep4 的 1024 个世界都在第 92–96 帧摔（躯干对参考的倾斜误差 > 0.6 rad），ep25 摔倒帧中位 183（`results/ml40/t12fall/mech_ep{4,25}_w1024.txt`）；
   手臂不去够物体的保底策略也摔（Tier 2 ep25 第 195 帧、ep28 第 204 帧，`results/ml40/t12lift/contact_window_ho_ml40.txt`）。
2. **参考回放的 checkpoint 在 mf4090 上**：`smoke-t2-ep{4,25,1}-w2048-cap4m-r3a-sd-mf4090/policy_409600.safetensors`（各 4,860,0xx 字节，mf4090 上 `ls -la`）。
   **残差均值头量过是严格的 0**（`stages/evaluate/residual_head_norm.py`，`results/t12replay/residual_head_mf4090.txt`）：第 409600 步里 state.0015、state.0018 (256×43)、
   state.0019 (43) 的最大绝对值都是 0；同一 run 第 4096000 步 0.233、0.142、0.019，训好的 t2-ep4-w2048-cap4m-mf4090 0.480、1.686、0.984。评测取确定性动作，
   所以这几个 checkpoint 就是零残差回放（SONIC 解码器照参考）。上游另有 `scripts/debug/replay.py --config-name=sonic_replay`，但它用 VOC 把物体推向参考、只渲一个世界，
   与评测器不可比，所以用 checkpoint 走评测器。
   4096 世界 MPPE：ep4 111.48、ep1 57.27、ep25 72.65（`results/t2rp/near_miss_mf4090.txt`、`agent-doc/plan-t2sd-2026-10-19.md`）。
3. **评测只要 policy 文件**：checkpoint 带自己解析过的配置（`evaluation/harness.py` 文件头），参考 parquet 在 ml40 上路径相同（`/repo/runs/motion/tier2/…`）。
4. **工具**：`diag_rollout.py --palms --bodies` 与 `fall_mechanism.py`（t12fall 用过，G0 与同步闸都过）；服务器之间搬文件走私有 HF 中转仓（`tools/hf_transfer.py`）。

## 1. 做什么

1. 搬运（私有仓 `Rongxuan-Zhou/v2d-track2-transfer`，凭据只经 `tools/hf_remote.sh` 的 stdin）：mf4090 上用 `cp` 把三个 policy 放进 `runs/t12replay_stage/<run>/policy_409600.safetensors`
   （不用软链接）；`tools/hf_remote.sh 'python3 runs/tools/hf_transfer.py push --repo Rongxuan-Zhou/v2d-track2-transfer --tag t12replay_1020 --dirs runs/t12replay_stage'`；
   README 补 `t12replay_1020` 一行并上传；ml40 上（`V2D_ENV=ml40 tools/hf_remote.sh …`）`pull --dest runs/hf_pull/t12replay_1020`（新建的空目录），
   再逐个 `mv` 到 `runs/flash_chord/<run>/`（新建这三个目录），三个 sha256 与清单比对记进 `results/`。
2. ml40：`stages/evaluate/t12replay_chain.sh <run>:409600:<序列>…`（tmux）：每条用前等卡空，`diag_rollout.py … --worlds 1024 --palms --bodies` 给 `V2D_GPU=1`、挂 fc_8c778f9，
   同步闸与 `fall_mechanism.py` 给 `V2D_GPU=0`。约 10 分钟。

## 2. 判据（登记）

- R0：三条的 G0 与同步闸照 t12fall 的门槛；G0 不过的那条只报数字（ep1 训好的那条右脚踝就差 2.9 cm）。
- R0b：残差均值头为 0（已量，见事实 2）。
- R1（参考本身跟不住）：ep4 回放摔倒的世界 ≥ 50%、摔倒帧中位 ≤ 133（参考第一次接触之前），并且同时满足两条（复核 MAJOR 3）：
  (a) 摔了的世界里，摔倒那一帧物体离起点 < 5 cm 的 ≥ 90%（摔倒不是手先碰飞物体引起的；`fall_mechanism.py` 第 2 版这一行）；
  (b) 回放的摔倒帧中位与训好的策略（94）相差 ≤ 10 帧（同一种摔法）。满足 → SONIC 照参考走就会摔，下一步改参考的走路段（另写计划）。
  只满足前一句、(a)(b) 有一条不满足 → “摔了，但不是同一种摔”，下一步查看器逐帧看。
- R2（残差带偏）：ep4 回放摔倒的世界 ≤ 10%：零残差不摔，是训练把它带偏了；下一步看训练这一侧（另写计划）。
- 介于两者之间：记“看不清”，下一步查看器逐帧看。ep25 同样报，读法同 ep4（接触帧换成 102），只报，不单独定方向：ep25 的回放 4096 世界 MPPE 72.65 本来就比训好的 117.09 低，
  两者读数不同是预期之内，不当矛盾。

## 3. 风险

- 第 409600 步的策略可能已被一批更新改动了一点；与真正的零残差回放可能有小差别，读数只当近似。
- 回放时物体照样会被碰到，物体的动作会反过来影响平衡；只看躯干倾斜，物体的影响不单独分。

## 复核

第 1 版交 Fable 5.1 独立复核：**GO WITH FIXES**。核过：事实 1–3 与记录一致；diag_rollout 只传 checkpoint、parquet 路径取自 checkpoint 自带配置，两台上 Tier 2 的 parquet 同 md5；
训好的与回放都用 fc_8c778f9 评；等卡、不停别人的进程；凭据只经 hf_remote.sh；只用 Tier 2。按意见改的：
1. （major）搬运步骤写实：暂存目录、一个空的 pull 目录再 mv，README 补一行。
2. （major）另写 `t12replay_chain.sh`（run、步数为参数），rollout 给 V2D_GPU=1。
3. （major）R1 加 (a) 摔倒时物体没被碰飞、(b) 摔倒帧与训好的相差 ≤ 10 帧；`fall_mechanism.py` 加摔倒那一帧物体离起点的读数。
4. （minor）残差头直接量过是 0（R0b）；写明不用上游 replay 脚本的原因。
5. （minor/nit）仓库名、各步在哪台机器上跑写明；文件大小按服务器 `ls -la`；ep25 的读数不同是预期之内。

## 执行记录

- 17:4x MDT：mf4090 上三个 policy 复制进 `runs/t12replay_stage/`，推到 `Rongxuan-Zhou/v2d-track2-transfer` 的 `t12replay_1020/`（HF_PUSH_OK 3，清单缺 0、不符 0、多出 0，
  `results/t12replay/hf_push_mf4090.txt`）；README 补一行并上传（HF_README_OK，`results/ops/hf_readme_v2d_track2_transfer_t12replay.txt`）；ml40 上拉到 `runs/hf_pull/t12replay_1020`
  （HF_PULL_OK 3，14.6 MB，`results/t12replay/hf_pull_ml40.txt`），挪进 `runs/flash_chord/<run>/`，三个 sha256 与 mf4090 上逐字节相同（`results/t12replay/sha256_ml40.txt`）。
- 17:5x MDT：ml40 上的 `fall_mechanism.py` 与仓库任何一版的 md5 都不同，`push-new-files` 拒绝覆盖；ml40 没有链在跑，按 `scripts/dev/remote` 整体同步（先空跑：只删 7 个 `__pycache__` 与一个锁文件，
  `results/box/sync_ml40_1020_t12replay.txt`），来历 ee177b46。17:51 MDT tmux `v2d-t12replay` 起 `t12replay_chain.sh`（ep4、ep25、ep1 的第 409600 步，日志 `runs/logs/t12replay_ml40.log`）。
- 18:0x MDT 读数（`results/ml40/t12replay/mech_*_s409600.txt`、`sync_*`）：R0 三条 G0 都过（第 0 步位置差 0.2–1.3 cm、躯干朝向差 0.006–0.016 rad），同步闸都 SYNC_OK；R0b 见事实 2。
  - **ep4：R1 成立。** 回放摔倒的世界 1024/1024，摔倒帧分位 10/50/90 = 88 / 88 / 89（≤ 133）；(a) 摔倒那一帧物体离起点 < 5 cm 的 100%（中位 0.001 m）；(b) 与训好的 94 相差 6 帧。
    SONIC 照参考走就在同一处摔，训出的残差没救回来；下一步改参考的走路段（另写计划）。回放第 50、75、100 帧：脚离参考 0.101、0.180、0.184 m，骨盆 0.081、0.165、0.459 m，躯干倾斜误差 0.191、0.292、1.143 rad。
  - ep25（只报）：回放摔倒的世界 22.7%，摔倒帧中位 467；训好的 100%、中位 183：ep25 是训练带偏的，与 MPPE 72.65 → 117.09 一致（预期之内）。
  - ep1（只报）：回放摔倒的世界 85.8%，摔倒帧中位 274。

