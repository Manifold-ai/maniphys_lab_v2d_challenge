# 计划：ep7 两份最后有限的 checkpoint 的评测（A）与训练的非有限防护（B）

第 4 版，2026-10-02（第 1 版只有 A 部分，9b6b015；第 2 版加 B 部分，3ce4ea5；第 3 版按审查改 A 部分，5492354；第 4 版按审查改 B 部分）。用户 10/2 的决定（原话）：“先评，同时写防护的计划”。事实依据：`agent-doc/experiments/2026-10-02-ep7-divergence-analysis.md`（jev 19 条核实）。
时间一律 UTC-6。A 部分先成文、先审、先跑；B 部分在本文件第 2 版里补全，另行审查，审过之前不动训练代码、不重训。

## A. 评两份最后有限的 checkpoint

第 3 版：按独立审查修改（A.6）。

### A.1 要回答的问题

- Q1：t1-ep7 的 130,004,992 步、t2-ep7 的 140,005,376 步这两份 policy，在评测条件（VOC 为 0、确定性动作、4096 世界）下是什么分数，够不够候选条件。
  用不用它们先凑齐 30 条，由用户看了结果再定；这一步不导出、不打包、不上传。
- Q2：评测条件下会不会出现崩掉的世界。出现的话崩在参考的哪一帧附近。

### A.2 做法

| 机器 | run | 步数 | 评测运行时 | 取证运行时 |
|---|---|---|---|---|
| ml40 | `t2-ep7-w2048-cap10m-p185-ml40` | 140005376 | `/lab_data/rxzhou/v2d/fc_src/fc_8c778f9` | `/lab_data/rxzhou/v2d/fc_src/v040_p185` |
| mf4090 | `t1-ep7-w2048-cap4m-p185-mf4090` | 130004992 | `~/v2d/fc_src/fc_8c778f9` | `~/v2d/fc_src/v040_p185` |

两台的 GPU 都已空闲（mf4090 的诊断链 14:51 结束），同时起。每台由 `stages/evaluate/arm_ep7_eval.sh <机器>` 在 tmux 里起一条
`stages/evaluate/ep7_ckpt_eval.sh <run> <步数> 896 ep7_eval_<机器>`（都是新文件，不替换服务器上任何现有文件）：

1. 先查，任何一条不满足就拒绝：日志不存在；policy 文件在；这一步的评测 JSON 与取证 npz 都还不存在（不沿用旧结果、不覆盖旧证据）；
   两份源码副本各自过 `fc_src_check.py`；`ckpt_nonfinite.py` 给出这一步“非有限 0”（规矩一）。本机还有别的长链在跑也不起。
2. 等 GPU 空出来（最多 7200 秒），用 8c778f9 副本跑 `stages/policy/fc_eval.sh`（4096 世界），与方盒评测链是同一条命令、同一运行时，
   结果记在 `results/ep7/eval_<run>_s<步数>.txt`。fc_eval 报 GPU 被占（退出码 6）就等 GPU 空了重跑。
3. 评测完不论成败，把 fc_eval 自己的日志里的要点行摘到 `results/ep7/evallog_…txt`：挂的是哪份源码、是否走满 896 帧、评测器报了几个非有限世界、
   有没有报 must disable task failure termination。评测的结局分三种：成功；失败（终止报错）；失败（其他）。
4. 评测成功时由脚本逐项核候选条件 A-2，记在 `results/ep7/a2_…txt`。
5. 取证 rollout 每次都跑（`stages/evaluate/blowup_rollout.py`，4096 世界，挂 v0.4.0 + #185 副本，与 `diag_rollout.py --palms` 用同一个手掌记录器）：
   把物体与两只手掌逐步的位置原样存成 npz（不清零），打印崩掉的世界数与第一次出问题的帧的分布。评分阶段报终止不算它失败。
6. 日志最后一行 `EP7_EVAL_DONE（评测 …；评测器记的非有限世界 …；A-2 …；取证 …）`。

之后在 Mac 上拉回 `results/`，用 `stages/evaluate/batch_verdict.py stages/policy/queues/<机器>_ep7ckpt.expect.tsv <results/ep7 目录> --steps <步数> --bar-root <不动基线所在目录>`
按批量判据出判定（期望表各只有 ep7 一行，取自方盒期望表；`--bar-root` 是这次给 batch_verdict.py 加的可选参数，不给时行为不变，已用两份旧判定逐字核过）。
评测记在 `results/ep7/` 而不是 `results/day2/`，免得进入此前按 `results/day2/` 统计的评测结局计数。

为什么不直接用 `diag_rollout.py --palms`：它存盘前把非有限世界的手掌清零，评测器也把这些世界的物体位姿清零，崩之前的轨迹看不到；
评分阶段若因有世界被判终止而报错，它不存盘。这次不改它。

### A.3 判据（跑之前登记）

