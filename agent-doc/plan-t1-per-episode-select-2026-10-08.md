# 计划：Tier 1 逐条选 checkpoint，按实际交上去的那条轨迹的分数选（2026-10-08，第 2 版）

第 1 版经 Fable 5.1 审查（GO WITH FIXES），8 条意见的处理见文末“审查与处理”；与正文冲突处以文末为准。

用户 10/8：“Tier 1 逐条选，按实际交上去的那条轨迹的分数选。……依旧先规划 review plan 再 execute”；同日要求计算不放在 Mac 上做。
这条决定替换 10/2 登记的“按规则、不按分数挑”（`agent-doc/plan-submission-exports-2026-10-02.md` 第 3.1 节），只用于 Tier 1；Tier 2 不变。时间一律 UTC-6。

## 1. 事实

- 规则（kit `config/tracks.json`、`tracks/track_2/README.md` 原文）：每档四个榜用同一份 CSV；每条 episode 一个 checkpoint、评 1 个世界（`worlds_per_episode = 1`）；
  没有隐藏数据（`private_fraction = 0`）；对照干净多视角参考、固定世界系、不对齐（`align_initial_pose = False`）。排行榜给交上去的那条轨迹打分，不重跑策略。
- 打包器 `tools/pack_submission.py` 的 `crosscheck` 用与计分端相同的 `op.episode_metric` 逐条算四项（发布网格按种子 0 采 500 个顶点），只打印合计
  （`locally computed: …`，第 506 行）。所以本地分数就是这条轨迹在排行榜上的分数；10/3 打包时 Tier 1 合计 AUC 0.3780、SP-SR 0.5333、MP-SR 0.2667、MPPE 25.1706 cm
  （`agent-doc/experiments/2026-10-03-submission-check.md` R2）。
- 评测不是逐位确定的：所有世界的初始状态相同（评测场景 `object_scale` 1.0、显式重置在第 0 帧），世界之间的差别来自 GPU 计算的不确定性；同一 checkpoint 重复评，
  4096 世界的 MP-SR 能差 0.02。1 个世界的导出是一次抽样。
- 候选清点（10/8，两台只读）：完成（DONE）、没有 NONFINITE、有 `policy_349999104`、逐帧回放（cfgcheck 里 `source_frame_playback: true`）、Tier 1 参考的 run：
  24 条 episode 只有现在交的那一条；ep6、ep18、ep27、ep29 各 4 条（基线 s42、s43，变体 A s42、s43），ep8 2 条（基线、变体 A），ep20 6 条（另有 cap1m 与 ml40 的 cap10m）。
  已有 1 世界导出的只有现在交的那 30 条（10/3）；要新导出 18 条（mf4090 17、ml40 1）。
- mf4090 磁盘剩 1.6 GB；flash_chord 容器里没有 pandas（打包器要）。ml40 剩 1.8 TB，有 Tier 1 数据集，容器里可用 uv 经腾讯云镜像装包。两台服务器之间不能直连。

## 2. 候选规则

- Tier 1、逐帧回放、DONE、无 NONFINITE、最终 checkpoint 349999104（`fc_export.sh` 的守卫另核 policy 有限）。不用中间 checkpoint。
- 方盒的 ep1、ep7、ep28 只用 #185 几何训的 run（`-p185-`、`-p185g-`）；v0.4.0 几何下训的那几条不进。实时回放（`-rt-`）不进。

## 3. 做法

1. **导出**（mf4090 17 条、ml40 1 条）：`V2D_FC_SRC=<8c778f9 副本> stages/evaluate/fc_export.sh <run> 349999104`（1 世界、写轨迹），后台串行。
   **每个 checkpoint 只导出一次**：已有导出就复用（现在交的 30 条），不重导；导出失败的候选记下、剔除，不重试。不靠重复导出“抽”更好的一次。
2. **集中**：两台的候选导出（json + parquet，各约 1 MB）经 Mac 管道转到 ml40 的 `runs/select_t1/cand/<run>/`（`ssh mf4090 tar … | ssh ml40 tar -x`，Mac 只转发、不计算）。
3. **逐条打分**（ml40，flash_chord 容器，kit 依赖用 `uv pip install --target runs/kitdeps` 装 `pandas<3`、`trimesh`）：`stages/evaluate/select_t1.py` 对每个候选
   建一个只含这一条 episode 的结果目录、一份把 `scored_episodes` 改成这一条的 tracks.json，调官方打包器，解析 `locally computed` 那一行，得到这条轨迹的四项分数。
   kit 用 `update_0f2f9f4b`（与 10/3 打包相同）。
