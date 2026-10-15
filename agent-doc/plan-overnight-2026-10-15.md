# 10/15 凌晨两台卡的排法（2026-10-15）

第 2 版。第 1 版经独立审查（Fable 5.1）为 GO WITH FIXES，8 条全部采纳，见第 6 节。用户 10/15 00:2x 要求今晚不让两台卡空着，看了排法后说“好的 你规划一下”。本计划只排已经登记过、审过的活，外加一处小代码改动
（`make_copy_queue.py` 的种子段）；新的训练方向（Tier 1 跟丢集的重训）等逐帧分析出来另写计划、另审。

## 1. 事实

- **现在在跑**：两台 00:30 起逐帧分析的 dump 链（`agent-doc/plan-frame-onset-2026-10-14.md`；mf4090 17 条、ml40 11 条，
  `results/frames/arm_frames_mf4090_1014.txt`、`results/frames/arm_frames_ml40_1014.txt`），估计 mf4090 约 01:50、ml40 约 01:35 结束。
- **已挂上的接续**：两台各有一个 `arm_after.sh`（md5 b631f35b）在等 dump 链结束、卡空，然后起选项甲：mf4090 的 `t1xb_s43`（ep14 seed 43，
  `t1-ep14-w2048-cap4m-r3a-s43-mf4090`）、ml40 的 `t1yb_s43`（ep19 seed 43，`t1-ep19-w2048-cap10m-r3a-s43-ml40`）。两段配置核对都过（意外键 0 个），
  起链预演 DRYRUN_OK（`results/jia/`）。队列由审过的 `make_var_queue.py --seed` 生成，与 seed 42 那条只差 run 名与种子两项（`results/jia/make_queue_*.txt`）。
- **甲登记的判据**（`agent-doc/plan-first-place-2026-10-14.md` 第 4 节）：ep14 的 s43 那条 4096 世界 MP-SR 低于 0.3、ep19 的低于 0.2，这一集不再补；
  那 1 局成功的集也不再补。10/14 用户定挑选与汇报以 4096 世界为主、两种分数都列（`agent-doc/plan-first-place-2026-10-14.md` 执行记录 20:10）。
- **Q2 要补的种子**（`agent-doc/plan-t3dyn-pilot-2026-10-14.md` 第 4 节）：ep12 的 dyn4s 减 dyn4 为 −0.562，记“平滑疑似变差”，要给两版各补一条
  seed 43、同向且差也 ≥ 0.4 才算数；没补种子时重训照规则用 best_dyn4。另一位用户的交接写 ep12 不受 dyn4 对称判据错误的影响（3e38561）。
- **生成器**：`make_copy_queue.py` 原先只有 t3pdyn、t3qdyn 两段、没有种子参数。本计划加 `t3qdyn_s43`：照抄 t3qdyn 的两条，run 名在机器名前加
  `-s43`，冒烟与正式行在变体 A 两项之前加 `reset.seed=43 training.seed=43`（与 `make_var_queue.py --seed` 的位置相同），期望表种子列写 43；源行已有
  种子覆盖就拒绝；候选导出清单抬头写“本段改种子”。测试 5 组 `ALL_OK`；原有两段重新生成与仓库里的逐字相同（`results/q2/check_queue_t3pdyn.txt`、
  `results/q2/check_queue_t3qdyn.txt`，都是 `COPY_CHECK_OK`），新段 `results/q2/check_queue_t3qdyn_s43.txt`（证明提交里的生成器复现提交里的文件的是这几份
  `--check` 记录，不是生成时的 `make_queue` 记录：那之后生成器又改过报告的写法与抬头）。
- **用时**（估计）：mf4090 上 400 万 buffer 的一条约 2 小时 15 分（ep15 best_dyn4 14:25–16:41）；ml40 上 1000 万 buffer 的 Tier 1 一条约 2 小时 30 分；
  ml40 上 400 万 buffer 的 ep12 两条共约 5 小时（t3qdyn：14:31–19:32）。

## 2. 排法