- **A-1 评测的结局**：日志最后一行是 `EP7_EVAL_DONE`。“成功”与“失败（终止报错）”都是结果：后者说明评测条件下有世界崩到被判终止，是 Q2 的答案之一，这份 policy 也就过不了 A-2。
  “失败（其他）”（容器、显存、磁盘等）等于没评成，查明原因后重跑，不当作结果。
- **A-2 候选条件**（与导出链对候选的要求相同，由脚本逐项核）：评测 JSON 里 `world_count` 为 4096、`non_finite_worlds` 是空列表、`step_count` 为 896、
  `checkpoint_sha256` 等于这份 policy 文件的 sha256。四项都满足才说“这份 policy 可以作临时候选”。满足也不自动使用，等用户定。
- **A-2 不满足之后**：这一份就不作候选。要不要试更早的 checkpoint 由用户定；要试的话只按规矩二的次序（步数从大到小，逐份评），不按分数挑。
- **A-3 质量只报数**：chord_sr、MP-SR、SP-SR、ADD-AUC 与不动基线之差、MPPE，以及 `batch_verdict.py` 的判定，都取自 8c778f9 副本的那次评测。它们不改变 A-2 的结论。
  取证 rollout 顺带写出的评测 JSON 不用于 A-2、A-3。t2-ep7 的分数对照的是 Tier 2 v5.4 参考，不和 Tier 1 比，也不拿来调方法。
- **A-4 触发**：
  - “崩掉的世界”的定义：物体或任一只手掌的位置出现非有限值，或绝对值超过 100 m（数值很大但有限的状态同样会毁掉训练）。评测器自己记的“非有限世界”只看物体位姿，范围更窄，两个数分开报。
  - 取证与评测是两次独立的 rollout（不同的源码副本，评测本身也不逐位可复现），两边的世界号不对应，只比个数与帧的分布。
  - 崩掉的世界数大于 0：报世界数、第一次出问题的帧的最早、中位、最晚与最集中的几帧，t1、t2 分开报。只描述，不据此下“触发就是薄桌面”的结论；
    要下这个结论，另需对照（例如把桌面加厚后同一份 policy 的同样 rollout），那是 B 之后的事。t1-ep7 的帧不拿去设 Tier 2 的任何东西。
  - 两份都没有崩掉的世界：结论只能是“这两份 policy 在 VOC 为 0 的 4096 × 896 步里没有出现”，不能推出训练里不会再出现。触发仍未知，留给 B 的事件记录。
- 结论的范围：两份 policy 分别只训到 VOC 0.25、刚进 0.1，评测在 VOC 为 0 下跑，与训练里出事时的条件不同。

### A.4 风险与守卫

- 与别的链抢 GPU：起链脚本见到本机有长链标记就不起；链每次用 GPU 之前都等它空出来。14:51 之后两台都没有在跑的链。
- 改动在跑的链要用的文件：不改。新文件是 `stages/evaluate/{ep7_ckpt_eval.sh,arm_ep7_eval.sh,blowup_rollout.py}`；`diag_rollout.py`、`diag_palms.py`、`fc_eval.sh` 原样。
- 磁盘：评测 JSON 很小；取证 npz 未压缩约 220 MB（896 帧 × 4096 世界：物体 44 MB、手掌 88 MB、评测器的逐步误差 88 MB）。mf4090 可用 5640 MB（14:30）。
- 16:47 的收尾任务（拉导出、打包、只跑 `--dry-run`）不受影响：它只读两台的导出表，两档都缺 ep7，按决策表列缺项。
- 不往 Kaggle 上传任何东西。

### A.5 测试

- `stages/evaluate/test_ep7_ckpt_eval.py`（8 组，Mac 上全过）：候选条件四项逐项判、缺键记未知；评测报终止与别的失败分开记；取证输出里带 Traceback 仍记完成；
  fc_eval 退出码 6 时等 GPU 重跑；六种拒绝（含两份副本填反）；评测前后 GPU 被占的两种结局；试跑不写日志。
- `stages/evaluate/test_blowup_rollout.py`（5 组，要 numpy，Mac 上用 uv 跑过）：假的评测脚本像 hydra 那样打印 Traceback 再 `sys.exit(1)` 时仍然存盘、原始 NaN 不清零；
  别的异常不存盘；输出已存在就拒绝；`first_bad_frame` 的单元检查。
- 真实路径的自测（起链前在 ml40 上跑一次，GPU 约 2 分钟）：用 9/29 那份已知会崩的 policy `smoke-t1-ep7-w2048-cap10m-ml40/policy_4096000`
  （默认的 v0.4.0 几何下 256 个世界里 172 个非有限，随后评分报终止，`results/ml40/batch1/ep7_smoke_diag_excerpt.txt`）跑 256 个世界的取证，
  期望：`BLOWUP_ROLLOUT_OK`、崩掉的世界数大于 0、`score_error` 非空。这一步只验证代码路径，数字不用于任何结论。那份 policy 若已不在，记一句，改靠上面两组测试。

### A.6 审查记录

独立审查由 Opus 5.5 做（主会话是 Fable 5.1，审查换模型），结论 GO WITH FIXES；审的是第 1 版（9b6b015）。逐条处理：

