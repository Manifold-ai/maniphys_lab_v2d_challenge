# 计划：ep1、ep7 训练发散（NaN）排查

- 日期：2026-09-30（MDT）；分支 `track2/p1-training`，起点 1ced9bf
- 状态：第 2 版，按独立审查（GO WITH FIXES，无 BLOCKER）修改后登记；C2 与 M1/M2 已可执行，GPU 步骤（G0、G1、G3、G4）写出细节、再过一次 review 才跑
- 相关记录：`agent-doc/experiments/2026-09-29-batch1.md`（ep7 冒烟、ep1 评测失败）

## 目的

1. 查清 ep1（vacuum_left_lean_02）与 ep7（iron_round_table_02）训练发散的原因，给出能训出有限 policy 的办法。
   官方每条 episode 只评 1 个世界、每次提交要全部 30 条；这两条的 policy 评测时大量世界发散，评测器直接报错，交不出轨迹。
2. 让训练链能早发现发散：ep1 从 5000 万步坏掉到训完，空跑约 3.5 小时 GPU，链没有察觉。
3. 监视今天在 mf4090 上正式训练的 ep28（第三条方盒支撑面），坏了就止损。

不在本计划内：怎么重训 ep1 / ep7（对策定下后另写计划）；提交流程。

## 已核实的事实

| # | 事实 | 证据 |
|---|---|---|
| 1 | 两台共 76 份训练日志，74 份有 W&B 摘要；摘要里动作均值、熵、回报为 nan 的只有 2 份：ep1 正式训练（mf4090）与 ep7 冒烟（ml40）。两份 `mixed_precision/loss_scale` 都是 0，回合平均长度约 5 步 | `results/diverge/train_nan_scan_{mf4090,ml40}.txt`（`stages/policy/train_nan_scan.py`） |
| 2 | ep1 的 policy checkpoint：4000 万步（40,001,536）全部有限，5000 万步（50,001,920）起每份都是 5892 / 1,207,577 个 NaN，直到训完。ep7 冒烟的最终 checkpoint（4,096,000 步）也是 5892 个 NaN | `results/diverge/ckpt_nonfinite_ep1.txt`、`ckpt_nonfinite_ep7_smoke.txt`（`stages/policy/ckpt_nonfinite.py`） |
| 3 | 其余已完成的 73 个 run（mf4090 35 个、ml40 38 个，含冒烟）的最终 checkpoint 全部有限 | `results/diverge/ckpt_nonfinite_last_{mf4090,ml40}.txt` |
| 4 | 审查抽查（待 C2b 落盘）：NaN 只在 `state.0021–0030` 这组成对的 256 / 1024 / 486 维向量里，推断是 BN 或观测归一化的滑动统计（配置 `batch_norm_update_rate=0.01`）；2 维 kernel 与 43 维输出头都有限；486 维那对里 386 维是 NaN，正好是位置、速度、关节、目标历史几块。配置 `compute_dtype=float16`、`replay.observation_storage_dtype=float16`；5000 万步后 31 个张量里 29 个逐字节不变（训练实际停了） | 审查报告；C2b 按张量重扫后落盘 |
| 5 | ep1 的冒烟（400 万步）正常；正式训练前 4000 万步每 1000 万步约 3 分 20 秒，第 5000 万步起约 7 分 20 秒。ep1 在 3000–4000 万步之间进入课程第 1 段（voc 1.0 → 0.75）；ep7 在第 0 段、约 240 万步就坏了（审查读 W&B 本地文件所得，待 C3 落盘）。W&B 摘要的迷你曲线显示动作均值在约第 3/40 个采样点就是 nan，比 checkpoint 坏的 4000–5000 万步早，这个矛盾由 C3 查清 | `results/batch1/pace_mf4090_a.txt`、`results/batch1/nonfinite_scan_mf4090.txt`；C3 |
| 6 | ep7 冒烟的 256 世界诊断 rollout 172 个世界位姿非有限；ep1 训完的 3 个 checkpoint 各评 4096 世界，2445 / 2387 / 2342 个非有限，随后评测器报 ValueError | `results/ml40/batch1/ep7_smoke_diag_excerpt.txt`、`results/batch1/ep1_eval_failure_excerpt.txt` |
| 7 | 评测器（v0.4.0 与 aee95f2 相同）：非有限世界只把位姿清零，completion 仍含全部世界；任何世界 terminated 就报错 | `results/batch1/termination_facts.txt` |
| 8 | 30 条的支撑面：16 条空，11 条是高 4 cm 的圆柱，3 条是方盒：ep1 `chair_back` 2×12×27 cm（中心高 0.715 m），ep7 `tabletop` 84×28.2×1 cm（0.777 m），ep28 两块 10×13×2 cm（约 0.706 m）。**这个分组是看到失败以后才定的**：方盒 3 条里冒烟 1/3 发散（ep7），ep1 在正式训练里坏；非方盒已训完 25 条，0 条发散 | `results/diverge/support_shapes.txt`、事实 1–3 |
| 9 | ep1 参考里物体最低点比地面低 22.5 mm（对齐检查 ALIGN）；但 ep17（−12.8 mm）、ep22（−12.5 mm）也低于地面，都训完没事。ep7 对圆桌面间隙 −0.2 mm（OK） | `results/batch_summary_v040.tsv` |
| 10 | `fc_stop.sh` 先放 STOP 标记再停容器；按代码，fc_run 记 stopped、不重试，训练链记失败、接着跑下一条，评测链对没有 DONE 的 run 不评。**这条路径只读过代码、没实际走过**（9/27 的停止测试走的是退出码 137、链退出码 5 的路径） | `stages/policy/fc_stop.sh`、`day2_train_chain.sh` |
| 11 | 卡：ml40 的 B 段约 09:05 训完、评完后空闲；mf4090 的 B 段 ep24 → ep28（约 09:00–11:15）→ ep29，约 14:35 评完 | 链日志、`results/{ml40/,}batch1/pace_*_b.txt` |

