# 计划：第 3 步，改动配方的小规模试验（2026-10-04，第 2 版）

第 1 版（faa5474）经 Fable 5.1 独立审查（`agent-doc/review-step3-recipe-trial-plan-2026-10-04.md`，GO WITH FIXES），按意见改成本版，逐条处理写在审查文件末尾。

用户 10/4：“先做第 3 步：用改过的配方在约 5 条序列上小规模试，过了登记的判据再铺开到 30 条。然后 Tier 2 的降噪改进可以和第 3 步并行，
Tier 2 要用它自己的数据另行验证，还是需要先计划的。”工作顺序是用户 10/1 定的：导出与提交流程、诊断、配方试验。第 2 步诊断的对照没过，
结论不成立；本计划挑序列只用评测与训练记录里照实描述的数，不用诊断的结论。Tier 2 降噪另有计划 `agent-doc/plan-tier2-denoise-2026-10-04.md`。
时间一律 UTC-6。

## 1. 事实

### 1.1 配方、奖励、终止与评测器（两档共用，出处是 FlashCHORD v0.4.0 源码）

- **配方**（`configs/experiment/g1_recon_body_flash_sac.yaml`）：3.5 亿环境步、2048 个世界、逐帧回放。课程 9 段（`configs/curriculum/recon_body_flash_sac.yaml`），
  VOC（给物体的虚拟辅助力）1 → 0.75 → 0.5 → 0.25 → 0.1 → 0.05，第 7 段（2.1 亿步）起为 0，最后两段混入 25%、50% 从第 0 帧直接开始的回合。
  每段课程自带一套奖励权重（同一个锚点，与 `objective` 配置相同）。
- **奖励里关于物体的只有位置一项。** 12 项（`objectives/recon_body.py:26–38`）：终止、动作两项、关节限位、骨盆位置与朝向、全身关节位置（权重 5）、物体位置（权重 1）、
  进度、手掌位置与朝向、力闭合（权重 5），**没有物体朝向项**。物体位置项是 `exp(-|e|²/σ²)`（`:276–278`），σ = `object_position_std` = 0.2 m
  （`configs/objective/recon_body.yaml:17`）：误差 1、3、5 cm 时 0.998、0.978、0.94，在 MP-SR 的 3 cm 门槛附近几乎没有斜率。每步奖励按 frame_dt 缩放（`:306–310`），
  一次终止计 −300 × 0.02 = −6。
- **终止**（`configs/termination/recon_body.yaml`）：物体位置 0.10 m、物体朝向 1.50 rad（86°），重置后 50 步内不判；冻结期后逐步按“大于阈值”判（`lifecycle/termination.py:636–646`）。
- **训练记录里的跟踪误差**是“日志窗口里每个世界步误差的平均”（`training/flash_sac/runner.py:307–309`）。均值接近某个阈值，意味着相当比例的世界步超过它。
- **排行榜的四个指标不读配置。** MP-SR 要每个世界按帧平均的位置误差 < 3 cm 且朝向 < 30°，SP-SR 是 ≤ 0.1 m 且 ≤ 0.5 rad，都是评测器里的常数
  （`evaluation/metrics.py:21–24, 296–349`）；ADD-AUC、MPPE 同样只用常数。评测时六个终止阈值一律改成 1e6，失败的世界照样走完（`evaluation/harness.py:173–207`）；
  chord_sr 在改之前从 checkpoint 的终止配置取阈值（`:141–170`），所以改了终止阈值后 chord_sr 不可比，评测的 rollout 不受影响。
- **评测器按 checkpoint 自带的配置重建环境**（`harness.py:331–355`；课程段取 checkpoint 的 metadata，`:384–393`）。只改已有字段的取值，官方 8c778f9 评测器照样能读；
  新加奖励项要改代码，违反“评测与导出用 8c778f9”的决定（`agent-doc/decision-organizer-q1-q3-2026-10-01.md`）。**本计划只改取值。**
  `env.objective`、`env.termination` 是对顶层 `objective`、`termination` 的引用（`configs/env/rl.yaml:13, 16`），顶层覆盖会一起带过去，没有第三份副本。

### 1.2 Tier 1 的事实（只用于 Tier 1）

- 4096 世界评测（mf4090，400 万 buffer，最终 checkpoint；`results/day2/eval_<run>_s349999104.txt`）：ep6 3.3 cm / 12.7° → MP-SR 0.562；ep18 4.1 / 11.1 → 0.152；
  ep27 5.6 / 12.7 → 0.321；ep29 3.5 / 5.8 → 0.174（卡在位置）；ep20 3.8 / 35.5 → 0.016（卡在朝向）。ml40 上 ep15 4.5 / 30.4、ep17 8.9 / 42.0 也卡在朝向，
  训练时 VOC 撤掉的过程中朝向误差一路涨（`agent-doc/experiments/2026-09-30-batch1b-failure-analysis.md`，jev 10 / 10）。