| 意见 | 处理 |
|---|---|
| BLOCKER：评分报终止时 hydra 把 Traceback 打进输出，`scripts/dev/record` 见到 Traceback 就判失败，最要紧的那条路径会被记成“取证 失败” | 取证那条 record 加 `V2D_RECORD_TRACEBACK_OK=1`；测试加一组“输出带 Traceback、退出码 0 → 记完成” |
| MAJOR：评测失败不分原因，GPU 被占（退出码 6）也当成结果；最直接的证据（评测日志里的非有限世界数与报错）只留在服务器上 | 退出码 6 等 GPU 重跑；评测日志的要点行经 record 摘进 `results/ep7/`；结局分三种，A-1 写明哪些算结果 |
| MAJOR：取证脚本的容错路径没跑过，16 世界试跑用的是有限的 policy，覆盖不到 | 加 `test_blowup_rollout.py`；另用已知会崩的 policy 做一次真实路径的自测。原来的 16 世界试跑去掉 |
| A-2 判不了：链只读了一个键，sha256 没人算 | 链里逐项核四项并落盘 |
| 缺 `non_finite_worlds` 键时默认放行 | 缺键或不是列表记“未知”，A-2 不满足 |
| 会沿用已有的评测 JSON | 已存在就拒绝 |
| 源码副本只查了 SOURCE_V2D.txt，两个变量填反也能过 | 两份副本各自过 `fc_src_check.py` |
| `V2D_EVAL_WORLDS`、`V2D_ALLOW_SHARED_GPU` 会漏进 fc_eval | 开头 unset |
| A-4 口径：崩掉的定义、世界号不对应、评测器只看物体、t1 与 t2 分开 | 写进 A-4；取证改成每次都跑，不再以评测结果为条件 |
| 等别的链没有上限 | 去掉“等别的链”这个功能：两台都空了，起链脚本见到长链标记就不起 |
| 取证前等 GPU 超时会把整条链记成失败，与事实不符 | 改记“取证 没跑（GPU 被占）”，结束行仍是 `EP7_EVAL_DONE` |
| 没登记 A-2 不满足之后怎么办 | 加一条：只按规矩二的次序，不按分数 |
| 来历不全 | 日志开头记三个脚本的 md5；npz 里存上游四个文件的 md5 |
| 小项：取证脚本先删旧输出；评测记录进了 `results/day2/` 的统计；`diag_palms` 导入太早；报错文字不准 | 已存在就拒绝；评测记到 `results/ep7/`，`batch_verdict.py` 加 `--bar-root`；改到环境建好之后导入；改文字，并改为要求扫描输出里出现“非有限 0”那一行 |

## B. 训练的非有限防护与 ep7 两档重训

第 5 版（10/2 21:00）：第 4 版按 Opus 5.5 的独立审查修改（GO WITH FIXES，6 条 MAJOR，对照见 B.8）；第 5 版再按 Fable 5.1 对第 4 版的审查修改
（GO WITH FIXES，没有 BLOCKER，2 条 MAJOR、16 条 MINOR，对照见 B.9）。两份审查的摘要都在 `agent-doc/review-ep7-guards-plan-b-2026-10-02.md`。两份审查都已处理；B.4 的闸都过之前不重训。

### B.1 事实（读仿真器与训练源码；A 的取证给了一处实测）

训练镜像里是 newton 1.2.0、mujoco_warp 3.8.1、warp 1.14.0（`results/ep7/sim_nan_facts.txt`）。

- **一个世界变成 NaN 之后，环境的重置多半救不回来（读代码，T1 实测）。** mujoco_warp 每步求解约束时直接拿上一步的加速度当起点（`solver.py:3352–3353`），
  每个子步结束再把这一步的加速度存回去（`forward.py:325`），两个文件里都没有有限性检查。Newton 的 `SolverMuJoCo.step` 每个子步把 Newton 的位置、速度拷进 mjw_data，
  另写 ctrl、qfrc_applied、xfrc_applied（都是整行赋值，不带 NaN 跨步），整个文件不碰 warmstart。环境重置只重写位置与速度（`envs/base.py:262–270`），
  所以 NaN 的 warmstart 留在那个世界里。审查逐项核过：跨步保留又不被覆盖的只有 qacc_warmstart；act 也算，前提是 G1 的 na 大于 0（未核实，T2 顺手记下）。
- **终止判定判不出 NaN 的世界，只会碰巧判出。** Warp 的浮点 `min / max / clamp` 用 fmin / fmax（一个参数是 NaN 时返回另一个），四元数 `normalize` 在长度不大于 kEps 时返回单位四元数。
  于是终止判定里：骨盆位置误差是 NaN，“大于阈值”不成立；手掌、物体的位置误差经 `wp.max(0, NaN)` 变成 0；骨盆、手掌朝向误差变成“单位四元数到参考朝向的夹角”。
  物体朝向没有先 normalize，NaN 经 clamp 得 0，夹角是 π，大于 1.5，所以过了冻结期（重置后 50 步）NaN 的世界会以 object 原因被判终止、重置，然后又是 NaN，循环下去。
  **实测：** A 的取证里世界 3680 在第 473 帧整个变成 NaN，这一帧记下的骨盆位置误差是 nan，手掌、物体位置误差是 0，骨盆朝向误差是有限的 0.26 rad
  （`results/ml40/ep7/blowup_inspect_t2-ep7_s140005376.txt`，jev 0.99）。
