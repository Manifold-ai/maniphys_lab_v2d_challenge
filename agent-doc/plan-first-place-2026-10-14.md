# 计划：Tier 1 与 Tier 2 各榜争第一（2026-10-14，第 3 版）

10/14 14:15 MDT 用户：“我们力求所有第一”。14:17 的榜上，我们在 Tier 1、Tier 2 的 8 个榜里有 4 个第一（Tier 1 SP-SR，Tier 2 AUC、SP-SR、MP-SR），
其余 4 个（Tier 1 AUC、MP-SR、MPPE，Tier 2 MPPE）都排在 Xueyi Wang (FF) 后面。本计划只收集事实、列选项与判据，这一步不用 GPU，
不同步、不起链、不停任何进程、不提交。两台机器上 Tier 3 试点的链约 21:20 MDT 才结束。时间一律 UTC−6（MDT）。第 1 版（3ece756）经独立审查（Fable 5.1）为 GO WITH FIXES，第 2 版（dc0c9ca）按审查意见修改；第 2 版再审仍是 GO WITH FIXES，第 3 版按第二轮意见修改，逐条处理见第 8 节。

## 1. 事实

### 1.1 榜单与差距

- 14:17 的榜（`results/submission/leaderboard_1014_1417.txt`）：
  - Tier 1：AUC FF 0.56422、我们 0.54623；SP-SR 我们 0.73333 第一；MP-SR FF 0.66666、我们 0.63333；MPPE FF 8.22045、我们 16.55939 cm。
  - Tier 2：AUC 0.51379、SP-SR 0.73333、MP-SR 0.53333 我们第一；MPPE FF 15.34253、我们 16.54028 cm。
- 交上去的 Tier 1 CSV（t1c1014b）对 FF 的差距（`results/t1gap/t1_gap_t1c1014b.txt`；11:33 以 `--candidate` 对照 07:35 的榜算的，早于 13:53 的提交，
  FF 的行此后没变、交上去的分数与 PACKED 相差小于 1e-5，所以数字成立）：MP-SR 要多成功 2 条（现在 19 条，FF 20 条）；
  AUC 的 30 集合计还差 0.540；MPPE 的 30 集合计还要减 250.2 cm。MPPE 超过 15 cm 的 7 集合计 436.3 cm，占 30 集总和 496.8 cm 的 87.8%。
  按 `t1_gap.py` 的“像成功的”假设（修好的集取 AUC 0.722、MPPE 2.09 cm），修好 ep25、ep4、ep28 三集 MPPE 就到 7.62 cm。
- Tier 2 MPPE 每集平均还差 1.198 cm，30 集真值 MPPE 合计要减 35.9 cm 以上（`results/first/t2_mppe_proxy.txt`）。

### 1.2 规则（官方原文与我们的解读分开）

官方原文（Kaggle 比赛规则页，sha256 b397f3d1…，`results/ops/kaggle_rules_submission_1014.txt`；比赛说明页，`results/ops/kaggle_rules_evaluation_page_1014.txt`；
kit，`third_party/v2d_submission_kit/update_0f2f9f4b/v2d_submission_kit/`）：

- “A different checkpoint may be used for each sequence.”
- “**Leaderboard positions are subject to verification.** Before any award is confirmed, the Competition Sponsor may require any Participant to
  demonstrate that their reported scores were produced by the submitted pipeline, and not by manipulation of the metric, the Submission file, or
  the evaluation process.” 应要求要交 “a single command-line invocation that runs that code against the Competition Data and reproduces the Submission”。
- “Train your policy using this tier's allowed input, record its object-pose rollout with the challenge evaluator, and pack the trajectory for Kaggle.”
- kit `tracks/track_2/README.md`：“Include all scored episodes and use one checkpoint per episode.” kit `config/tracks.json` 里 Track 2 三档
  `worlds_per_episode` 都是 1（`results/submission/kit_facts.txt` 第 30–32 行）；kit 的 `examples/run_policy_evaluation.py` 默认 `--world-count 1`、
  `evaluation.reset_mode=explicit`。我们的导出（`stages/evaluate/fc_export.sh`）与它逐项相同。