- 已过关的对照：ep8 MP-SR 0.979（3.0 cm / 6.3°）。
- 同配方只换种子的 run 只有一对：ep20 实时回放、mf4090、s42 与 s43，MP-SR 0 与 0.0002、ADD-AUC 0.421 与 0.411，都在地板上。换配置差别就大（同样实时回放，
  ml40 上 1000 万 buffer 0.887）。中间段换种子的波动没有量过。

### 1.3 Tier 2 的事实（只用 Tier 2 的数据）

- 4096 世界评测（ml40，1000 万 buffer，对照 v5.4 参考，即策略的输入；`results/ml40/day2/eval_<run>_s349999104.txt`）：ep8 3.3 / 8.2 → 0.021；ep12 4.1 / 9.0 → 0.001
  （卡在位置）；ep20 4.0 / 35.7 → 0；ep24 3.7 / 30.8 → 0；ep26 2.4 / 32.3 → 0.006（卡在朝向）。已过关的对照：ep22 0.724（3.3 cm / 15.0°）。
- 训练记录（`results/ml40/t2/wandb_by_stage_trial_candidates.txt`，按课程段）：VOC 撤掉的过程中物体朝向误差 ep20 0.12 → 0.61 rad、ep24 0.09 → 0.51、ep26 0.32 → 0.58，
  ep26 在 VOC 全开时就是 0.32 rad；物体位置误差 ep12、ep24 在 VOC 全开时已是 3.5、3.8 cm，最后一段 3.6、4.1 cm，ep8 从 1.8 cm 涨到 3.2 cm。
- **参考本身的物理一致性**：v5.4 重定向后，物体静置时最低点相对最近支撑面的间隙（最低 5% 帧的中位数，`stages/retarget/check_support_alignment.py:56–65`；
  `results/batch_summary_v040_t2v54.tsv`）ep20 −22.1 mm（陷进桌面，ALIGN 不过）、ep26 −10.0、ep22 −8.5、ep8 −3.4、ep24 −2.2、ep12 −0.8。仿真里的物体陷不进去，
  ep20 静置帧对 v5.4 的位置误差有约 2 cm 的地板。
- Tier 2 没有任何同配方只换种子的 run。

### 1.4 评测器版本、算力、磁盘、GPU

- 10 条试验 episode 与 2 条对照的基线（seed 42）当时用 v0.4.0 评测器评；新 run 由评测链用 8c778f9 副本评。同一个 checkpoint 两版评测器的结果有小差
  （兼容性验证 P4，`agent-doc/experiments/2026-10-02-box6-eval-runtime.md`）。所有组一律用 8c778f9 的数，基线重评（第 7 节）。
- 一条正式训练约 2 小时（10/2 两条重训 1:57、2:00）；每条冒烟加冒烟检查与 256 世界 rollout 约 10 分钟；4096 世界评测约 5 分钟。训练链先跑完全部冒烟再跑正式，
  评测链等训练链全部结束才开始评（`stages/policy/day2_train_chain.sh:67–120`、`stages/evaluate/day2_eval_chain.sh:32–36`）。
- mf4090 可用 8.5 GB（10/4 晚），一条 run 留 1 份 state 约 0.33 GB；ml40 约 1.8 TB。
- **mf4090 上现在有别人的 GPU 进程**：`maniphys_visual_worker`（容器 `maniphys-visual-dev-worker-120`，10/4 早上起），占 2.7 GB 显存。我们在这张卡上的冒烟显存峰值约 23.85 GB
  （整卡 24.56 GB），训练链的 GPU 检查见到别的进程就停（`day2_train_chain.sh:38`）。ml40 空闲。

## 2. 变体 A（只改取值，不改代码）

| 字段 | 基线 | 变体 A | 理由 |
|---|---|---|---|
| `objective.object_position_std` | 0.2 m | 0.05 m | 误差 1 / 3 / 5 cm 时奖励 0.96 / 0.70 / 0.37，3 cm 处的斜率是原来的约 11 倍；10 cm 时 0.02，由 10 cm 的位置终止兜住 |
| `termination.object_orientation_threshold` | 1.5 rad | 0.6 rad（34°） | 奖励里没有朝向项，只能经终止施压；取略宽于 MP-SR 30° 的值，冻结期 50 步照旧；评测时终止阈值本来就改成 1e6 |