- **奖励归一化器与 BatchNorm 不设防**（分析记录第 2 节）：一个 NaN 奖励就让归一化器永久失效，带非有限观测的样本让 BatchNorm 统计量永久变 NaN。
- **回放的写法**（审查核对）：下一步写进回放的 `observation`、`critic_context` 是上一步的 `post_reset_observation`、`post_reset_critic_context`（`learner.py:1069–1081, 1127–1131`）；
  只有观测按存储精度（G1 是 fp16）存；n-step 是 7，以坏那一步结尾的窗口最多 7 个会被提交；回放与 TD 目标用乘法掩码，NaN × 0 仍是 NaN（`replay.py:278–312`、`update.py:129–133`）。
- **奖励的第 0 项是终止项**，权重 −300，值是 `float(terminated)`（`objectives/recon_body.py:27, 47, 234`）。普通失败那一步的奖励约 −6。
- **G1 配方每采集一步更新 4 次**（`g1_recon_body_flash_sac.yaml:53`），批 2048；回放满 409,600 条才开始更新，2048 个世界要 200 步。

### B.2 目标与不做的事

目标：某个世界的仿真状态变成非有限（或大到存不进 fp16）时，训练照常继续。具体四条：
1. 环境当步把这个世界判终止、重置，重置后恢复有限；
2. 这一步与它相关的数据不以非有限的形式进入奖励归一化器、回放缓冲、BatchNorm 统计量与日志；坏世界那一步在回放里是一条普通失败样本（终止项为 1）；
3. 每次事件都留下记录：哪一步、哪个世界、当时的参考相位、是环境判出的还是只有学习器判出的；
4. 没有事件时，训练与原来逐位相同（由组件级测试证明，B.4 的 K1–K3）。

不做：不找物理触发的根因（留给事件记录）；不改奖励、课程、网络与超参；不改评测与导出（仍用 8c778f9 副本，`eval_code_sha256` 不变；网络结构与观测不变，checkpoint 照常可用）。

### B.3 设计

补丁 `third_party/patches/flash_chord-v0.4.0-nonfinite-guard.patch`，打在“v0.4.0 + #185”之上，生成新的训练源码副本 `fc_src/v040_p185_nfg`（两台各一份）：
`stages/policy/make_patched_fc_src.sh` 加一个可选的第二个补丁参数；给新副本出一份 sha256 清单 `third_party/patches/flash_chord-p185-nfg.sha256`，开训前用 `fc_src_check.py` 核。原有两份副本不动。

**环境侧（`lifecycle/termination.py`、`envs/base.py`）**
- `evaluate_recon_body_termination`：遍历本世界的全部刚体（kernel 已有 `bodies_per_world`），平移用 `wp.isfinite(vec3)`、旋转用 `wp.isfinite(quat)` 判，
  任一分量非有限、或平移的绝对值超过 1e3 m，就把这个世界记为坏：`pelvis_failed` 置 1（不受冻结期屏蔽，于是 `terminated`、原因位、重置掩码都跟着成立），
  写出的骨盆位置误差记 −1（哨兵值，正常时误差不会是负数），其余误差记 0。kernel 的签名不变，不用比较或 `max` 来判 NaN。
- `BaseEnv.reset`：在 `reset_worlds` 之后加一个 kernel，对重置掩码里的世界，把 `solver.mjw_data.qacc_warmstart` 里**非有限的行**清零（有限的行一位不动）；
  `act` 若存在（na > 0）同样处理。用 `getattr(self.solver, "mjw_data", None)` 取，取不到就跳过；断言它的世界数等于 `world_count`。清零发生在最后一个子步把 qacc 存回 warmstart 之后、
  下一步第一次求解之前（审查核对过顺序），也在录下的图里。
- 很大但有限的 warmstart 不清：下一步多半变成 NaN，再被判坏、再清一次，一次真实事件可能记两次。

**学习器侧（`training/flash_sac/runner.py` 加一个单独 jit 的前置函数，`learner.py` 不改）**
- `sanitize_transition(transition, observation, critic_context)` 在 `consume_transition` 之前调用，输入 `observation`、`critic_context` 是学习器当前的观测与上下文（这一步之前的），只读。
- 坏世界的判据：奖励分项、`next_observation`、`next_critic_context`、`post_reset_observation`、`post_reset_critic_context`、`action` 任一有非有限值；
  或者两种观测转成回放的存储精度（读 `config.replay.observation_storage_dtype`）之后非有限。上下文与其余量按 fp32 判。
