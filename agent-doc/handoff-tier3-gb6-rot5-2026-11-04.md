# 交接：Tier 3 第二份 final `tier3_cari4d_gb6_best_dr2s_dyn7`（2026-11-04 EST）

分支 `track2/tier3-recon`，代码 commit `af1f37f4`（L40S 部署版，`$T/code/DEPLOYED`）；之后的 `fc3a5a96` 只把 GPU 占位的睡眠上限改成 3 小时，不影响产出。计划与预期见 yqchen 本地 `~/v2d/synth-hoi/plan-tier3-rot5-submission-2026-11-04.md`（不在仓里，要点抄在下面）。

## 是什么

交付版 `tier3_cari4d_gb5_best_dr2s_dyn7` 那份提交不动，再交一份作为第二个 Final Submission（Kaggle 规则 §2.c：每个比赛最多选 2 个 final）。两者只差 FP 选择器的 `ROT_DEG` 一个参数，按集自动决定：

- 规则 `stages/recovery/tier3/t3_rot_rule.py`：只看走 FP 选择器的 13 集。每集在 `ROT_DEG` 10（交付值）和 5 下各选一次；在两次选择结果不同的帧上，比较物体轮廓与 SAM2 掩码的 IoU。5 的均值比 10 高出 0.02 以上，才用 5。只用 Tier 3 自己的输入。
- 预期选中 **ep11、ep17** 两集，其余 28 集与 gb5 逐字节相同。
- 一条命令：`stages/recovery/tier3/t3_rot_full.sh gb6 gb5`（L40S，日志 `$T/logs/rot_full_gb6.log`）。它依次跑规则、两集的选择、CARI4D 06–08、convert、`t3_gb_chain.sh`，最后逐字节比对 28 集。

## 什么时候能用

- 日志末行 `ROT_FULL_DONE` 才算产出完成。末行 `ROT_FULL_FAILED <原因>` 表示这份不交。
- GPU：驱动在你这一段（`t3qr3o2d`）的训练和评测结束、三个 `.chain-active-*` 标记撤掉、卡上没有进程之后 20 秒内上卡，先起占位容器 `rot_hold_gb6`（约 0.5 GB），占到 06–08 和 convert 跑完，日志里会写 `GPU steps done, hold released`，预计 01:00 EST 前后。看到这一行之后再放 `t3qr3o2e` 的接力。
- 之后的后处理链只用 CPU，预计 02:15 EST 前后 `ROT_FULL_DONE`。
- 如果占位残留（驱动不在了，容器还在），`docker stop rot_hold_gb6` 即可。看门狗 `/lab_data/yqchen/v2d/seedance_t3/rotrule/hold_watchdog.sh` 也会在驱动消失或占位超过 3 小时时自动停掉它。

## 训练要做的

- 只重训 `ROT_FULL_DONE` 时日志第 4 步列为「ROT_DEG 5」的集（预期 ep11、ep17）。其余 28 集的参考与 gb5 逐字节相同，沿用 gb5 那份提交用的 checkpoint。
- 版本目录：`/lab_data/yqchen/v2d/tier3/runs/tier3_cari4d_gb6_best_dr2s_dyn7`（以及 `_suspect`），支撑面 usda 在 `$G/support_usda_gb6dyn7`。`ROT_FULL_DONE` 之后由 yqchen 用 `t3_deliver.sh` 把 usda 放进版本目录、写 `DELIVERY.md`，放好后另行通知；在那之前不要开训练。
- 打包：`--frame-references` 用 gb6 的参考，所以这两集的参考是新的，其余 28 集与 gb5 相同。
- 留档（容器复现要用，工具包 `CONTAINER_SUBMISSION.md`）：这份提交的打包文件、上传回执、打包用的工具包副本、30 个被评测的 checkpoint（2 个新训的加 28 个沿用的）、评测器运行时，都要和 gb5 那份提交的产物分开保存，不能覆盖。
- `code_commit_url`：每行必须相同（§2.d），并且对应产出这份提交的代码（§9.a）。这个 commit 要同时包含 `af1f37f4` 的重建代码和你的训练配置，不能填分支链接。

## 不做什么

- 不动 gb5 那份提交，也不改交付版的任何文件（驱动只复制，不硬链接）。
- 不按目测挑集（10-15 定的：Tier 3 的修复只能来自自动方法）。