4. **选**：按第 4 节的规则每条 episode 选一个，写 `stages/evaluate/exports/t1_select_1008.tsv`（档位 episode run 步数 机器）。
5. **打包**（ml40）：30 条选中的轨迹放一个目录，官方打包器打出 `runs/submission/csv/track2_tier1_select_1008.csv`，`--code-commit` 用已推到 origin 的当时 HEAD。
   上传器 `--dry-run` 要 Kaggle token（只在 Mac 上），留到用户决定提交时再跑；**不提交**。

## 4. 判据（执行前登记）

- **打分门**：用 `select_t1.py` 逐条重算现在交的 30 条，四项的 30 条平均必须与 10/3 CSV 的本地分数相同（差 ≤ 1e-4）；不满足就停，查原因。
- **选择规则**（每条 episode）：先比 MP-SR（成功优先），再比 SP-SR，再比 ADD-AUC（高者优先），最后比 MPPE（低者优先）；全部相同时保留现在交的那条。
- **只报**：每条 episode 各候选的四项分数与选中者；选中者在某一项上比别的候选差的情况（帕累托冲突）；选中者的 4096 世界 MP-SR（看这一次是不是运气）；
  新 CSV 与 10/3 CSV 的四项合计对比；导出失败的候选。

## 5. 风险

- 1 世界是一次抽样，候选越多越像“抽签”。这是用户定的做法；报告里把每个选中者的 4096 世界 MP-SR 并列，区分实力与运气。
- 打分门保证逐条打分与整份打包的口径一致；AUC 的顶点采样与计分端相同（kit 原文），本地分数即排行榜分数，这一点仍以第一次真实提交为准。
- 档位隔离：只碰 Tier 1。

## 6. 产物

`select_t1.py`（带测试：造的候选分数覆盖选择规则与平手）、导出清单、`results/select_t1/` 下的打分与选择记录、执行记录、jev 核结论。

## 审查与处理（Fable 5.1，GO WITH FIXES）——第 2 版

审查确认：打包器逐条算、再取平均，与计分端（`metric_code/track_2/*.py` 的 score）同一做法；单条 episode 的 `scored_episodes` 配置得到的正是这一条在整份里的那一项。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | must | ml40 是 rsync 副本，`pack_tier.sh` 的守卫（工作树干净、HEAD 已推、kit zip sha、CSV 已存在就拒绝、record）都不跑 | 打包前先提交并推送 `select_t1.py` 与选择清单；ml40 上打包前核 `.v2d-source-commit` 等于 `--commit-url` 的 sha、且没有 `-dirty` / `-syncing`；核 kit zip 的 sha256 = 0f2f9f4b…；CSV 已存在就拒绝；经 `scripts/dev/record` 落盘 |
| 2 | must | 解析打印行有损且会默默出错（缺 NaN 指标、4 位小数、打包器非零退出） | 不解析打印：进程内替换 `crosscheck` 拿全精度；任一指标缺失或打包器失败的候选剔除并报告，不当 0 分；先核网格目录存在 |
| 3 | should | 打分门把“逐条 = 整份”与“ml40 环境 = Mac 环境”混在一起 | 拆成 A 门：ml40 上整份打包现在交的 30 条，与 30 条逐条分数的平均相差 ≤ 1e-9；B 门：ml40 整份与 10/3 的打印值相差 ≤ 1e-4。依赖钉成 10/3 的版本（numpy 2.5.3、pandas 2.3.3、pyarrow 25.0.1、trimesh 5.1.1）；先按 10/3 导出链结果表核现在交的 30 份文件的 sha256 |
| 4 | should | kit 与网格不在 ml40 上 | kit 目录与 zip 经 Mac 管道传到 ml40（只转发），核 zip sha256；打分前核 `data/challenge/track_2/tier_1_multiview_caption/mesh/` 存在 |
| 5 | should | 裸循环 `fc_export.sh` 遇 GPU 占用、缺记录文件、磁盘满会默默少候选 | 改用 `export_chain.sh`（候选清单、`V2D_FALLBACK_MAX=0`、等 GPU、sha256 结果表、record）；只有状态 `ok` 的进候选，其余状态如实报告 |
| 6 | should | 失败的 episode 上 AUC 贴近 0、MPPE 没有上限，先比 AUC 再比 MPPE 不合理 | 成功率两项之后改按 `AUC / 0.3780 − MPPE / 25.1706`（以 10/3 合计归一）取大者；平手仍保留现在交的那条 |
| 7 | nit | 老 run 能否被 8c778f9 加载 | 10/3 已导出过 v0.4.0 训的 checkpoint；导不出的按退出码记下、剔除 |
| 8 | nit | kit 新鲜度、运气列、候选目录只放 episode 文件 | kit 新鲜度在真提交前（Mac 上 dry-run 时）重核；运气列只用已有的 4096 世界 JSON；打包时只复制 `episode_XXXXXX.{json,parquet}` |