- 对坏世界（全部用 `jnp.where`，条件全假时原样返回每一位）：
  - 奖励分项写成“终止项 1，其余 0”，`terminated` 置真；
  - 四个观测与上下文数组**各按自己的判据换**（第 5 版，Fable MAJOR A）：`next_observation`、`post_reset_observation` 自身非有限或存不进存储精度时换成这一步之前的观测，
    `next_critic_context`、`post_reset_critic_context` 自身非有限时换成这一步之前的上下文。环境判坏的世界在 `_rl_step` 里已经重置，它的 `post_reset_*` 是新回合的第一帧观测（有限），
    原样留下；只有学习器判坏、环境没重置的世界，换上的 `post_reset_*` 与仿真脱节一步，它的 `terminated` 也让学习器多记一个完成回合（环境的 `episode_step` 照旧）；
  - `action` 非有限时置 0；
  - `termination_diagnostics` 的原因位里骨盆记 1、别的原因不动，误差列一律 `where(isfinite, x, 0)`（每个被判终止的世界至少带一个原因位，`runner.py:377–381` 的一致性检查才过）；
    环境判坏的世界，哨兵 −1 计数之后清成 0，不进 `tracking_error/pelvis_position_m_*`。
  - 另对所有世界的 `termination_diagnostics`、`episode_reference_progress` 做 `where(isfinite, x, 0)`。
- 实现约束（第 5 版）：不在宿主端按“有没有坏世界”分支；一律 `jnp.where`，输出是新缓冲（不会把 `learner.observation` 的缓冲原样当 transition 的叶子交给会 donate learner 的 `consume_transition`）；
  `terminated` 保持 int32（AOT 编译的执行体不重追踪，dtype 不符直接报错）；终止项按 `objective_term_names` 里的名字找，找不到就写全 0。
- `consume_transition` 编译出来的东西与原来完全一样；没有事件时前置函数原样返回，训练逐位不变（K3 证明）。
- 计数放在 `LearnerState` 之外（一个很小的设备数组，跟着前置函数走），日志窗口结束时读一次：
  - `guard/env_flagged_world_steps`：环境判坏的世界步数（原因位里骨盆为 1 且骨盆位置误差是哨兵值 −1）；
  - `guard/learner_only_world_steps`：只有学习器判出来的世界步数；
  - `guard/event_phase_min`、`guard/event_phase_max`：这些世界当时的参考相位（从终止时的评论家上下文 `next_critic_context` 按名字取 `normalized_reference_phase`，
    它由整数的 timestep 算，NaN 世界也有限；万一非有限退回这一步之前的上下文；没有这个名字记 −1；窗口里没事件时也记 −1，保证有限）；
  - 每个窗口有事件时，宿主机往训练日志打一行，以 `NONFINITE_GUARD_EVENT` 开头、后面是键值对：环境步数、两种计数、相位范围、第一个坏世界的编号、最长连续步数。
  - 计数不进 checkpoint：续训后从 0 起（正式 run `V2D_MAX_RETRY=0`，不自动续）。
- **停止条件（事先登记）**：`learner_only_world_steps` 累计超过 100，或同一个世界连续 3 步被判坏（说明重置没救回来），runner 先打一行 `NONFINITE_GUARD_STOP`（键值对加理由），
  再抛异常停训，链记失败；不自动重试。链里与别的失败混在一起（`fc_run.sh` 记成重试用尽），所以结局一律按日志里有没有这一行判。

### B.4 重训之前要过的闸（事先登记）

