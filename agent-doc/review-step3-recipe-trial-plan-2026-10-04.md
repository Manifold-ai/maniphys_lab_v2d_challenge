# 审查：第 3 步配方试验计划第 1 版（2026-10-04，Fable 5.1）

审查对象 `agent-doc/plan-step3-recipe-trial-2026-10-04.md` 第 1 版（faa5474）。审查人是独立的 Fable 5.1 agent，只读仓库与 FlashCHORD 源码副本，不连服务器。下面是原文，处理意见见文末。

**总评：GO WITH FIXES。** 第 1 节的事实我逐条核到源码和结果文件，基本都对；变体 A 的取值论证和“只改取值、8c778f9 能读”也成立。但按现有链的机制，中途检查做不到；判据有两处能钻的洞（S5 排除没跑完的 run、S2 没边距）；变体 A 最可能出的问题——VOC 撤掉后朝向终止大面积触发——没有任何闸看得见，Tier 2 不通过时归不了因。这些改完再跑。

### M（必须改）

**M1. 中途检查与链的机制对不上，按第 7 节的起法做不到。**
- 证据：`stages/evaluate/day2_eval_chain.sh:32–36` 要等训练链日志最后一行变成 `DAY2_TRAIN_DONE/FAILED` 才开始评任何一条；`stages/policy/day2_train_chain.sh:67–120` 先把期望表里全部冒烟跑完，再按行序跑全部正式。单链 15 行时，“5 条变体 A seed 42 评完”要等 15 条全训完（约 33 小时）才发生。另外评测链 `:41`、训练链 `gpu_check` 见到卡上有别的进程就停，所以段与段只能串行。
- 改法：拆三段（A：变体 s42×5；B：基线 s43×5；C：变体 s43×5），各自期望表、冒烟/正式队列、评测链。B 段照 `stages/policy/chain_after.sh` 的做法等 A 的评测链 `DAY2_EVAL_DONE` 再起，但 `chain_after.sh:16–22` 的门槛只认“完成条数”，要换成（或再加）`trial_verdict.py --midcheck` 的结论；这一步要在服务器上自动做，Mac 会离线。时间预算加 A 段评测与决策的等待（约 30–40 分钟）。

**M2. S5 不参与判定，而“没跑完的按跑完的算”是单边有利的分叉路径。**
- 证据：计划第 97 行“S1–S4 都过判通过”，S5 不在条件里；第 95 行“S1–S4 按跑完的算并注明”。变体 A 若让某条训练崩（看守止损退出码 9、训完 NONFINITE 退出码 10，`stages/policy/fc_run_watched.sh:32–39`），这条被剔除后 S1–S4 只在幸存者上算，对变体 A 只会更好看。
- 改法：事先登记——变体 A 的 run 因训练原因没跑完，该 episode 该 seed 的 MP-SR、SP-SR 记 0、ADD-AUC 记该 episode 的不动基线值、MPPE 记基线值（或整条 episode 直接计为变体 A 失败）；只有基线 run 没跑完才允许“注明后按跑完的算”。S5 写进通过条件：任何一条变体 A 没跑完，这一档不得判通过。

**M3. 变体 A 最大的训练风险没有闸：朝向终止在 VOC 撤掉后会大面积触发，冒烟看不见，S5 不管。**
- 证据：`results/ml40/t2/wandb_by_stage_trial_candidates.txt`：ep20 第 4–8 段物体朝向误差 0.41→0.61 rad，ep26 第 0 段（VOC=1）就是 0.32、第 4 段起 0.55–0.62，ep24 第 4 段起 0.37→0.51。这一列是“窗口内全部世界步的逐世界误差的均值”（`training/flash_sac/runner.py:307–309`），均值在 0.6 附近说明相当比例的世界步会越过 0.6 rad；终止是冻结期后逐步判、`>` 阈值（`lifecycle/termination.py:636, 643–646`），每次 −300×frame_dt≈−6（权重 `configs/curriculum/recon_body_flash_sac.yaml:13`，`objectives/recon_body.py:234, 310`），之后这个回合的进度项与后段样本都没了。冒烟只有 400 万步、第 0 段、VOC=1（冒烟队列行 4096000），训练健康 S5 只看有限性与 DONE。
- 改法：事先登记一条训练健康判据，并在第 6 段边界（2.1 亿步，开跑约 70 分钟后）对每档第一条变体 A 用 `stages/policy/wandb_local_history.py --by-stage` 读在跑的 .wandb 查一次，例如“第 6 段 终止:物体 > 0.5，或 进度 < 基线同段的一半”——判停还是只报要写死；至少要把这种结局登记成 Tier 2 不通过时的归因之一（“物理上做不到”与“配方无效”要分得开）。ep26 在 VOC 全开时对 v5.4 的朝向误差已 0.32 rad，这个数应写进第 6 节。

