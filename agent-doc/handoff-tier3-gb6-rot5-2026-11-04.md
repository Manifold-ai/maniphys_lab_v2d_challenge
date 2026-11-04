# 交接：Tier 3 第二份 final `tier3_cari4d_gb6_best_dr2s_dyn7`（2026-11-04 EST）

分支 `track2/tier3-recon`。产出代码 `af1f37f4`（GPU 段）+ `e6e2f19e`（对齐修复，链路续跑）+ `8a9cc9ce`（驱动第 4 步比对）。版本说明在版本目录的 `DELIVERY.md`，登记在 `stages/recovery/tier3/versions.json`。计划在 yqchen 本地 `~/v2d/synth-hoi/plan-tier3-rot5-submission-2026-11-04.md`（不在仓里，要点在下面）。

## 是什么

第一个 final 不动，再交一份作为第二个 Final Submission（Kaggle §2.c：每个比赛最多 2 个 final）。用户 11-04 定：交；训练照抄第一个 final 里这两集的配置，只换重建（参考）；跟丢换跟丢也换。

- 重建：FP 时间线选择器的 `ROT_DEG` 按集自动定（`stages/recovery/tier3/t3_rot_rule.py`，只用 Tier 3 输入），选中 **ep11、ep17** 用 5，其余用 10（交付值）。复现命令是 `stages/recovery/tier3/t3_rot_full.sh gb6 gb5`，但本次没有端到端跑通（链路对齐步停下后续跑、第 4 步另跑，按现在的代码重跑预期在第 4 步 ep01 停下），细节见 `DELIVERY.md` 的未完成项。
- **第一个 final 里这两集的参考是 hm，不是 gb5**（ep17 `t3-ep17-w2048-cap4m-r3a-hm-mf4090`，ep11 占位 `t3-ep11-w2048-cap10m-r3a-hm-ph-ml40`）。所以两份提交在这两集上的差别是 hm → gb6（中间隔着 gb4、gb5 的选择器改动与 dr2s、dyn7），不只是 `ROT_DEG`。
- 其余 28 集的数据表与 gb5 交付版相同（parquet 元数据只差记来历的版本名）。ep01 支撑面的依靠方块差约 1.4 mm（采样无种子，见 `DELIVERY.md` 已知问题）。这 28 集都不进第二份提交的改动，沿用第一个 final 的 checkpoint 与帧参考。

## 要做的（rxzhou）

1. **入库**：用你自己的流程把 gb6 的 ep11、ep17 收进 `runs/motion/tier3_gb6`（同 gb5 那次：从版本目录取 parquet、元数据与 `support_surface/` 下我们的支撑面 usda，跑你的 retarget）。版本目录 `/lab_data/yqchen/v2d/tier3/runs/tier3_cari4d_gb6_best_dr2s_dyn7`（ep11、ep17 都在主目录，不在 `_suspect`）。我们门槛里的 retarget 输出（`$G/repo/runs/motion/tier3_gb6dyn7`）与你的 retarget 列不同、支撑面是空的，不要用。你的白名单（`tier3_pack_remote.sh`、`t3_episode_remote.sh`）要加 gb6 这个名字。
2. **训练**（L40 `l40n`，卡空着；照抄第一个 final 的两行，只换 parquet 路径与 run 名）：
   - ep17，照 `stages/policy/queues/mf4090_t3p4a.txt` 的 `t3-ep17-w2048-cap4m-r3a-hm-mf4090`：2048 世界、349999104 步、`training.replay.capacity=4000000 objective.object_position_std=0.05 termination.object_orientation_threshold=0.6`，训练副本 `v040_p185_nfg`，seed 42。建议名 `t3-ep17-w2048-cap4m-r3a-gb6-l40n`。约 2.1 小时（按 L40S 实测约 4.6 万步/秒，推断）。
   - ep11，照第一个 final 的占位 `t3-ep11-w2048-cap10m-r3a-hm-ph-ml40`（10-15 `ffee511a`：`t3-ep11-w2048-cap10m-r3a-hm-ml40` 那行训到冒烟长度）：2048 世界、**4096000 步（刻意沿用占位长度，不要训满）**、`objective.object_position_std=0.05 termination.object_orientation_threshold=0.6`，replay 用默认 1000 万（那行没有 capacity 覆盖），训练副本 `v040_p185_nfg`，seed 42（`ml40_t3qa` 期望表）。建议名 `t3-ep11-w2048-cap10m-r3a-gb6-ph-l40n`。
   - 评测用 `fc_8c778f9`，同你的链。
3. **打包**：底是第一个 final 实际交的那个包，只换 ep11、ep17 两行与它们的帧参考（用 gb6 的参考建）。上传前核对 `CSV_EPISODE_DIFF_OK` 只差 11、17。
4. **留档**：这份的打包文件、上传回执、工具包副本、两个新 checkpoint 与 28 个沿用的、评测器运行时，与第一个 final 分开存（工具包 `CONTAINER_SUBMISSION.md`）。`code_commit_url` 要同时含产出代码（`8a9cc9ce` 或之后）与你的训练配置。

## 时间

比赛 11-04 17:00 EST 截止。ep17 训练约 2.1 小时，打包上次约 1 小时：正式训练最晚 12:30 EST 前要起。

## 不做什么

- 不动第一个 final 与 gb5 交付版的任何文件。
- 不按目测挑集（10-15 定：Tier 3 的修复只来自自动方法）。