| 闸 | 在哪跑 | 做什么 | 通过的判据 |
|---|---|---|---|
| T1 复现 | ml40 GPU，未打防护的副本 | 照训练的做法建 ep7 的环境（Tier 2 参考，64 个世界，`capture_step` 之后只走录好的图，不训练，动作给 0），跑 100 步后把世界 7 的关节速度全写成 NaN（经 `wp.launch` 写 `state_0.joint_qd`，与仿真同一个流），再跑 120 步，逐步记下每个世界是否有限、是否被判终止、原因是什么。预期（第 5 版）：注入时已过冻结期的话，世界 7 当步就以 object 或 palm 原因终止，之后每 51 步一次 | 世界 7 第一次被重置之后的下一步仍然非有限。若它恢复了，说明 B.1 第 1 条读错了：去掉 warmstart 那一处改动，其余照做，并记下来 |
| T1b 机理 | 同上 | 只把一个健康世界的 `qacc_warmstart` 写成 NaN（不动它的位置、速度） | 下一步它整个变成 NaN（证明 warmstart 一处就足以让世界变 NaN） |
| T2 环境侧防护 | ml40 GPU，打了防护的副本 | 同 T1 的建法，四种注入各跑一次（第 5 版：位姿类注入写 `joint_q`，不写 `body_q`）：(a) 世界 7 的关节速度全写 NaN；(b) 世界 7 物体自由关节的平移写 1e6（有限，但超出 fp16）；(c) 世界 7 物体自由关节的四元数写 NaN；(d) 同一步坏 3 个世界（关节速度 NaN）：世界 3 在第 90 步后用 `RLEnv.reset(reset_frame=…, reset_mask=…)` 显式重置到第 0 帧（注入时在冻结期），世界 5 在第 96 步后显式重置到倒数第 5 帧（注入后的第一步正好是截断步），世界 7 照常 | 每个被注入的世界在注入后的第一步 done 为 1，9 列诊断恰好是（骨盆 1、手掌 0、物体 0、骨盆位置误差 −1、其余 0），这一步之后它的 `qacc_warmstart`（与 `act`，若有）有限；注入后 120 步里它的刚体位姿、关节量、观测、评论家上下文全程有限，第一步之后的终止观测也有限；其余世界 220 步全程有限；(d) 另要求世界 5 那一步 truncation 为 1、世界 3 注入时 episode_step 小于 50 |
| T2n 对照（第 4 版叫 T2c） | 同上，但在探针进程里把 `envs.base._solver_rows_to_clear` 换成返回空（只在这个进程里，不是训练的开关） | 注入 (a) | 这个世界被判终止、重置之后的下一步仍然非有限（与 T1 的结论一起，说明清 warmstart 是必要的） |
| K1 终止 kernel 不变 | ml40 GPU，在 T2 (a) 的进程里 | 注入之前的 100 步，每步把 `body_q`、`timestep`、`episode_step` 与物体参考位姿（`object_ref_pos_w / quat_w`）拷一份，上游 v0.4.0（按文件从 `/repo/third_party/video_to_data` 加载）与打了防护的两版终止 kernel 各算一次；另报评估次数、冻结期内的次数、判终止的次数 | 12 个输出数组逐位相同 |
| K2 warmstart kernel 不变 | 容器 CPU | 随机的有限行与掺了 NaN、inf 的行 | 有限的行逐位不变，非有限的行变成 0，不在重置掩码里的世界不动 |
| K3 学习器前置函数 | 容器 CPU（JAX） | 干净的 transition；一个世界的分项与观测是 NaN、inf、1e5（fp16 溢出）；环境没判终止、只有重置后观测含 1e5、上下文含 NaN | 干净输入原样返回（逐位）；坏的输入：输出全部有限，坏世界的分项是“终止 1、其余 0”，原因位与 terminated 一致；把输出连续喂给真的 `consume_transition` 8 步（多于 n-step），回放的 storage 与 pending、奖励归一化器、学习器的观测全部有限 |
| T4 上游测试 | 先在 ml40 GPU 上跑未打防护的副本作基准，再跑打了防护的 | `tests/training/flash_sac`、`tests/lifecycle/test_termination.py`、`tests/envs/test_rl.py`、`tests/envs/test_base.py`（后三个带 gpu 标记，CPU 上会整批跳过，所以放 GPU 上；带 `sequence_data` 标记的在容器里没有数据时两边同样跳过，T4 对环境侧的信息量因此有限，环境侧靠 T2、K1） | 通过、失败、跳过的测试与基准相同 |
| T5 冒烟 | ml40 GPU，打了防护的副本 | ep7 冒烟 400 万步、种子 42，run 名取重训链的冒烟名（`smoke-t2-ep7-w2048-cap10m-p185g-ml40`），经 `fc_run.sh` 按冒烟队列行跑，链见 DONE 就跳过这一步 | 跑完；W&B 各行全部有限；日志里没有 `NONFINITE_GUARD_EVENT` 与 `NONFINITE_GUARD_STOP`；稳态行吞吐的中位数不低于同配置方盒冒烟 `smoke-t2-ep7-w2048-cap10m-p185-ml40`（ml40，10/2 10:22 UTC-6，只差防护补丁）的 95%；稳态行指环境步数不小于 1,024,000 的 W&B 行（回放 409,600 步满、开始更新之后再过约 300 次采集），取 `throughput/env_steps_per_second`（第 5 版：单机两次冒烟常差 2–3%，97% 偏紧；第 4 版写的“9/30 同配置冒烟”不对，同配置的是这一条，T5 跑之前改正） |
| T6 端到端注入 | ml40 GPU，打了防护的副本 | `stages/policy/nfg_train_inject.py` 包一层运行未改动的训练入口（参数同 `fc_train.sh`，W&B offline）：2048 个世界、1300 次采集，第 300 次采集之后按 T2 的 (a) 注入世界 7，再跑 1000 次 | 训练跑完设定的步数；注入之后 W&B 各行全部有限；`NONFINITE_GUARD_EVENT` 行里注入那个窗口的 `env_flagged` 是 1 或 2（见 B.3 很大但有限的 warmstart 那一条），其余窗口没有事件行；最后的 policy 没有非有限参数；没有 `NONFINITE_GUARD_STOP` |