**M4. S2 没有边距，Tier 2 上是空判据。**
- 证据：Tier 2 五条基线 MP-SR 是 0.021、0.001、0、0、0.006（`results/ml40/day2/eval_t2-ep{8,12,20,24,26}-…_s349999104.txt`），任何 >0 的数都算“赢”。同一 checkpoint 两版评测器 MP-SR 差 0.007（box6 P4：0.5623 对 0.5696），同版评测器重复评的噪声没量过。
- 改法：S2 改成 MP_A(e) ≥ MP_B(e) + 0.05（或 + 2 倍同版重复 SD）。G1 时顺手把一条基线 checkpoint 用 8c778f9 评两次（约 5 分钟）量出同版重复噪声，写进记录。

**M5. 正向核对不断言变体字段，漏写一个覆盖就会以 r3a 的名字训出一条基线。**
- 证据：`stages/policy/precheck_expect.sh:37` 只断言 parquet、回放、support、capacity、步数、世界数、seed、motion_speed；`stages/policy/assert_cfg.py` 文档第 3 行自己写明 cfg_diff 只拦意外差异、漏写覆盖照样过。`fc_config_check.sh:26–27` 的 `env.` 放行只对 `reset.*`，第 7.2 条说对了，还要补测试。
- 改法：期望表加一列“配方”（或 arm 脚本加一步），变体行断言 `objective.object_position_std=0.05 env.objective.object_position_std=0.05 termination.object_orientation_threshold=0.6 env.termination.object_orientation_threshold=0.6`，基线行断言 0.2 / 1.5；`fc_config_check.sh:27` 的 case 加 `objective.*|termination.*`。配置里只有 `configs/env/rl.yaml:13, 16` 两处引用，没有第三份副本（核过 `configs/`）。

### m（建议改）

**m1. 档位隔离的标注。** ADR-00002 Consequences 写“任何看过 Tier 1 结果之后的改动都要单独标注并重新论证”。变体 A 的假设最早出自 Tier 1 失败分析（ep15/ep17），第 1 节“训练记录指向同两处”又把 Tier 1 的 ep15/ep17 并列作证据。Tier 2 部分单独写一段只用 Tier 2 证据的论证（材料够：Tier 2 评测 3 条卡朝向 2 条卡位置、Tier 2 wandb 的漂移、代码里没有朝向项、σ=0.2 在 3 cm 处的斜率），标注“在看过 Tier 1 结果之后提出”；Tier 2 的判定记录与 `trial_verdict.py` 输出里不出现 Tier 1 的数。取值 3 cm/30° 来自公开指标常数，不是 Tier 1 数据，这点成立。

**m2. 回归均值。** 5 条按 seed 42 结果挑的，基线 s42 是被选中的样本，(s42+s43)/2 仍带着它。建议同时报告“变体两种子均值 − 基线 s43 单种子”作敏感性分析，主判据仍按登记写法（事先写明哪个是主）。中途检查 s42 对 s42、偏差方向不定、只判停，可接受。

**m3. 没有“已过关”的 canary。** 试验全是差一点的，变体 A 若让 MP>0.95 的 episode 退步（更紧的核、更多终止），铺开前看不到；§5 乙按分挑能兜住分数，但每档 25 条×2 小时就白烧。建议每档加 1 条（Tier 1 ep8 0.98 或 ep24 0.96；Tier 2 ep22 0.72），变体 A seed 42 一条即可，登记“canary MP 不低于基线 −0.10”。