- 评测器（FlashCHORD 8c778f9）评测时把所有世界都重置到第一帧，重置种子固定为 42（`results/first/harness_eval_composition_mf4090.txt`）。
- “Held-out evaluation does take place, but not on this platform. After the Competition closes, the Competition Sponsor evaluates selected solutions
  against data that is not part of the Competition Data and is not distributed to Participants.”“You may select up to 2 Final Submissions for judging.”
- “Every Submission must record the code that produced it. The `code_commit_url` column of your Submission must link to a commit in a Git repository
  shared with the V2D organisers' account”。10/14 13:54 组委会账号 Nvidia-V2D-Challenge 仍不是仓库协作者（`results/ops/collab_check_nvidia_1014_1354.txt`）。

我们的解读：

- 每集用不同的 checkpoint：规则明文允许（“A different checkpoint may be used for each sequence.”）。唯一的约束是 2.2.d
  “the checkpoint digest must be identical within each episode”。kit 的 `examples/run_policy_evaluation.py --checkpoints`（“JSON object mapping
  episode index to its checkpoint path”）用 2.9.b 要的单条命令就能复现逐集选择。
- 在候选之间按本地 1 局的分数挑：条文没有提到，也没有禁止。我们交过的两次都是这样挑的；交的轨迹就是评测器对那个 checkpoint 录的那 1 局。
- “同一个 checkpoint 导出 N 局、交成功的那一局”（选项丁）：kit `config/tracks.json` 写明 “under reset_mode=explicit every world resets to the same
  frame and runs a deterministic policy, so the cohort is expected to be redundant and only one world is submitted”，样例 CSV 的世界只有 `w000`
  （`results/submission/kit_facts.txt`）。交第 k 局就要改行号，既动了评测流程，也动了提交文件，容易被认成 2.9 的 “manipulation of … the evaluation
  process”。没有组委会书面同意就不做。
- 待验证（第 3 节第 0 步测）：同一个 checkpoint 按 kit 的做法再导出一次，得到同一局。kit 假设各世界相同，而我们的 4096 世界评测里同一个 checkpoint
  的世界有成有败（例如 ep14 r3a 的 MP-SR 0.677），所以这一条不能默认成立；它同时撑着 2.9.b 的复现与选项乙。

### 1.3 Tier 1：交的那 1 局与同一 checkpoint 4096 世界的成功率

`results/first/t1_multiworld_estimate.txt`（`tools/t1_multiworld_estimate.py`，读 t1c1014b 的 select 记录与已落盘的评测）：

| 集 | 交的 run | 交的那局 SP / MP / AUC / MPPE | 4096 世界 SP-SR / MP-SR | 候选里 4096 世界 MP-SR 最高的 run |
|---|---|---|---|---|
| ep14 | t1-ep14-w2048-cap4m-mf4090 | 1 / 0 / 0.330 / 5.89 | 0.711 / 0.000 | t1-ep14-w2048-cap4m-r3a-mf4090：0.677（它那 1 局 SP 0、MP 0、MPPE 78.03） |
| ep19 | t1-ep19-w2048-cap10m-r3a-ml40 | 1 / 0 / 0.430 / 3.68 | 0.735 / 0.258 | 同交的 run |
| ep10 | t1-ep10-w2048-cap4m-r3a-mf4090 | 1 / 0 / 0.379 / 3.77 | 0.957 / 0.008 | 同交的 run |
| ep2 | t1-ep2-w2048-cap10m-r3a-ml40 | 0 / 0 / 0.422 / 24.51 | 0.138 / 0.001 | 同交的 run |

跟丢的 7 集（ep25、4、28、11、9、1、2）4096 世界 MP-SR 都是 0 或接近 0，见 1.5。

### 1.4 估算（假设见 `tools/t1_multiworld_estimate.py` 文件头：每次抽取独立、成功概率等于 4096 世界的成功率；变成功的集取“像成功的”AUC 与 MPPE）