任何一道不过就停，照实记录，不绕过。T1 若显示重置能救回来，按表里写的处理，其余各闸照跑。
脚本（第 5 版）：T1、T1b、T2、T2n、K1 是 `stages/policy/nfg_env_probe.py`（一个闸一个进程，存 `runs/nfg_probe/<闸>.npz`），T6 是 `stages/policy/nfg_train_inject.py`，
T4、探针各闸与 T6 由 `stages/policy/nfg_gpu_gates.sh` 在 ml40 上依次脱机跑，每一步记到 `results/ep7/nfg_<步>_ml40.txt`；K2、K3 是 `nfg_test_kernels.py`、`nfg_test_learner.py`（容器 CPU）。

### B.5 重训与判据

两台并行，各约 2.2 小时：mf4090 训 `t1-ep7-w2048-cap4m-p185g-mf4090`，ml40 训 `t2-ep7-w2048-cap10m-p185g-ml40`。配置与发散的那两条相同（种子 42、buffer、课程都不变），
只换训练源码副本。第 5 版（Fable MAJOR B）：副本的挂法写在**链的启动命令**里（`V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<机器>/fc_src/v040_p185_nfg`，链自己读这两个变量），
不写进队列行；每台新写一套期望表（含冒烟行）、冒烟队列、正式队列，队列行写 `V2D_WANDB_TAG=<新 tag> V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0 V2D_KEEP_STATES=4 <run> <parquet> 2048 <步数> [capacity]`；
开链前先用 `fc_config_check.sh` 生成两条 run 与两条冒烟的 `runs/cfgcheck/<run>.yaml`，再用 `precheck_expect.sh` 预跑正向核对。冒烟、看守照常（ml40 的冒烟就是 T5，跑过了链会跳过）。

- **R-1 跑完**：349,999,104 步、有 DONE、最终 policy 没有非有限参数、W&B 历史里没有 nan、停止条件没有触发。
- **R-2 事件记录**：报每条 run 的 `env_flagged`、`learner_only` 累计数，各次事件的环境步数、世界号与参考相位（宿主机日志的事件行）。全程 0 次就照实写“没有再出现”，
  不据此说防护验证过了（那靠 T2、K3、T6）。
- **R-3 质量只报数**：按批量判据，评测用 8c778f9 副本、4096 世界。不和发散前的 checkpoint 比高低来挑。
- **结局**：
  - 跑完 → 评测、导出、两档打包、上传器只跑 `--dry-run`。导出用哪条 run 由 `stages/evaluate/export_map.py` 按规则定：改规则（同一条 episode 有名字带 `-p185g-` 的 run 时用它；
    `tier1()` 的正则不认新名，靠期望表路径匹配）与 `test_export_map.py`；`exports/*.tsv` 已存在时它拒绝覆盖，先挪走再重新生成；在提交流程的计划里写明原因。
  - 跑完但评测里出现非有限世界（候选条件不满足）→ 按规矩二往前退（同一条 run 里步数从大到小），不按分数挑。
  - 停止条件触发（日志里有 `NONFINITE_GUARD_STOP`）或再发散 → 停，不换种子重试，带着事件记录重新分析。
- 改用打了补丁的训练副本是新的决定：在 `docs/adr/00003-stage-handoff-and-runtime.md` 的变更记录里补一行（#185 与这次的防护补丁），按 CLAUDE.md 的顺序在动手前完成。

### B.6 风险

- 没有事件时训练变了：K1–K3 证明三处改动在没有事件时逐位不变；T5 只看跑得完、全程有限、吞吐。GPU 上本来就不能逐位复现两次训练，所以不拿冒烟的曲线比高低。
- 清 warmstart 不够、还有别的状态带着 NaN：T2 兜这一条（重置后状态与观测都要有限），不过就按 T2 记下的现象补。
- 观测里的历史量（`processed_target_history`）若没随重置清掉，坏世界会每一步都产出 NaN 观测：T2 查观测、停止条件兜底。
- 换阶段那一步恰好有坏世界：替换用的上下文是换阶段之前的，只影响那一条样本。
- 补丁针对 v0.4.0；上游以后改了这三个文件要重做。补丁头注明上游版本与用途。
- 档位隔离：两档用同一个补丁；防护不读任何轨迹数据。Tier 2 的重训只读 Tier 2 的参考。
- 磁盘：mf4090 20:00 可用约 5040 MB，多留 3 份 state 约 480 MB，够。
- 重训每条约 2.2 小时 GPU；两台此刻都空闲，没有排队的任务。

### B.7 顺序

1. Fable 5.1 审第 4 版，处理意见，登记（第 5 版，B.9）。ADR-00003 改正文并补变更记录，`docs/contracts/policy.md` 加 POLICY-I001 到 I006。
2. 写补丁与测试：K2、K3 在容器 CPU 上跑；改 `make_patched_fc_src.sh`，两台生成新副本并按 sha256 清单核对（第 5 版补丁改了 `nonfinite_guard.py` 与 `runner.py`，ml40 上第 4 版的副本挪开重生成）。
3. ml40 GPU：`nfg_gpu_gates.sh` 跑 T4 基准与 T4、T1、T1b、T2 (a)–(d)、T2n、K1、T6，约 40 分钟；之后 T5（重训链的冒烟名）。
4. 闸都过：两台起重训（tmux 脱机），约 2.2 小时；之后评测、导出、打包，上传器只跑 `--dry-run`。