**m4. S1 的分辨力写清楚。** 中段单 run 的 SD 没量过；若按 0.2 算，S1 统计量 SD≈0.09，0.15 门槛相当于 1.7 SD，假阳性约 5%，对真实 +0.15 的检出率约 50%；SD 0.3 时假阳性约 13%。写进计划：S1 不过不等于变体 A 无效；基线 s43 的数据只用于事后报告噪声，不改门槛。

**m5. S4 只看 5 条平均。** 单条大退步会被平均掉；加逐条报告，登记“任一 episode ADD-AUC 退 > 0.05 列为不通过理由”或至少报。SP-SR 项对 Tier 2 三条朝向 episode（基线 0.001 / 0.11 / 0）几乎无约束。

**m6. 第 64 行措辞。** “34° 的逐帧上限比 MP-SR 的要求更严”不准：逐帧 <34° 不保证按帧平均 <30°，反之平均 <30° 也允许个别帧 >34°。方向一致，但别写“更严”。

**m7. 磁盘与 arm 脚本的两个环境变量。** state 是 160 MB（`results/ops/hf_archive_run_mf4090.txt:75–77`），35 份 policy 按 1,207,577 参数×4 B 约 170 MB，合计 0.33 GB/run 与计划一致。但 mf4090 的 1.2 GB 门槛和冒烟 state 剪除都来自 `arm_nfg_chains.sh:12` 的 `V2D_MIN_FREE_MB=1200 V2D_PRUNE_SMOKE_STATE=1`，训练链默认是 2048 MB、不剪（`day2_train_chain.sh:47–51`）；新 arm 脚本要照抄，否则 15 条冒烟 state 再吃 2.4 GB。`V2D_KEEP_STATES=1` 时每 60 秒剪一次，峰值 2 份。8.7 GB 这个数我没法核（不 ssh）；建议试验前就把旧 run 的 state 归档，别留到铺开。

**m8. 基线重评与新 run 评测落在两种路径，`trial_verdict.py` 要都认且核来历。** 基线用 `fc_export.sh`（`V2D_EXPORT_WORLDS=4096 V2D_EXPORT_TRAJ=0`）写到 `export_8c778f9/s349999104_w4096/episode_xxxxxx.json`；新 run 由评测链用 `fc_eval.sh` 写 `eval_349999104_w4096.json`（评测链环境 `V2D_FC_SRC=fc_8c778f9`，`arm_nfg_chains.sh:33`）。两条路的评测参数一致（`configs/evaluation/flash_sac.yaml:6–8` 默认 explicit、4096、start_frame 0、deterministic；`fc_export.sh:64` 显式同值）。判定脚本要核每份 JSON 的 `eval_code_sha256` 等于 8c778f9 的 b1b3ebe3…，防止误读旧 v0.4.0 结果；chord_sr 干脆不读。

**m9. 导出规则。** `stages/evaluate/export_map.py:36` 的正则 `t1-ep(\d+)-w2048-(cap10m-ml40|cap4m-mf4090)` 不认 `-r3a-`、`-s43-`，§5 已说要改规则与测试；甲/乙两种挑法都要落成规则（“每条 episode 恰好一条 run”是硬断言，`:77–82`）。fc_run / fc_export / precheck 的名字正则都放行新名字（核过）。

**m10. Tier 2 对照 v5.4 的局限写具体。** 降噪计划里 v5.4 静置段倾斜残差中位 4.98° / 19.59°，参考本身对真值可能偏约 20°；把策略对 v5.4 的朝向误差从 32° 压到 25°，对排行榜的收益不确定。建议 Tier 2 记录里按 episode 报“VOC 全开段的朝向误差”作参考质量旁证，供降噪计划用。

**m11. 时间预算补两项。** 训练链先跑完 15 条冒烟（每条含冒烟检查与 256 世界 rollout 约 10 分钟，约 2.5 小时）才开正式训练；拆三段后每段各有前置；总体约 34–36 小时，另加中途检查的等待。