- 新种子（只补 ep14、ep19，每集 k 个；`results/first/t1_seed_estimate_ep14_ep19.txt`）：
  | k | 期望多出 MP 成功 | 至少多 2 条（MP-SR 超过 FF）的概率 | AUC 期望 |
  |---|---|---|---|
  | 1 | 0.94 | 0.175 | 0.5576 |
  | 2 | 1.35 | 0.403 | 0.5623 |
  | 3 | 1.56 | 0.572 | 0.5646 |
  | 4 | 1.69 | 0.689 | 0.5659 |
  AUC 要超过 FF 的 0.56422，大致要 ep14、ep19 两集都变成功。MPPE 只降到约 16.4 cm，这条路拿不到 MPPE 第一。
- 多导几局（选项丁，只作参考，`results/first/t1_multiworld_estimate.txt` 乙）：N=16 时期望多出 2.13 条 MP 成功，至少多 2 条的概率 0.993，AUC 期望 0.5705。
- 这两种估算都高估：ep14 r3a 那个 checkpoint 的第 0 局已经失败过一次，说明第 0 局对 ep14 可能偏难；种子 43 与 42 的 4096 世界 MP-SR 也会差
  （r3a 8 对最大差 0.348，`results/t3dyn/seed_pair_diff_t1_cap4m_r3a.txt`）。

### 1.5 Tier 1 跟丢的 7 集

`results/first/t1_fail_runs.txt`（`tools/episode_runs_table.py`，每个 run 取步数最大的那次 4096 世界评测）：

- ep25、ep4、ep28、ep9、ep1、ep11：Tier 1 试过的 run 4096 世界 MP-SR、SP-SR 都是 0，骨盆失败比例 0.988–1.000（几乎每个世界都摔）。
  ep2 的 r3a run SP-SR 0.138、MP-SR 0.001。变体 A（r3a）在 Tier 1 只在 ep2 上试过；ep25、4、9、11 的 r3a 原定在 10/12 计划的 C 段（t1ya），
  按登记的停手规则（t2xb 的 9 条里没有一条 ≥ 0.5）没有起（`agent-doc/plan-next-training-2026-10-12.md` 执行记录 10/13 07:09）。
- 同集 Tier 2：ep25、4、28、9、1 两种配方都是 0、骨盆约 1.0；ep11 的旧配方骨盆失败比例 0.396、物体 0.593（约六成世界没摔）；ep2 的 r3a SP-SR 0.422。
- 任务（`results/site/task_table.txt`）：ep25 两手交替传递水瓶，ep4 拿球棒边转边绕场地，ep28 双手持刮水器扫地，ep1 单手持吸尘器左右推，
  ep9 双手把大碗从椅子上放到地上，ep2 单手拿篮子换位置，ep11 把书从桌上放到地上。前四个是持工具或双手传递、全身持续运动的任务。
- 现有记录里没有逐帧信息，说不清是接近、抓取还是跟踪阶段失败、骨盆何时失守。已有两套工具，都要用 GPU：
  - `stages/evaluate/fc_eval_dump.sh` 加 `stages/evaluate/fall_order.py`：存逐步、逐世界的误差，给出骨盆失守与接触帧的先后，开销同一次 4096 世界评测。
  - diag2（`stages/evaluate/diag2_chain.sh`，`diag_rollout.py`、`diag_phase.py`）：把世界分成接近、抓取、跟踪三类失败；运行表只认 `^t1-` 的 run，
    且要求那条 run 已有的 4096 世界评测是默认 v0.4.0 运行时算的，t1xb、t1yb 与 Tier 2 的 run 按现状起不了。10/3 三集各用 5–7 分钟 rollout 加
    1–3 分钟分析（`results/diag2/chain_log_mf4090.txt`）。

### 1.6 Tier 2 MPPE（只用 Tier 2 的数据）

档位隔离：Tier 2 没有本地真值，下面用的是交上去的 run 在 4096 世界里对照自己参考（降噪后的 Tier 2 轨迹）的 MPPE，不读 Tier 1 的任何数据
（`results/first/t2_mppe_proxy.txt`，`tools/t2_mppe_proxy.py`）。

- 30 集平均 19.156 cm、合计 574.7 cm；超过 15 cm 的 8 集合计 481.1 cm（83.7%）：ep4 119.8、ep25 117.1、ep28 58.7、ep9 56.9、ep1 46.7、
  ep17 34.4、ep2 26.4、ep11 21.1。