### B.8 第 4 版对审查意见的处理

| 意见 | 处理 |
|---|---|
| M1 学习器漏了重置后的观测与上下文两个入口 | B.3：四个数组同一个判据，命中就一起换；K3 加“只有重置后的量坏了”的用例并连喂 8 步 |
| M2 坏世界那一步把终止项也清零 | B.3：写成“终止 1、其余 0” |
| M3 T4 在 CPU 上测不到环境侧；相位按第 356 维硬编码 | T4 放 GPU；相位按名字从上下文取；另加 K1 |
| M4 T5 的范围判据四成概率误停、又挡不住小改动 | T5 只看跑完、有限、计数 0、吞吐；“没有事件时不变”改由 K1–K3 证明；学习器侧改成单独的前置函数 |
| M5 T6 没写世界数与注入时机；注入只代表一种事件 | T6 写明 2048 个世界、第 300 步注入、再跑 1000 步；T2 加三种注入 |
| M6 记录报不出各次事件，也没有“事件太多就停” | 两种计数、相位范围、事件行；登记停止条件 |
| MINOR 1–2 B.1 漏了物体朝向那条路；Newton 还写 ctrl 等 | 已写进 B.1，并补了 A 取证的实测 |
| MINOR 3 判据只看几个刚体；transform 不要直接调 isfinite | 遍历全部刚体，vec3、quat 分开判，另加 1e3 m 的超远判据 |
| MINOR 4 很大但有限的 warmstart；取不到 mjw_data | 写明可能记两次；`getattr` 取、断言世界数 |
| MINOR 5 T1 的后备做法无效 | 删掉；加 T1b、T2c |
| MINOR 6–8 n-step 窗口、乘法掩码、fp16 判据、诊断量、相位初值、原因位 | 都写进 B.3 |
| MINOR 9 KEEP_STATES 要写进队列行、ALLOW_FC_SRC、留 4 份、副本清单 | B.5、B.3 |
| MINOR 10 导出表按规则生成；要补 ADR 变更记录 | B.5 |
| MINOR 11 少了“评测里出现非有限世界”的结局 | B.5 |
| MINOR 12 分析记录两处叙述 | 已改分析记录（6934475，“更正（10/2 19:30）”一节） |

### B.9 第 5 版对 Fable 5.1 审查意见的处理

| 意见 | 处理 |
|---|---|
| MAJOR A 重置后的观测与上下文被一起换掉 | B.3：四个数组各按自己的判据换；补丁里的实现本来就是逐数组判（第 4 版计划的文字与实现不一致，以实现为准改了文字）；K3 加“环境已重置、终止观测 NaN、重置后观测有限 → 原样返回” |
| MAJOR B ALLOW 与 FC_SRC 不能写进队列行 | B.5：写进链的启动命令；补期望表、冒烟队列、cfgcheck、precheck 这几步 |
| MINOR 1 ADR 正文与契约 | ADR-00003 的 toolkit 接入一段加训练副本的说法、补变更记录；policy.md 加 POLICY-I001 到 I006，测试 docstring 指回 |
| MINOR 2 哨兵进 W&B | 清洗函数计数后把哨兵清成 0（补丁），K3 断言 |
| MINOR 3 停训在链里分不出来 | 事件行、停训行用固定前缀 `NONFINITE_GUARD_EVENT` / `NONFINITE_GUARD_STOP`（补丁），结局按这一行判 |
| MINOR 4 计数不进 checkpoint | B.3 写明续训从 0 起 |
| MINOR 5 实现约束 | B.3 写明；补丁本来就满足（无宿主分支、全 `jnp.where`、int32、按名字找） |
| MINOR 6 相位取终止上下文 | 补丁改成取 `next_critic_context`，非有限时退回；K3 断言 |
| MINOR 7–8 注入写 joint_q / joint_qd；(d) 显式造；图里跑 | B.4 的 T2 行；`nfg_env_probe.py` |
| MINOR 9 T1 的预期 | B.4 的 T1 行 |
| MINOR 10 K1 的输入 | K1 拷 `body_q`、`timestep`、`episode_step` 与物体参考位姿 |
| MINOR 11 对照不用环境变量 | T2n 只在探针进程里替换 `_solver_rows_to_clear` |
| MINOR 12 na = 0 | 补丁的 `_solver_rows_to_clear` 跳过宽度 0（K2 已测） |
| MINOR 13 T5 判据与名字 | 吞吐改成 95%，run 名取链的冒烟名 |
| MINOR 14 export_map | B.5 写明规则、正则、先挪走再生成 |
| MINOR 15 学习器判坏多记一个回合 | B.3 写明 |
| MINOR 16 清单的注释行 | 清单不写注释行（现在就没有），`make_patched_fc_src.sh` 不改 |
| 替代设计 | 不采用：一律清 warmstart 会失去“没有事件时逐位不变”；只改环境侧会失去学习器那张安全网与停止条件 |