### 我核过、没问题的事实

- 配方：349999104 步、2048 世界、`source_frame_playback: true`（`configs/experiment/g1_recon_body_flash_sac.yaml:17, 22, 52`）；课程 9 段、VOC 1→0.75→0.5→0.25→0.1→0.05→0，第 7 段起点 209999872，最后两段 `immediate_first_frame_probability` 0.25 / 0.50，权重用同一 YAML 锚点、12 项与 `configs/objective/recon_body.yaml` 相同（`configs/curriculum/recon_body_flash_sac.yaml:7–50`）。
- 奖励 12 项、无物体朝向项（`objectives/recon_body.py:26–39`）；物体位置项 `exp(-|e|²/σ²)`（`:276–278`），目标是参考物体位置（`runtime/command.py:189–191`）；σ 来自 `self.config.object_position_std`（`:552`），各段 `set_weights` 只换权重（`training/environment.py:252`）。0.2 时 1/3/5 cm 为 0.998/0.978/0.939；0.05 时 0.961/0.698/0.368，10 cm 0.018，3 cm 处斜率比 11.4 倍。
- 终止阈值 1.50 / 0.10 / 冻结 50（`configs/termination/recon_body.yaml:6–8`）；两处几何夹角都是双覆盖感知的测地角（`utils/quat.py:64–67`，`evaluation/metrics.py:137–141`），无对称性处理，口径一致。
- MP-SR `<0.03 m` 且 `<30°`，SP-SR `≤0.1 m` 且 `≤0.5 rad`（`metrics.py:21–24, 315, 344–346`）；ADD-AUC、MPPE 只用常数。评测把六个阈值改成 1e6（`harness.py:59, 196–199`），chord_sr 的阈值在改之前取（`:141–158`，调用顺序 `:343–345`）；环境由 checkpoint 配置重建（`:349`），课程段取 metadata（`:384–393`）；`ReconBodyObjectiveConfig` / `ReconBodyTerminationConfig` 对 0.05、0.6 的校验都过（`recon_body.py:86–97`，`termination.py:512`）。
- 第 1 节两档全部 MP-SR / 位置 / 朝向数值与 `results/day2`、`results/ml40/day2` 的 `summary_json` 一致（含 ep20 的 s42/s43 对、ml40 rt 0.887、逐帧 0.016 / 0.0005）；Tier 2 五条按课程段的朝向与位置数值与 `wandb_by_stage_trial_candidates.txt` 一致。
- 10 条试验 episode 都是现在导出的 run（`stages/evaluate/exports/{mf4090,ml40}.tsv`）；支撑面是 Cylinder 或 empty（`results/t2/support_kinds_tier2_mf4090.txt`），#185 只改带 `xformOp:scale` 的 Cube（`third_party/patches/flash_chord-v0.4.0-cube-support-scale-8c778f9.patch`），对它们无影响。
- `reset.seed=43 training.seed=43` 的写法与 9/30 的 s43 行一致（`stages/policy/queues/mf4090_day2.txt:5`），`training.seed` 是 `${reset.seed}` 的引用（`configs/training/reference_flash_sac.yaml:3`），两键都显式写出才能过 cfg_diff（`results/day2/cfgcheck_mf4090_day2.txt` 的 rt-s43 段 17 处差异、意外 0）。
- 两次重训用时 1:57:28、1:59:55（`agent-doc/experiments/2026-10-03-ep7-nfg-retrain.md`）；K1 6400 次世界评估逐位相同、K3 只换非有限值（`2026-10-02-nfg-gates.md`）；box6 P4 两版评测器差 ADD 0.0014、MP 0.5623 对 0.5696。
- 中途检查“只许判停”是无效性停止，不抬高假阳性率，这个论断成立。
- 两档各在一台机器上做比较，buffer 在每档内部恒定；基线 s42 旧副本与其余三组新副本的差异，在无事件时按 K1/K3 为零，GPU 本身不逐位可复现，这个混杂可以接受。
## 处理意见（2026-10-04，计划第 2 版）