## 假设（不互斥）

- **H1 方盒支撑面让个别世界的物理量爆掉**（薄盒 1–2 cm 被压穿、隧穿，接触冲量极大）。
- **H1c 方盒相关代码路径的数值问题**（盒子距离、法向里的零除等），与接触物理无关。
- **H2 ep1 参考穿地 22.5 mm**（ep17、ep22 也穿地却没事，只作次要）。
- **H3 与场景无关的随机数值不稳**。
- **H4 放大路径（审查补充）**：个别世界的观测在 fp16 下溢出成 inf → 归一化的滑动统计变 nan → 此后所有输入都是 nan，loss scale 跳步护住了权重却护不住统计量，整条训练死掉。
  H1–H3 回答“爆掉的频率跟什么有关”，H4 回答“为什么一个世界爆掉就毁掉整条训练”。两者都要查，对策也分两层：减少爆掉 + 统计量不被污染。

## 判据（执行前登记，结果出来后不改）

- **发散起点**：第一份含非有限参数的 policy checkpoint；W&B 本地记录里各指标第一次非有限的步数作细化（C3）。
- **单条冒烟的“发散”**：冒烟结束时 W&B 摘要有 nan，或最后一份 checkpoint 含非有限参数。
- **复现**：ep7 原场景种子 42 单列，只看能不能复现（不计入下面的比例）。
- **H3 检验**：按事实 1–3，单条冒烟发散的基础率约 1/39。ep7 原场景新种子 43–46：≥ 2/4 发散 → 拒绝 H3（H3 下概率约 0.4%）；
  0/4 → 不拒绝 H3；1/4 → 补种子 47–50，8 个里 ≥ 3 次才拒绝。
- **H1 检验**（只在 H3 被拒绝后判）：同样的新种子下，加厚方盒（顶面高度不变）与 4 cm 圆柱（顶面高度不变）两组各 0 次发散 → 支持 H1（发散来自薄方盒）；
  任一对照组也 ≥ 2/4 发散 → H1 不成立。
- **H1c**：C4 找到只有方盒走的计算，并在 CPU 上用最小例子构造出非有限输出。
- **H4**：C4 找到统计量的更新处没有非有限过滤，且 C3 显示统计量坏在环境侧指标（观测、跟踪误差）先出现非有限之后。
- **ep28**：正式训练出现非有限 checkpoint → 方盒添一例；训完都有限 → 如实记下。