- 改的是 σ 不是权重：权重写在 9 段课程里，各段要一起改；σ 只在 `objective` 里。
- 终止逐帧判，MP-SR 看按帧平均：逐帧都 < 34° 不保证平均 < 30°，平均 < 30° 也允许个别帧 > 34°。两者方向一致，判法不同。
- **来源标注**（ADR-00002）：变体 A 的假设是看过 Tier 1 失败分析（9/30，ep15、ep17 的朝向漂移）之后提出的。对 Tier 2 的论证只用 Tier 2 的证据：1.3 的评测
  （三条卡朝向、两条卡位置）与训练记录（VOC 撤掉时朝向漂移），加上代码事实（奖励里没有朝向项、σ = 0.2 m 在 3 cm 处几乎没有斜率）；取值 3 cm、30° 是公开的指标常数。
  Tier 2 的判定记录与判定脚本的输出里不出现 Tier 1 的数。
- 只试一个变体：两处改动检验同一个假设，“配方没有要求 MP-SR 量的东西”。A 过了再按需拆开做消融；A 不过就带着结果重新分析，不在同一批数据上反复调参。

## 3. 试验设计

| 档位 | 机器（buffer） | 试验序列（基线 seed 42 已有，都是现在导出的 run） | 对照（已过关） |
|---|---|---|---|
| Tier 1 | mf4090（400 万） | ep6、ep18、ep20、ep27、ep29（`t1-ep<N>-w2048-cap4m-mf4090`） | ep8 |
| Tier 2 | ml40（1000 万） | ep8、ep12、ep20、ep24、ep26（`t2-ep<N>-w2048-cap10m-ml40`） | ep22 |

每档 16 条新 run，分两段（审查 M1：评测链要等整个训练链结束，中途检查只能放在段与段之间）：

- **A 段**（6 条）：5 条试验序列的变体 A seed 42，加对照序列的变体 A seed 42。
- **段间门**：服务器上的脚本等 A 段评测链结束，跑 `trial_verdict.py --midcheck`；结论 CONTINUE 才起 BC 段，STOP 就写下结论、不起。两种结论都有测试覆盖；Mac 离线也照常。
- **BC 段**（10 条）：5 条基线 seed 43，5 条变体 A seed 43。
- 每段有自己的期望表、冒烟队列、正式队列、训练链与评测链。一档约 6 × 2.2 + 10 × 2.2 ≈ 35 小时，加段间等待约 1 小时。

细节：

- 命名：`t<档>-ep<N>-w2048-cap<4m|10m>-r3a-<机器>`（变体 A、seed 42）、`…-r3a-s43-<机器>`、`…-s43-<机器>`（基线配方、seed 43），与已有 run 都不重名。
- 训练副本：全部用带防护的 `v040_p185_nfg`（链的环境给 `V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<机器>/fc_src/v040_p185_nfg`）。这 12 条序列都不在方盒的三条
  （ep1、ep7、ep28）里，#185 不起作用；没有事件时防护不改变训练（终止 kernel 与上游逐位相同，K1；学习器侧只替换非有限值，K3）。基线 seed 42 是 9/29–10/1 用 v0.4.0
  原副本训的，是唯一用旧副本的一组。
- 队列行照 ep7 重训的写法（`V2D_WANDB_UPLOAD_CKPT=0 V2D_MAX_RETRY=0 V2D_GPU_APPS=1`），`V2D_WANDB_TAG=r3`、`V2D_KEEP_STATES=1`；seed 43 的行末加
  `reset.seed=43 training.seed=43`；变体 A 的行末加 `objective.object_position_std=0.05 termination.object_orientation_threshold=0.6`。mf4090 的链环境照抄
  `V2D_MIN_FREE_MB=1200 V2D_PRUNE_SMOKE_STATE=1`（`arm_nfg_chains.sh:12`）。
- **配方断言**（审查 M5）：起链脚本在 `fc_config_check.sh` 之后，对每条 run 与冒烟用 `assert_cfg.py` 核 `runs/cfgcheck/<run>.yaml`：名字带 `-r3a-` 的必须是
  `objective.object_position_std=0.05`、`env.objective.object_position_std=0.05`、`termination.object_orientation_threshold=0.6`、`env.termination.object_orientation_threshold=0.6`，
  其余必须是 0.2 与 1.5。不过就不起链。期望表的格式不动（几个脚本按固定列读它）。