- 这是“跟自己的参考差多少”，不是榜上对照真值的 MPPE。跟丢的集在真值上也一定差得多，所以只拿它找拉高总和的集。真值上要减 35.9 cm，
  大致相当于把一集从几十厘米的“跟丢”变成几厘米的“跟住”（推断）。
- 榜给的只有每次提交的四个总数，每周每榜 5 次。

### 1.7 GPU

两台 GPU 都在跑 Tier 3 试点，约 21:20 结束（`agent-doc/plan-t3dyn-pilot-2026-10-14.md` 第 9 节）。试点若支持 best_dyn4，Tier 3 全量重训约 60 个 GPU 小时，
会与本计划抢卡。

### 1.8 核对

本节 12 条承重的事实都经 jev 核实（0.77–0.99），对照 4 道正常（`results/first/jev_claims_first_place.txt`；规格 `agent-doc/experiments/2026-10-14-first-place.claims.json`）。分析脚本：`tools/t1_multiworld_estimate.py`、`tools/episode_runs_table.py`、`tools/t2_mppe_proxy.py`，规则摘录用 `tools/kaggle_rules.py` 新加的 `--pattern`、`--pages`。`results/first/t1_multiworld_estimate_run1.txt` 是只有甲、没有乙的第一版输出。

## 2. 选项

| 选项 | 做什么 | 针对的榜 | GPU（估计） | 预期 |
|---|---|---|---|---|
| 零 | 复现性：交上去的 ep14（`t1-ep14-w2048-cap4m-mf4090`）与 ep19（`t1-ep19-w2048-cap10m-r3a-ml40`）最终 checkpoint 按 kit 的做法各再导出 1 局，与候选文件比 sha256。`fc_export.sh` 遇到已有结果只打印，所以加一个输出后缀 `V2D_EXPORT_SUFFIX`（默认空，行为不变） | 2.9.b、乙的前提 | 2 局 × 约 2 分钟 | 相同才做乙；不同就报用户 |
| 乙 | 先探：ep14 r3a（mf4090）与 ep19 r3a（ml40）各 5 份更早的 checkpoint（300011520、310011904、320012288、330012672、340013056，`results/first/snapshots_ep14_ep19.txt`）按 kit 的做法导出 1 局，读导出 JSON 的四项；4096 世界评测走 `fc_eval_dump.sh`，第 0 世界与 1 局导出对照。有一份那 1 局 MP 成功，才做第二步：逐条选支持带步数的候选 | Tier 1 MP-SR、AUC | 10 份 × 约 7 分钟 ≈ 1.2 GPU 小时 | 相邻 checkpoint 相关，成功概率比新种子低，但最便宜 |
| 甲 | 新种子：ep14、ep19 各补 1 条 seed 43（`t1-ep14-w2048-cap4m-r3a-s43-mf4090`、`t1-ep19-w2048-cap10m-r3a-s43-ml40`）。现有生成器出不了单条的 s43：`make_trial_queue.py` 只出 10/7 试验的段，`make_var_queue.py` 只出 seed 42。甲排上之前给 `make_var_queue.py` 加种子参数、补测试、另审（不用 GPU，可在乙、丙跑的时候做） | Tier 1 MP-SR、AUC | 2 条 × 约 2.1 小时 | k=1 时多 2 条 MP 成功的概率约 0.175（偏乐观，1.4） |
| 丙 | 跟丢的集先诊断：Tier 1 的 ep25、4、28、9、1、11 与 Tier 2 的 8 集，各用本档交上去的 run 跑 `fc_eval_dump.sh`，再用单条 run 的驱动 `stages/evaluate/fall_order_one.py`（第 0 步新写，调 `fall_order.py` 的 `run_one` 与 `describe`，门与判法不改；`fall_order.py` 的 `main()` 只收 10/7 试验的四条一组）；diag2 只用于它支持的行 | Tier 1 MPPE、AUC；Tier 2 MPPE | 约 14 集 × 5–7 分钟 ≈ 1.5–2 GPU 小时 | 只报；MPPE 第一只能靠修好跟丢的集，诊断之后另写训练计划 |
| 丁 | 同一 checkpoint 导出多局、交成功的那局 | Tier 1 MP-SR、AUC | 不到 1 GPU 小时 | 规则风险（1.2），不做，除非组委会书面同意 |