## 步骤

### CPU（不占卡，不同步服务器；脚本都在仓库里，经 `scripts/dev/pipe-py` 在训练机执行、`scripts/dev/record` 落盘）

- **C1** ep1、ep7 冒烟训练日志末尾的 W&B 摘要段落盘。
- **C2**（已完成，事实 2、3）checkpoint 扫描。**C2b**：`ckpt_nonfinite.py` 加按张量报告，重扫 ep1 的 40M、50M 与 ep7 冒烟，落盘事实 4 的张量名与维数。
- **C3** 本地 `.wandb` 历史（不用 W&B API 与凭据）：解析 ep1、ep7 冒烟的 `run-*.wandb`，报各指标第一次非有限的步数，
  看是环境侧（回报、跟踪误差、终止比例）先坏，还是 loss / Q 先坏；解析要 wandb 包，在 ml40 空出后进容器跑，或确认 protobuf 可用后用 pipe-py。
- **C4** 代码阅读（`stages/policy/support_code_facts.sh`，经 gh api 读上游 v0.4.0，逐行带文件与行号落盘）：方盒与圆柱在场景构建、观测、回报、终止里的差别；
  归一化滑动统计在哪更新、用什么 dtype、有没有非有限过滤；训练时对非有限状态有没有防护；loss scale 遇到 nan 的处理。
- **C5** 参考几何（`stages/retarget/support_penetration.py`）：ep1、ep7、ep28 每帧物体网格到方盒与地面的最小有符号距离，报穿透 > 5 mm 的帧数与最深处；
  对照几条圆柱支撑面的序列。机器人与方盒的穿透要 FK，列为可选。

### ep28 监视（mf4090，ep28 正式训练约 09:00 起）

- **M1** 部署前先提交 `ckpt_nonfinite.py`；复制到 mf4090 的 `runs/tools/`（不在同步范围，不碰 `.v2d-source-commit`），核对 md5 与提交一致，
  `setsid nohup` 起看守：每 2 分钟扫一次 `t1-ep28-w2048-cap4m-mf4090` 新写完的 policy；另每轮数本地 `.wandb` 里的 NaN 字样，变了就报（只报警）。
  日志 `runs/logs/ep28_nan_watch.log`，启动时打出脚本 md5 与提交号；run 出现 DONE 或 STOP、或 6 小时到时退出。结束后用 record 把日志拉进 `results/diverge/`。
- **M2 止损规则（本计划新登记）**：按步数**连续两份完整的 policy checkpoint 都含非有限参数** → `stages/policy/fc_stop.sh t1-ep28-w2048-cap4m-mf4090`。
  已有 DONE 或 STOP 时不止损。按 ep1 的轨迹，这条规则会在第 6000 万步停下，省约 3.5 小时。打开前提：事实 3（健康 run 全部有限，已满足）。
- **M2 的恢复预案**：fc_stop 之后链马上对 ep29 做 `gpu_check`；若那一刻显存还没放掉，链会以 DAY2_TRAIN_FAILED 结束，等着的评测链随即开评，ep29 不会训。
  出现这种情况：评测链跑完后，单独 `fc_run` ep29 的正式训练（冒烟已过），训完单独评测，另记执行偏差。
- **M3** 看守只读，唯一的写操作是 `fc_stop.sh`；不碰链、不同步。

### GPU（ml40 空出后；不占 mf4090）。细节写成附录、再过一次 review 才跑

- **G0 零残差动作 rollout**：用全零输出的 policy（输出层置零的 checkpoint 副本）在 4096 世界里走完整条参考，数每种几何（原方盒、加厚方盒、圆柱）下多少世界炸掉。
  没有训练噪声，每条约 3 分钟；直接回答“场景本身会不会炸”。
