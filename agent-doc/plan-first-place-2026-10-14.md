# 计划：Tier 1 与 Tier 2 各榜争第一（2026-10-14，第 1 版）

10/14 14:15 MDT 用户：“我们力求所有第一”。14:17 的榜上，我们在 Tier 1、Tier 2 的 8 个榜里有 4 个第一（Tier 1 SP-SR，Tier 2 AUC、SP-SR、MP-SR），
其余 4 个（Tier 1 AUC、MP-SR、MPPE，Tier 2 MPPE）都排在 Xueyi Wang (FF) 后面。本计划只收集事实、列选项与判据，这一步不用 GPU，
不同步、不起链、不停任何进程、不提交。两台机器上 Tier 3 试点的链约 21:20 MDT 才结束。时间一律 UTC−6（MDT）。第 1 版还没有经过独立审查（第 8 节）。

## 1. 事实

### 1.1 榜单与差距

- 14:17 的榜（`results/submission/leaderboard_1014_1417.txt`）：
  - Tier 1：AUC FF 0.56422、我们 0.54623；SP-SR 我们 0.73333 第一；MP-SR FF 0.66666、我们 0.63333；MPPE FF 8.22045、我们 16.55939 cm。
  - Tier 2：AUC 0.51379、SP-SR 0.73333、MP-SR 0.53333 我们第一；MPPE FF 15.34253、我们 16.54028 cm。
- 交上去的 Tier 1 CSV（t1c1014b）对 FF 的差距（`results/t1gap/t1_gap_t1c1014b.txt`）：MP-SR 要多成功 2 条（现在 19 条，FF 20 条）；
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

- 每集从不同 checkpoint（不同种子、不同步数）里挑，规则明文允许；我们一直按交上去的那 1 局在本地的分数挑，交的轨迹就是评测器对那个 checkpoint 录的那 1 局。
- “同一个 checkpoint 导出 N 局、交成功的那一局”：交上去的轨迹不是按 kit 的做法（1 个世界、种子 42）录出来的那一局，组委会用 kit 的命令重跑会得到另一局。
  这容易被认成上面那句“manipulation of … the evaluation process”。没有组委会书面同意就不做（选项丁）。
- 推断（未核实）：同一个 checkpoint 按 kit 的做法导出，每次得到同一局（种子固定）；不同 checkpoint 面对的“第 0 局”初始状态相同。

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
  按登记的停手规则（Tier 2 同集没有一条 ≥ 0.5）没有起（`agent-doc/plan-next-training-2026-10-12.md` 执行记录 10/13 07:09）。
- 同集 Tier 2：ep25、4、28、9、1 两种配方都是 0、骨盆约 1.0；ep11 的旧配方骨盆 0.396、物体 0.593（四成世界没摔）；ep2 的 r3a SP-SR 0.422。
- 任务（`results/site/task_table.txt`）：ep25 两手交替传递水瓶，ep4 拿球棒边转边绕场地，ep28 双手持刮水器扫地，ep1 单手持吸尘器左右推，
  ep9 双手把大碗从椅子上放到地上，ep2 单手拿篮子换位置，ep11 把书从桌上放到地上。前四个是持工具或双手传递、全身持续运动的任务。