考虑过但不排：Tier 1 的 ep25、4、9、11 补 r3a。Tier 2 同集的 r3a 都是 0、骨盆约 1.0，Tier 1 大概率同样跟丢，先等丙的诊断。

## 3. 建议的顺序

0. 代码（现在、不用 GPU）：`stages/evaluate/fc_export.sh` 加 `V2D_EXPORT_SUFFIX`（输出目录、日志名与 hydra 目录后加后缀；默认空时一切照旧），补测试；
   `results/ml40/select_t1/t1_select_t1c1014b.tsv` 复制为 `stages/evaluate/exports/t1_select_t1c1014b.tsv`（`select_t1.sh` 只认这个目录）；
   新写 `stages/evaluate/fall_order_one.py` 与测试。提交、代码审查。
1. 两台的 Tier 3 试点链都结束后（ml40 约 20:30、mf4090 约 21:20）同步、跑测试，先做零（ep19 在 ml40、ep14 在 mf4090）。
2. 零通过就做乙的探查与丙的诊断，两台各一半，约 23:30 前出结果。
3. 乙有可用的 checkpoint：另写逐条选的代码改动（候选键改成 `<run>@s<步数>`，贯穿 `stage_t1_candidates.sh`、`relay_t1x.sh`、`select_t1.py`，
   补测试；`fc_eval_dump.sh` 的评测 JSON 写在 `runs/flash_chord/<run>/eval_dump/` 下，而候选与导出链找的是 run 根目录下的
   `eval_<步数>_w4096.json`，这一步一并处理，或探查通过后按现有评测链补评一次），代码审查后进逐条选、打包，报用户。
   乙没有：甲排上（先做生成器的种子参数，见第 2 节）。
4. 丙的诊断出来后另写训练计划、另审。Tier 3 全量重训与本计划怎么分卡，等试点结果出来再定（第 7 节第 2 条）。

## 4. 判据（执行前登记）

- 零：在同一台机器上比，不搬文件。ep14 的再导出（mf4090，`V2D_EXPORT_SUFFIX=_rep1`）对照 mf4090 `runs/exports/export_mf4090.tsv` 里
  `t1-ep14-w2048-cap4m-mf4090` 那一行的 json、parquet 两个 sha256；ep19 的再导出（ml40）对照 ml40 `runs/exports/cand_t1_t1yb_ml40.tsv` 里
  `t1-ep19-w2048-cap10m-r3a-ml40` 那一行的两个 sha256。打分只看 parquet：两份 parquet 都相同记“1 局可复现”，做乙；parquet 相同而 JSON 不同时，
  列出不同的键再定，不直接停；有一份 parquet 不同就停在这一步，不做乙，报用户（现有提交按 2.9.b 的复现要另想办法）。
- 乙的探查：某份 checkpoint 那 1 局导出 JSON 的 `metrics.maniptrans_sr` 与 `metrics.spider_sr_uncentered` 都是 1，记“可用”。
  第 0 世界的对照（只报）：`fc_eval_dump.sh` 的 npz 里第 0 世界的 `mp_success`、`sp_success`、`mp_position_m`、`mp_orientation_deg`，对 1 局导出 JSON 的
  `maniptrans_sr`、`spider_sr_uncentered`、`object_position_error_m`、`object_orientation_error_deg`（允许 float16 的舍入）；AUC、MPPE 没有逐世界的值，不在对照里。进逐条选时登记 `V2D_SELECT_CURRENT=stages/evaluate/exports/t1_select_t1c1014b.tsv`、
  `V2D_SELECT_GATE=0.546236,0.733333,0.633333,16.559396`（`results/ml40/select_t1/select_t1c1014b.txt` 的 PACKED 行），选法不变
  （先比 MP-SR，再比 SP-SR，再比 AUC / 0.3780 − MPPE / 25.1706），打分门 A、B 照旧。新 CSV 只打包、不提交，提交要用户点头。