| 机器 | 现在 | 接着（已挂） | 再接着 |
|---|---|---|---|
| mf4090 | dump 链 17 条（约到 01:50） | 甲 ep14 s43（约 01:55–04:25，含评测与导出） | Tier 1 跟丢集的重训：等逐帧分析，另写计划、另审；赶不上就空着 |
| ml40 | dump 链 11 条（约到 01:35） | 甲 ep19 s43（约 01:40–04:30） | Q2 补种子：ep12 dyn4 s43、dyn4s s43（约 04:35–09:40） |

理由：甲直接对着 Tier 1 的 MP-SR（我们 19 条、FF 20 条），而且审过、队列已生成，可以最先跑。Q2 的种子是试点登记的后续，**只供参考**：试点计划第 4 节
里这个方向不论结果如何，重训都用 best_dyn4，所以这一对改变不了我们的任何决定；它回答“人体平滑是否有害”，人体平滑与另一位用户修的对称判据无关，
所以对“dyn7 要不要再加人体平滑”仍有用。ml40 后半夜没有别的现成的活。**让路**：Tier 1 跟丢集的重训计划若先审完，就在 ml40 上建
`runs/.chain-stop-t3qdyn_s43_train_ml40`（`day2_train_chain.sh` 的停链标记）：没开的那条不开，正在训的那条训完，Tier 1 的接上。Tier 1 跟丢集占 MPPE 合计 87.8%，但重训怎么做要看逐帧分析
（骨盆是在接触前还是接触中失守），所以不预排。

## 3. 做法

1. `make_copy_queue.py` 的改动与测试、生成的 `t3qdyn_s43` 队列已提交（ba3f513），按审查意见的修改另提交。
2. 下面三步**必须按顺序**，前一步不过就停（arm_after 第 1 步记下这一段四个文件的 md5、第 6 步再比；文件还没推到就起 arm_after，两次 md5 对不上，它会停）：
   - 推文件：`V2D_ENV=ml40 scripts/dev/record q2/push_t3qdyn_s43_ml40 scripts/dev/push-new-files stages/policy/queues/ml40_t3qdyn_s43.expect.tsv
     stages/policy/queues/ml40_t3qdyn_s43_smoke.txt stages/policy/queues/ml40_t3qdyn_s43.txt stages/evaluate/exports/cand_t3_t3qdyn_s43_ml40.tsv`，
     要以 `PUSH_OK` 结束（ml40 上有链在跑，`scripts/dev/remote` 会拒绝同步；`push-new-files` 只加已提交的新文件、不碰 `.v2d-source-commit`）。
   - 配置展开核对：`stages/policy/fc_config_check.sh stages/policy/queues/ml40_t3qdyn_s43_smoke.txt stages/policy/queues/ml40_t3qdyn_s43.txt`，
     要“配置核对通过”、意外 0 个（不占 GPU，只写 `runs/cfgcheck/` 与空的 `.lock`）。
   - 挂接续：照 `results/jia/arm_after_launch_t1yb_s43_ml40.txt` 的写法（record 包住、已有日志就不起、`setsid nohup`），环境加 `V2D_AFTER_MAX_POLLS=1080`：
     `bash runs/tools/arm_after.sh t3qdyn_s43 runs/logs/t1yb_s43_train_ml40.log runs/logs/t1yb_s43_eval_ml40.log runs/logs/cand_t1_t1yb_s43_ml40.log 1`。
     它等到 t1yb_s43 的三条链全部做完（训练 1 条、评测 ≥ 1、导出 1 条）、没有长链标记、卡空，才起 Q2 的种子；t1yb_s43 有任何一条没做完就不起（arm_after 的第 5 步）。
     日志还不存在时它照样等（`tail` 读不到就当没结束）。
3. 生成器本身的改动不推（服务器起链用不到它）。
4. 结果：甲的两条按登记的判据读，两种分数都列（4096 世界为主）；Q2 按试点计划第 4 节读，写进试点计划的执行记录。

## 4. 判据（执行前登记，不改）