- **评测**：新 run 由评测链用 `fc_eval.sh`（8c778f9 副本）评最终 checkpoint；基线 seed 42 用 `fc_export.sh`（`V2D_EXPORT_WORLDS=4096 V2D_EXPORT_TRAJ=0`，8c778f9 副本）重评，
  与兼容性验证 P4 同一做法。两条路跑的是同一个评测配置（`configs/evaluation/flash_sac.yaml` 默认 explicit、4096 世界、第 0 帧、deterministic）。`trial_verdict.py`
  两种输出都认，并核来历：JSON 里的 checkpoint sha256 等于 policy 文件；评测日志里 `in-flash-chord` 记的 `/workspace` 来源是 fc_8c778f9 副本（这一版指标 JSON 里没有评测代码哈希）。

## 4. 判据（执行前登记，每档分开判）

记 MP_A(e)、MP_B(e) 为 episode e 上变体 A、基线两个种子（42、43）的 4096 世界 MP-SR 的平均，全部用 8c778f9 评测器的数；ADD-AUC、SP-SR、MPPE 同理。

| 编号 | 判据 |
|---|---|
| S1 主判据 | 5 条的平均 MP_A − 平均 MP_B ≥ 0.15 |
| S2 一致 | MP_A(e) ≥ MP_B(e) + 0.05 的 episode 至少 3 条 |
| S3 不大退 | 没有一条 MP_A(e) < MP_B(e) − 0.20，也没有一条 ADD-AUC_A(e) < ADD-AUC_B(e) − 0.05 |
| S4 不伤其他指标 | 平均 ADD-AUC_A ≥ 平均 ADD-AUC_B − 0.02；平均 SP-SR_A ≥ 平均 SP-SR_B − 0.10；平均 MPPE_A ≤ 平均 MPPE_B + 0.5 cm |
| S5 训练健康 | 变体 A 的 11 条都跑完（有 DONE、最终 policy 有限、没有 `NONFINITE_GUARD_STOP`）。变体 A 有一条因训练原因没跑完，这一档就不能判通过 |
| S6 对照不退 | 对照序列变体 A seed 42 的 MP-SR ≥ 基线 seed 42 − 0.10 |

S1–S6 都过，这一档判“变体 A 通过”，进第 5 节；任一不过判“不通过”，照实报告，不在同一批数据上换参数重试。基线 seed 43 没跑完时，这条 episode 的 B 只用 seed 42，注明。

**中途检查（只许判停，不许判过）**：A 段评完后，若 5 条 MP_A,42(e) − MP_B,42(e) 的平均 ≤ 0，并且没有一条 ≥ +0.10，这一档判“不通过（中途）”，不起 BC 段。
否则起 BC 段，不看中途数做别的决定。这是无效性停止，不抬高误判“通过”的概率。

**分辨力**（写在前面，免得事后改门槛）：中间段单条 run 的 MP-SR 标准差没量过。按 0.2 算，S1 的统计量标准差约 0.09，0.15 的门槛约 1.7 个标准差，假阳性约 5%，
真实提升正好 0.15 时检出率约 50%；按 0.3 算，假阳性约 13%。所以 S1 不过不等于变体 A 无效。基线两个种子的差只用于事后报告波动，不用来改门槛。

**同版重复噪声**：闸 G1 时把一条基线 checkpoint 用 8c778f9 评两次，量同一评测器重复评的差，写进记录（只报）。

**只报、作归因**：

- 每条 run 第 6–8 段（VOC = 0）的“终止:物体”比例与“进度”（`stages/policy/wandb_local_history.py --by-stage`）。这一档不通过时，若变体 A 两个种子这两项的平均，
  终止:物体 ≥ 基线的 2 倍且进度比基线低 0.1 以上，记为“朝向终止过严或参考做不到”，与“配方无效”分开写。
- 敏感性：变体 A 两种子均值 − 基线 seed 43 单种子（seed 42 是挑序列时用的样本，可能偏）；主判据仍按上表。
- 每条 episode 的四个指标与 chord_sr（chord_sr 与终止阈值有关，不可比）；防护事件；Tier 2 每条 episode 在 VOC 全开那一段的朝向误差（参考质量的旁证，给降噪计划用）。

## 5. 通过之后（铺开）

- **Tier 1**：其余 24 条（对照 ep8 已有变体 A）用变体 A、seed 42 重训。mf4090 试验后约剩 3 GB，不够再跑十几条：要么旧 run 的 state 归档到 HF 后删本地
  （`tools/hf_archive_run.sh`，先核 HF 上的 sha256；删之前问用户），要么多分给 ml40（1000 万 buffer，与试验的 400 万不同，靠下面“每条交哪一个”兜底）。