- 甲的停手：ep14 的 s43 那条 4096 世界 MP-SR 低于 0.3、ep19 的低于 0.2（低于它现有的 0.258），这一集不再补；那 1 局成功的集也不再补。
  补 s44 及以后由用户定（第 7 节第 2 条）。
- 丙：每集报骨盆失守与接触帧的先后（`fall_order.py` 的判法不改）、diag2 能跑的行报接近、抓取、跟踪三类的占比，只报；写训练计划之前不起训练。
- 档位隔离：Tier 2 的诊断、选择与判断只用 Tier 2 的数据；用 `fall_order.py` 跑 Tier 2 之前先核对它读的文件只有 Tier 2 的。Tier 1 的结果不拿来调
  Tier 2 的任何东西。
- 丁：不做。

## 5. 风险

- 1.4 的估算假设各次抽取独立，实际高估（第 0 局固定、相邻 checkpoint 相关、种子间差异大）。
- 所有行都在公榜上，按本地 1 局的分数挑 checkpoint 等于直接对着榜优化；规则说闭赛后还有 held-out 评测，这种挑法在那里不一定有用。
- 仓库还没共享给组委会账号，按规则每次提交的 commit 链接都要指向“shared with the V2D organisers' account”的仓库。
- 与 Tier 3 全量重训抢卡。

## 6. 时间（估计）

- 20:30–21:20 两台的试点先后结束；零约 2 分钟一局；乙与丙约 23:30 前出结果；甲若要做，10/15 凌晨起，约 03:00 出结果。

## 7. 要用户定的

1. 要不要就“同一 checkpoint 导出多局、交成功的那局”给组委会发邮件问（选项丁）。我们的建议是不问、不做，靠乙、甲。
2. 今晚之后的卡：本计划（零、乙、丙、甲，以及甲补 s44 以后）与 Tier 3 全量重训怎么分。
3. 每一次提交的同意；临近封榜时从全部提交里选 2 份 Final Submissions。
4. 请组织 owner 或仓库管理员把 Nvidia-V2D-Challenge 加为协作者（规则 2.9.a）：每次提交的 commit 链接都要指向共享给组委会账号的仓库，交过的两档现在都不满足。

## 8. 审查

第 1 版（3ece756）由 Fable 5.1 独立审查，只读，结论 **GO WITH FIXES**（1 MAJOR、7 MINOR、5 NIT）。审查核过、没有问题的部分：第 1 节 12 条事实与记录逐数相符；
六段规则引文与记录、kit README 逐字相同；三个新工具的正则、文件选取与泊松二项算法都对（k=2、k=4 手算复核一致）；`t2_mppe_proxy.py` 只读 Tier 2；
`fc_export.sh` 与 kit 的 `run_policy_evaluation.py` 参数逐项相同；没有用 GPU；没有队友姓名；提交同意权留给用户。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | 乙的更早 checkpoint 进不了现有逐条选：候选按 run 名建目录，`select_t1.py` 写死步数 349999104，`relay_t1x.sh` 见到重名就停 | 采纳并改顺序：乙先只做探查（导出 1 局、读四项），有可用的 checkpoint 才写带步数的候选键（`<run>@s<步数>`）、补测试、另审 |
| 2 | MINOR | diag2 只认 `^t1-`、要求默认运行时的评测，Tier 2 与 t1xb/t1yb 的行起不了；“每集用时没量过”不准 | 采纳：丙主用 `fc_eval_dump.sh` 加 `fall_order.py`，diag2 只跑它支持的行；用时引 10/3 的记录 |
| 3 | MINOR | ep11 “四成世界没摔”说反了 | 采纳：改为约六成世界没摔 |
| 4 | MINOR | 甲的停手门 0.3 会在 ep19 与现有 0.258 持平时就停，k=3、4 到不了；续补没有登记谁定 | 采纳：ep19 的门改为 0.2；补 s44 以后由用户定 |
| 5 | MINOR | 新种子没登记种子号与 run 名，s44 要改生成器 | 采纳：先只补 s43（现成支持），run 名登记在第 2 节；s44 以后要改生成器、另审 |
| 6 | MINOR | “同一 checkpoint 再导出得到同一局”没有记录支撑，却撑着丁的解读与 2.9.b 的复现 | 采纳：新加选项零，先测这一条，不过就不做乙并报用户 |
| 7 | MINOR | 打分门没写值；`select_t1.sh` 只认 `stages/evaluate/exports/` 下的清单 | 采纳：第 0 步复制 `t1_select_t1c1014b.tsv`，门 B 登记为 PACKED 的四项 |
| 8 | MINOR | “每集从不同 checkpoint 里挑，规则明文允许”把两件事合在一起 | 采纳：分开写，补 kit `--checkpoints` 与 2.2.d 的原文 |
| 9 | NIT | 丁的解读可以引 kit 原文加固 | 采纳：引 `config/tracks.json` 与样例 CSV 只有 `w000` |
| 10 | NIT | C 段的停手规则看的是 t2xb 的 9 条，不是同集 | 采纳 |
| 11 | NIT | `t1_gap_t1c1014b` 的时点早于提交 | 采纳：注明 |
| 12 | NIT | 六集“摔”的诊断，`fall_order.py` 直接给骨盆失守与接触的先后 | 采纳：丙主用它 |
| 13 | NIT | 审查提示词放在会话 scratchpad，不会留下来 | 采纳：删掉这句引用，审查的问题与处理记在本节 |