- 甲：照 `plan-first-place-2026-10-14.md` 第 4 节（上面第 1 节已抄），另按 10/14 的决定把导出那 1 局与 4096 世界的四项并列；本计划不改甲的任何判据。
- Q2：照 `plan-t3dyn-pilot-2026-10-14.md` 第 4 节，s43 这一对的 dyn4s 减 dyn4 ≤ −0.4，“平滑疑似变差”才算数。本计划新登记：|差| < 0.4 或方向相反，
  记“两种子不一致，看不出差别”；s43 的 dyn4 ≥ 0.6 时记“不是瓶颈”。不论哪种，重训照试点计划用 best_dyn4（这一对只供参考，见第 2 节）。
- 起链：每段 `arm_var_chain.sh` 自己的预演与核对（GPU、来历、磁盘、配置）都过才起；arm_after 第 5、6 步不过就不起。
- 停：任何一步不满足就停在那一步，查原因，不改判据、不改配置重跑。

## 5. 风险

- arm_after 等不到上一段做完（比如 ep19 训练失败）就不起 Q2，ml40 会空着；这是有意的，失败要先查。
- 链跑的时候两台都不能同步代码；分析脚本若要修，按约定复制到 `runs/tools/` 再跑，记 md5。
- Q2 的两条在 ml40 上、s42 那一对也在 ml40 上，同机比较；best_hm 的 ep12 基线在 mf4090 上（试点计划第 5 节已记）。
- 估计的时间可能偏差半小时以上；SOP 07:00 的定时更新照常。
- 第二个 arm_after 等上一段最多 `V2D_AFTER_MAX_POLLS` 次 × 60 秒：默认 720 次（约到 13:00），按审查意见设 1080 次，约到 19:00 MDT；只有 GPU 被长时间占住才会碰到。

## 6. 审查

第 1 版：Fable 5.1，GO WITH FIXES。核过没问题的：新段只改 run 名、种子两项、种子列与抬头；种子的位置与 `make_var_queue.py --seed` 相同；
`arm_var_chain.sh`、`precheck_expect.sh`、`day2_train_chain.sh`、`fc_config_check.sh` 都接受这段名与 run 名；arm_after 能等还不存在的日志，最后一个参数 1 对；
甲的判据照抄未改；`push-new-files` 不碰在跑的链。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MINOR | 第 3 节的先后顺序是承重的却没写明，命令也没写全 | 采纳：三条命令按顺序写全，标“必须按顺序” |
| 2 | MINOR | Q2 这一对改变不了任何登记的决定，后半夜占着 ml40 | 采纳：第 2 节写明只供参考；登记让路办法（停链标记） |
| 3 | MINOR | Q2 的读法符号含糊，部分是新登记的 | 采纳：写成 ≤ −0.4；不一致与“不是瓶颈”两条标“本计划新登记” |
| 4 | NIT | 第二个 arm_after 默认只等 12 小时 | 采纳：设 `V2D_AFTER_MAX_POLLS=1080`，写进第 5 节 |
| 5 | NIT | “原有两段逐字相同”没有记录；make 记录的生成器 md5 与提交里的不同 | 采纳：两段 `--check` 经 record 落盘并引用；写明以 `--check` 记录为准 |
| 6 | NIT | 另两种拒绝没有测试 | 采纳：补“变体 A 位置项不是恰好一个”“源种子列不是 42”两种 |
| 7 | NIT | 候选清单抬头没写“本段改种子” | 采纳：推之前补上、重新生成、重核、提交 |
| 8 | NIT | 第 3 节两处措辞（已提交却写“审查之后”；配置核对不是只读） | 采纳：改写 |

## 7. 执行记录

- 00:30 两台起 dump 链；00:31 两台挂上甲的 arm_after（见第 1 节）。
- 00:4x 审查（第 6 节）后按意见修改，提交 a6d0200。00:5x ml40 上按第 3 节的顺序：推 4 个文件 `PUSH_OK`、md5 一致、远端来历仍是 6bfb784
  （`results/q2/push_t3qdyn_s43_ml40.txt`）；配置核对通过、意外 0 个（`results/q2/cfgcheck_t3qdyn_s43_ml40.txt`）；挂上第二个 arm_after，
  `V2D_AFTER_MAX_POLLS=1080`，日志里记下的队列 md5 与推上去的相同（`results/q2/arm_after_launch_t3qdyn_s43_ml40.txt`）。