- **G1 ep7 复现与 H3 检验**：冒烟长度（4,096,000 步），原场景，种子 42（复现）与 43–46。
- **G3 ep7 几何对照（主对照）**：同样种子，加厚方盒（顶面高度不变）、4 cm 圆柱（顶面高度不变）两组。诊断用的支撑面只放 `runs/diag/`，不进提交用的训练。
- **G2 去掉方盒（可选）**：`scene.support=false` 会连带改变接触、终止与回合长度，且 VOC（第 0 段 voc_scale=1.0，最大 60 N）可能托住熨斗，只作参考、不进判据。
- **G4 ep1 截断复现**：ep1 坏在课程第 1 段（3000–5000 万步），与 ep7 的第 0 段触发条件不同，G1–G3 的结论不能直接套过去。
  用 1–2 个新种子训到约 6000–7000 万步（每条约 30 分钟），看是否再坏、坏在哪一步。
- **运行方式**：`make_batch_queue.py` 写死了 `t1-ep…` run 名与种子 42，`precheck_expect.sh` 与 `day2_train_chain.sh` 断言正式步数 349,999,104，
  走批量链会在冒烟后接着开 3.5 亿步的正式训练。所以诊断队列手写：只有冒烟长度（G4 为截断长度）、run 名带 `diag-` 前缀、
  `reset.seed=N training.seed=N`（Day 2 的 s43 有先例）、W&B 项目 `v2d-selftest`、`V2D_WANDB_UPLOAD_CKPT=0`；先过 `fc_config_check.sh`，
  再在 tmux 里用 `fc_queue.sh` 跑。`fc_queue.sh` 不写 `.chain-active`，跑的时候手动放一个，挡住同步。

## 之后的决定（不在本计划内，结果出来后另写）

- 对策分两层：减少爆掉（场景或接触参数；改场景要先问组委会）；统计量不被污染（归一化更新加非有限过滤、关 fp16 存储或计算，偏离配方要登记）。
  梯度裁剪碰不到滑动统计，不列入。
- 训练链加发散检测：冒烟判据加“W&B 摘要无 nan、最后一份 checkpoint 全部有限”；正式训练加 M1 那样的看守。改链脚本要等两台的链都结束后再同步。

## 不做的事

- 不改正在跑的链；mf4090 的链结束（约 14:35）前不同步 mf4090，ml40 在 B 段评完前不同步。
- 不在 mf4090 训练期间占它的卡；诊断用的场景改动不进提交用的训练。
- 不因为发散去改已登记的 Day 1 判据或第 1 批的判定。

## 时间

- C1–C5：今天上午（CPU）；M1 在 09:15 前布好，ep28 结束或止损后收尾。
- G0–G4：写出附录、review 后在 ml40 上跑，GPU 约 2–3 小时。
- 结论：今天下午到晚上；对策与 ep1、ep7 重训另写计划。

## 审查与处理（09-30 08:50，独立审查：GO WITH FIXES，无 BLOCKER）

- MAJOR 1 发散的放大路径（fp16 溢出 → 归一化统计 nan）没有单列 → 加 H4、判据与 C4 的对应项；对策里删掉梯度裁剪；“权重 nan”改成“统计量 nan（待确认）”。
- MAJOR 2 判据偏向 H3，种子 42 不独立 → 42 单列为复现；每组新种子 43–46；≥ 2/4 拒绝 H3，1/4 补种子；H1 看组间差别。
- MAJOR 3 `scene.support=false` 有混杂，“熨斗会掉”未核实 → 主对照改为加厚方盒与圆柱，去掉方盒降为可选；加 G0 零残差动作 rollout。
- MAJOR 4 批量工具生成不了诊断队列，走批量链会接 3.5 亿步正式训练 → 手写诊断队列、用 `fc_queue.sh` 跑、手动放 `.chain-active`。
- MAJOR 5 ep1 与 ep7 的触发条件不同 → 加 G4 ep1 截断复现。
- MINOR 6 W&B 历史在本地 `.wandb` 文件里 → C3 改为解析本地文件，不用 API 与凭据。
- MINOR 7 事实表的措辞与遗漏 → 事实 5、8、9、10、11 已按意见改（分组是事后定的、ep17 / ep22 也穿地、fc_stop 路径没走过、ml40 约 09:05 空出）。
- MINOR 8 看守的细节 → DONE 优先于止损（脚本已改、测试 4 条通过）；启动时打印 md5 与提交；加 `.wandb` NaN 报警；止损在事实 3 满足后才打开；
  写好 ep29 的恢复预案；日志收尾用 record 拉回。