第 2 版（dc0c9ca）再请同一位审查者看改动与第 0 步的代码，结论 **GO WITH FIXES**（5 MINOR、2 NIT）。审查核过：`V2D_EXPORT_SUFFIX` 的校验、输出目录、
日志名、“已有结果”、hydra 目录与锁都对，默认空时与改前相同，9 个旧测试组不变；导出链、提交拉取、兼容检查都按不带后缀的目录找文件，带后缀的不会被当成提交导出；
第 4 节每条判据两个方向都有动作；门 B 的值与 PACKED 行一致；第 1 版 13 条都有处理。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MINOR | 零没写比什么、在哪台机器上比 | 采纳：各在原机器上对照导出表那一行的两个 sha256，表的路径写进判据 |
| 2 | MINOR | 打分只看 parquet，JSON 不同不该直接停 | 采纳：parquet 定结论，JSON 不同列出键再定 |
| 3 | MINOR | “第 0 世界与 1 局导出的四项相同”算不出来：npz 没有逐世界的 AUC、MPPE；`spider_sr` 在 JSON 里叫 `spider_sr_uncentered` | 采纳：改成对照 MP、SP 标记与平均位置、朝向误差，键名照 JSON |
| 4 | MINOR | `fall_order.py` 的 `main()` 只收四条一组的试验清单，单条 run 跑不了 | 采纳：第 0 步新写 `fall_order_one.py`（调 `run_one`、`describe`）与 4 组测试 |
| 5 | MINOR | 现有生成器出不了单条的 s43 | 采纳：甲排上之前给 `make_var_queue.py` 加种子参数、补测试、另审 |
| 6 | NIT | 后缀测试没断言 hydra 目录与预演 | 采纳：补两条断言 |
| 7 | NIT | `fc_eval_dump.sh` 的评测 JSON 不在候选找的位置 | 采纳：写进第 3 节第 3 步 |

## 9. 执行记录

- 15:29 第 0 步（Mac，不用 GPU）：`fc_export.sh` 加 `V2D_EXPORT_SUFFIX`，`test_fc_export.py` 补第 10 组（带后缀重新导出到新目录、日志名带后缀、
  原来那份不动、不合格式的后缀退出码 2），10 组 `ALL_OK`，`bash -n` 通过；`t1_select_t1c1014b.tsv` 复制到 `stages/evaluate/exports/`，与原件 sha256 相同
  （`results/first/tests_mac_step0.txt`）。代码审查见第 8 节。
- 15:39 第 0 步补充（按第二轮审查）：`fall_order_one.py` 与 4 组测试，连同 `test_fall_order.py` 的 7 组共 11 个通过；`test_fc_export.py` 第 10 组补 hydra 目录与
  预演两条断言，10 组 `ALL_OK`（`results/first/tests_mac_step0b.txt`；pytest 用本机缓存的 uv 环境，numpy 取另一份同为 Python 3.13 的缓存环境）。