承重的说法先在源码与结果文件里核过再改：评测链等整个训练链结束（`day2_eval_chain.sh:32–36`）、训练链先跑完全部冒烟（`day2_train_chain.sh:67–120`）、
正向核对不断言变体字段（`precheck_expect.sh:37`）、训练记录的跟踪误差是世界步平均（`runner.py:307–309`）、对照序列的数（Tier 1 ep8 0.979、Tier 2 ep22 0.724）都属实。

| 意见 | 处理 |
|---|---|
| M1 中途检查与链机制 | 采纳。每档分 A 段（变体 seed 42 五条加对照一条）与 BC 段（基线 seed 43 五条、变体 seed 43 五条），段间门在服务器上跑 `trial_verdict.py --midcheck`。B、C 之间没有决定要做，所以分两段而不是三段 |
| M2 S5 与没跑完的 run | 采纳。S5 成为通过的必要条件：变体 A 有一条因训练原因没跑完，这一档不能判通过；基线 seed 43 没跑完时这条 episode 的 B 只用 seed 42，注明 |
| M3 朝向终止大面积触发 | 部分采纳。登记为只报的归因项（第 6–8 段终止:物体 ≥ 基线 2 倍且进度低 0.1 以上，记为“终止过严或参考做不到”）；不在训练中途止损，中途检查已把浪费限在 A 段。ep26 VOC 全开时 0.32 rad 写进第 1.3、6 节 |
| M4 S2 没有边距 | 采纳。S2 改为 MP_A(e) ≥ MP_B(e) + 0.05；闸 G1 量同版评测器的重复噪声（只报） |
| M5 变体字段不断言 | 采纳。起链脚本按 run 名（`-r3a-`）用 `assert_cfg.py` 断言四个字段；`fc_config_check.sh` 的放行加 `objective.*`、`termination.*`。期望表格式不动，因为几个脚本按固定列读它 |
| m1 档位隔离的标注 | 采纳。第 2 节写明变体 A 是看过 Tier 1 失败分析后提出的，Tier 2 的论证只用 Tier 2 证据；第 1 节分成 Tier 1、Tier 2 两小节；Tier 2 的判定输出不出现 Tier 1 的数 |
| m2 回归均值 | 采纳。另报“变体两种子均值 − 基线 seed 43” |
| m3 已过关的对照 | 采纳。每档加一条（Tier 1 ep8、Tier 2 ep22），S6：对照的变体 MP-SR ≥ 基线 − 0.10 |
| m4 S1 的分辨力 | 采纳，写进第 4 节 |
| m5 S4 只看平均 | 采纳。S3 加“没有一条 ADD-AUC 退 0.05 以上” |
| m6 “更严”的措辞 | 采纳，改成判法不同、方向一致 |
| m7 磁盘与环境变量 | 采纳。照抄 `V2D_MIN_FREE_MB=1200 V2D_PRUNE_SMOKE_STATE=1`；可用空间按 10/4 晚的 8.5 GB；旧 state 归档仍放在铺开前，删本地要问用户 |
| m8 两种评测输出与来历 | 采纳并改法：8c778f9 经 `fc_eval.sh` 写的指标 JSON 里没有评测代码哈希（核过 `t2-ep7-…-p185g-ml40` 的键），来历改为核 checkpoint sha256 加评测日志里 `in-flash-chord` 记的 `/workspace` 来源；判据不读 chord_sr |
| m9 导出规则 | 采纳，写进第 5 节 |
| m10 Tier 2 对照 v5.4 的局限 | 部分采纳。意见里“v5.4 静置段倾斜残差中位 4.98° / 19.59°”是降噪前观测的残差（`cleanroom_params.py` 在观测轨迹上算），不是 v5.4 自身的误差，不采用这个数；采用的是按 episode 报 VOC 全开段的朝向误差，并补上参考陷进支撑面的事实（ep20 −22.1 mm） |
| m11 时间预算 | 采纳，每档约 35 小时加段间约 1 小时 |

另外，审查之后核 GPU 时发现 mf4090 上有别人的进程（`maniphys_visual_worker`，2.7 GB），训练链的 GPU 检查会直接停链，写进第 1.4、8 节，由用户定。