- 现有记录里没有逐帧信息，说不清是接近、抓取还是跟踪阶段失败。已有工具 `stages/evaluate/diag_rollout.py`、`diag_phase.py`（10/9 的 diag2）
  可以把 4096 个世界分成接近、抓取、跟踪三类失败，要用 GPU。

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
| 甲 | ep14、ep19 补新种子（变体 A，配置同现有 r3a run，只换种子），每集先 2 个 | Tier 1 MP-SR、AUC | 4 条 × 约 2.1 小时 ≈ 8.5 GPU 小时 | 见 1.4：k=2 时 MP-SR 超过 FF 的概率约 0.40；k=4（17 GPU 小时）约 0.69 |
| 乙 | 同一 run 更早的 checkpoint（ep14 r3a、ep19 r3a 各取 300M–340M 的 5 份，两个 run 都留着 35 份 policy，`results/first/snapshots_ep14_ep19.txt`）按 kit 的做法评测、导出，进逐条选 | Tier 1 MP-SR、AUC | 10 份 × 约 7 分钟 ≈ 1.2 GPU 小时 | 相邻 checkpoint 很相关，单份成功的概率比新种子低；最便宜 |
| 丙 | 跟丢的集先诊断：Tier 1 的 7 集与 Tier 2 的 8 集各用本档的 run 跑 diag2（接近、抓取、跟踪三类），再写针对性的训练计划 | Tier 1 MPPE、AUC；Tier 2 MPPE | 诊断约 15 集 × 10 分钟 ≈ 2.5 GPU 小时（每集用时是估计，没量过）；之后的训练另算 | MPPE 第一只能靠这条：Tier 1 要修好约 3 集大的，Tier 2 约 1 集 |
| 丁 | 同一 checkpoint 导出多局、交成功的那局 | Tier 1 MP-SR、AUC | 不到 1 GPU 小时 | 规则风险（1.2），不做，除非组委会书面同意 |

## 3. 建议的顺序

1. 21:20 试点结束后先做乙与丙的诊断（合计约 4 GPU 小时，两台各一半），当晚出结果。乙的 checkpoint 有成功的就进逐条选，打包后报给用户。
2. 甲排在乙之后：乙没让 ep14、ep19 变成功，就补种子（每集 2 个，两台各 2 条，约 4.5 小时）。
3. 丙的诊断出来后另写训练计划、另审。
4. Tier 3 全量重训与本计划怎么分卡，等试点结果出来由用户定（第 7 节第 2 条）。

## 4. 判据（执行前登记）

- 乙、甲的每个新 checkpoint：按现有的评测链与导出链评 4096 世界、导出 1 个世界（kit 的做法，不改世界数、不改种子），进逐条选；选法不变
  （先比 MP-SR，再比 SP-SR，再比 AUC / 0.3780 − MPPE / 25.1706），打分门 A、B 照旧。新 CSV 只打包、不提交，提交要用户点头。
- 甲的停手：每集补完 2 个种子后，某集两个新种子的 4096 世界 MP-SR 都低于 0.3，这一集不再补（r3a 那次 0.677 可能是运气好）；
  有一个新种子的那 1 局成功，这一集也不再补。两集都停就报给用户。
- 丙：每集出接近、抓取、跟踪三类失败的占比与主要失败环节（diag2 的判法不改），只报；写训练计划之前不起训练。
- 档位隔离：Tier 2 的诊断、选择与判断只用 Tier 2 的数据；Tier 1 的结果不拿来调 Tier 2 的任何东西。
- 丁：不做。

## 5. 风险

- 1.4 的估算假设各次抽取独立，实际高估（第 0 局固定、相邻 checkpoint 相关、种子间差异大）。
- 所有行都在公榜上，按本地 1 局的分数挑 checkpoint 等于直接对着榜优化；规则说闭赛后还有 held-out 评测，这种挑法在那里不一定有用。
- 仓库还没共享给组委会账号，按规则每次提交的 commit 链接都要指向“shared with the V2D organisers' account”的仓库。
- 与 Tier 3 全量重训抢卡。

## 6. 时间（估计）

- 21:20 前后试点结束；乙与丙的诊断约 23:30 前出结果；甲若要做，10/15 凌晨起，约 05:00 出结果。

## 7. 要用户定的

1. 要不要就“同一 checkpoint 导出多局、交成功的那局”给组委会发邮件问（选项丁）。我们的建议是不问、不做，靠甲、乙。
2. 今晚之后的卡：本计划（乙、丙、甲）与 Tier 3 全量重训怎么分。
3. 每一次提交的同意；临近封榜时从全部提交里选 2 份 Final Submissions。
4. 请组织 owner 或仓库管理员把 Nvidia-V2D-Challenge 加为协作者（规则 2.9.a）。

## 8. 审查

第 1 版待独立审查（GO、GO WITH FIXES 或 NO GO）。审查提示词在本会话的 scratchpad（`review_prompt_first_place.txt`）。

## 9. 执行记录

（未开始）