- **Tier 2**：取决于降噪计划。新的 Tier 2 参考若被采用，铺开时直接在新参考上训，免得 30 条训两遍；否则在 v5.4 上训。全在 ml40 上约 66 小时。
- **每条 episode 交哪一个**，要用户定（与 10/2 “按规则、不按分数挑”的约定不同）：甲，全部换成变体 A；乙，每条在已评完的 run 之间按 4096 世界 MP-SR 取高者，
  相同取 ADD-AUC 高者。我们建议乙：4096 个世界的 MP-SR 抽样误差约 ±0.008，按它挑带来的乐观偏差很小；Tier 2 按对照 v5.4 的评测挑，这与排行榜对照的干净真值不是一回事。
  两种挑法都要落成 `export_map.py` 的规则与测试（它现在的正则不认 `-r3a-`、`-s43-`，并断言每条 episode 恰好一条 run）。
- 之后照提交流程：导出、拉回、打包、上传器只跑 `--dry-run`；真提交等用户确认。

## 6. 风险

- 变体 A 最可能出的问题：VOC 撤掉后朝向终止大面积触发。Tier 2 的 ep20、ep24、ep26 在 VOC 为 0 的几段，训练朝向误差均值已在 0.5–0.6 rad（ep26 在 VOC 全开时就是 0.32），
  0.6 rad 的终止会频繁触发，冒烟（400 万步、第 0 段）看不见。只报不止损：中途检查把浪费限在 A 段；第 4 节的归因项把这种结局与“配方无效”分开。
- 收紧位置核可能让训练前期更难（误差大时这一项几乎为 0）。
- Tier 2 的判据对照 v5.4：跟得更紧不等于排行榜更高。ep20 的参考静置时陷进桌面 22 mm，位置误差有地板；v5.4 自身残留的朝向误差也可能让朝向终止在物理上做不到的地方触发。
- 两个种子量不准小的提升（见第 4 节分辨力）。试验序列是按基线 seed 42 挑的“差一点”，所以基线补 seed 43，另报敏感性。
- 评测兼容：只改取值，但正式开跑前实测 8c778f9 评测器能读变体 A 的 checkpoint（闸 G1）。
- mf4090：别人的进程不停，Tier 1 试验起不来（第 8 节）。磁盘：Tier 1 试验 16 条约 5.3 GB，现有 8.5 GB 够。
- 档位隔离：两档的试验、判定、记录分开；Tier 2 的判定脚本开头调 `forbid_tier1()`。

## 7. 顺序

1. 独立审查第 1 版（已做），处理意见后登记本版。
2. 代码，各带测试：`fc_config_check.sh` 的放行规则在 `reset.*` 之外加 `objective.*`、`termination.*`（同样放行 `env.` 下的副本）；`stages/evaluate/trial_verdict.py`
   （按第 4 节算 S1–S6、中途检查、归因与敏感性，两种评测输出都认、核来历，用造的数据覆盖过与不过的各分支；Tier 2 调 `forbid_tier1()`）；起链脚本按批次与段参数化，
   含配方断言；段间门脚本（等 A 段评测链结束 → `--midcheck` → 起或不起 BC 段）。
3. 闸 G1（每台一次）：变体 A 的配置跑一条 400 万步的冒烟（Tier 1 用 ep6、Tier 2 用 ep8），过 `fc_config_check.sh` 与配方断言；用 fc_8c778f9 副本按 4096 世界评这条冒烟的 policy，
   要求评测成功、`non_finite_worlds` 为空。不过就停，查原因。接着用 `fc_export.sh` 重评本档 6 条基线 seed 42（每条约 5 分钟），其中一条评两次量重复噪声。
4. 写两台的期望表与队列，`fc_config_check.sh`、配方断言、`precheck_expect.sh` 都过之后起 A 段与段间门。
5. 全部评完后用 `trial_verdict.py` 逐项算，写执行记录、过 jev、向用户回报。

## 8. 要用户定的

1. **mf4090 上别人的进程**：Tier 1 试验要这张卡空出来。可以请同事在试验期间（约 36 小时）停掉那个服务；或者 Tier 1 试验等它停；或者挪到 ml40、排在 Tier 2 之后
   （多等约 36 小时，而且换了机器，基线也要在 ml40 上补训，这一条要另写计划）。Tier 2 试验只用 ml40，不受影响。
2. 通过之后每条 episode 交哪一个（第 5 节甲、乙）。
3. 旧 state 归档后删本地（铺开前需要）。
