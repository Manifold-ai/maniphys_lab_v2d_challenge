# 看榜与 SOP 的定时安排（10/19 起，到封榜为止）

2026-10-19 12:4x MDT 写定，分支 track2/p1-training。要求（rxzhou 10/19）：每 3 小时看一次 Kaggle 榜并据此调整策略；SOP 照旧每天早晚各更新一次；定时一直排到比赛结束。

## 0. 事实

1. **调度器按 MDT 解析 cron。** Claude 进程 10/6 在 Denver 时区下启动，系统时区 10/16 22:18 改成 America/New_York（`/etc/localtime`），shell 里的 `date` 显示 EDT，
   调度器仍按 MDT 触发：`10 23 17 10 *` 在 23:10 MDT 触发，`33 9 18 10 *` 在 09:33 MDT，`12 11 19 10 *` 在 11:12 MDT（对话记录里的触发时间，UTC 换算）。
   10/17 以来按 EDT 换算挂的单次检查因此都晚了 2 小时。从现在起 cron 一律写 MDT。
2. **循环任务 7 天后自动过期。** 10/11 建的 SOP 任务（`0 7,18 * * *`）最后一次在 07:30 MDT 10/18 触发，此后没有再触发：10/18 18:00 与 10/19 07:00 的 SOP 更新没有做。
   这类任务也只活在当前会话里，会话退出就没了。
3. **SOP 的触发时刻相隔 11 小时**（07:00 与 18:00），不能同时落在一个 3 小时的网格上。此前 SOP 实际在整点后约 30 分钟触发。
4. **榜在这次安排之前就变了**（`results/board/diff_1019_1236.txt`，对比 10/18 20:57 的快照）：另一支队（Xueyi Wang (FF)）10/19 05:50 UTC 交了 Tier 1、17:49 UTC 交了 Tier 3。
   读法 B 名次和：FF 24，我们 25（同分按 Kaggle 规则）或 27（同分按官网规则）；读法 A：FF 5，我们 7。

## 1. 安排

| 任务 | 时刻（MDT） | 内容 |
|---|---|---|
| 看榜 | 每天 02:10、05:10、08:10、11:10、14:10、17:10、20:10、23:10 | `tools/board_watch.sh` 取 12 个榜的快照并与上一份比较；查两台服务器的卡；榜变了就按第 3 节调整 |
| SOP 更新 | 每天 07:00、12:00、17:00、23:00（10/20 起；此前 07:00、18:00） | 先跑 `tools/board_watch.sh` 取新快照，再更新 SOP 页面（规则照旧） |
| 结果检查 | 按各段训练的预计出结果时刻挂单次检查 | 照各计划的判据判读 |
| 续期 | 10/26 06:20、11/02 06:20 | 按同样的 cron 与提示词重建看榜、SOP 两个循环任务，删掉旧的 |
| 收尾 | 11/04 15:20（封榜 15:00 MDT，即 17:00 EST） | 记终榜快照，最后更新一次 SOP，删掉两个循环任务 |

看榜的网格离 SOP 的触发时刻至少 40 分钟，两者不会排队撞在一起；SOP 自己取快照，所以不靠网格对齐也能拿到最新的榜。分钟数避开整点与半点。

## 2. 比较规则（`stages/evaluate/board_diff.py`，测试 `stages/evaluate/test_board_diff.py`）

- 逐榜列出分数变化、重新提交（分数没变、提交时间变了）、新进来与不见了的队。10/18 20:57 那份快照每榜只取了前 10 行，第一次比较里 Tier 1 的“新进”有一部分是这个原因；
  `tools/board_snapshot.sh` 不再截行。
- 我们在 12 个榜的名次（基线不计名次）以及与第 1 名或第 2 名的差距；两种同分规则（Kaggle 先提交者在前、官网队名字母序）下第一的榜各有几个。
- 读法 B（12 个榜名次相加，缺榜按那个榜最后一名再加 1）与读法 A（三档平均后 4 个名次相加，只算三档都交了的队），两种同分规则都算，与 `track2_rank_sum.py` 一致。
- ALERT：我们在某个榜的名次变差（任一同分规则）；任一读法、任一同分规则下我们的总名次变差。
- 取不到任何一个榜（没有网、Kaggle 出错、空表）就整次失败，不拿半截快照比较，也不把“取不到”当成“没变”。

## 3. 每次看榜之后

1. 没有变化、两台的卡都在跑计划内的活或另一位用户的活：一两句话回报，不为此单独提交。
2. 榜变了：说清谁在哪个榜动了、各榜差距、两种读法的名次和；判断策略要不要变（哪个榜最快能拿回来、用哪些 run、占哪一次提交额度），把决定和理由写进当前计划的执行记录或另写短计划。
3. 规则不变：新的 GPU 工作先写短计划、交独立复核，GO 或 GO WITH FIXES 且改完才起；Tier 2 按已登记的判据，有把握拿某个榜第一才交；Tier 1、Tier 3 每次提交都要 rxzhou 点头；
   不停别人的进程；Tier 2、Tier 3 的方法里不用 Tier 1 的数。
4. 有卡空着、又没有复核过的计划在等它：写下一步的短计划，优先补差距最小、最快能拿回的榜，照第 3 条走。

## 执行记录

- 12:36 MDT：第一次快照与比较（`results/board/lb_1019_1236.txt`、`results/board/diff_1019_1236.txt`），结果见事实 4；ALERT 10 条（Tier 1 AUC 第 2 → 3、SP-SR 第 1 → 2，
  Tier 3 MPPE 第 2 → 3，三种总名次由第 1 变第 2 等）。`track2_rank_sum.py` 对同一份快照给出相同的名次和。

- 14:38 MDT：第二次看榜（`results/board/diff_1019_1438.txt`；14:10 的定时晚触发）。FF 的 Tier 3 MPPE 49.61 → 48.39，拿下这个榜的第一；wte09fl 的 Tier 1、Tier 2 都涨了，
  仍远在我们后面。我们 12 个榜的名次不变。读法 B：Kaggle 同分规则 FF 23、我们 25，官网规则 FF 23、我们 27；读法 A：FF 5、我们 7。
  决定：拿下 FF 紧挨在前面、差距最小的 Tier 2 AUC（差 0.00417），另写 `agent-doc/plan-t2auc-2026-10-19.md`（不用 GPU），复核后再交。
  t2st 没用（执行记录见那份计划），mf4090 13:44 起空着；更早的 checkpoint 要先改队列生成器，另写计划。ml40 的卡上还有另一位用户的进程。

- 16:1x MDT：Claude 进程 18:13 EDT 重启，调度器改按纽约时间解析 cron（新挂的任务报的下次触发时刻证实了这一点）；照旧的写法会让 SOP 提前 2 小时、收尾任务在封榜前 1 小时 40 分触发。全部按纽约时间重建，触发时刻不变：看榜 `10 1,4,7,10,13,16,19,22 * * *`（= Denver 02:10、05:10 … 23:10），SOP `0 9,20 * * *`（= 07:00、18:00），续期 10/26、11/02 的 08:20（纽约），收尾 11/04 17:20 EST。续期任务带两份提示词全文；下面附录是 12:4x 的旧版，只作参考。进程再重启就要重新核时区。
- 10/20 00:3x MDT：SOP 更新改为每天 07:00、12:00、17:00、23:00 MDT（rxzhou 10/20：“现在更新时间改为MDT早上七点晚上五点晚上十一点以及中午十二点更新SOP”）。调度器给这个任务固定加约 30 分钟的延迟，所以 cron 写成纽约时间 `31 0,8,13,18 * * *`，CronCreate 报的下次触发是 09:01 纽约（= 07:01 MDT）。两个续期任务（10/26、11/02 08:20 纽约）按新的 SOP 提示词与 cron 重建，并要求续期时核对报出的触发时刻；去掉了“shell 的 date 应显示纽约时间”这一条（shell 显示的是 Denver 时间）。看榜任务的 23:10 与 SOP 的 23:00 相隔约 10–40 分钟，两者都自己取快照，排队也不影响结果。
- 10/20 02:40 MDT（`results/board/diff_1020_0240.txt`）：DAP 在 Tier 1 交了一次：AUC 0.48807 → 0.60030（超过我们的 0.58258 与 FF 的 0.595），SP-SR 0.66666 → 0.80000（仍低于我们的 0.83333），MP-SR、MPPE 没变。我们 Tier 1 AUC 第 3 → 第 4（两种同分规则都是）；读法 B：FF 21、我们 26（Kaggle 规则）/ FF 21、我们 28（官网规则）；读法 A 不变（FF 5、我们 7）。决定：按 `agent-doc/strategy-2026-10-19.md` 第 1 节不交——夺回第 3 不是“遥遥领先拿第一”，且 Tier 1 每次要 rxzhou 点头。两台卡都在跑登记过的计划（mf4090 t3pg4，ml40 t2fc），不改。待定：只为少丢一个名次（不拿第一）的提交要不要另定一档规矩（rxzhou 定）。
- 10/20 11:40 MDT（`results/board/diff_1020_1140.txt`）：新队 Team OPS 在 12 个榜里交了 11 个、Javier Medel, MSc. 交了 Tier 1，分数都在 maniphys.ai 之后；Team OPS 的 Tier 3 SP-SR 0.16666 排到第 2（maniphys.ai 0.26666 仍第一），把 FF 挤到第 3；Open4D 的 Tier 3 MPPE 86.66 → 79.79。maniphys.ai 各榜名次不变。读法 B：FF 22、maniphys.ai 26（Kaggle 规则）/ 23、28（官网规则）；读法 A 不变（5、7）。决定：不改，不交；两台卡在跑登记过的计划（mf4090 t3pg4，ml40 t2ho）。
- 10/20 14:41 MDT（`results/board/diff_1020_1441.txt`）：新队 Chivatam 交了 Tier 1 四个榜，都在 maniphys.ai 之后；名次和不变（FF 22、maniphys.ai 26，Kaggle 规则）。不改、不交；两台卡在跑登记过的计划（mf4090 t3pg4，ml40 t1ho）。

- 10/20 20:44 MDT（`results/board/diff_1020_2044.txt`）：DAP 在 Tier 1 交了一次（10/20 19:00 MDT）：AUC 0.60030 → 0.73467、SP-SR 0.80000 → 0.83333（与 maniphys.ai 同分）、
  MP-SR 0.43333 → 0.76666（超过 maniphys.ai 的 0.70000）、MPPE 12.65831 → 11.99700（仍在 maniphys.ai 的 11.86661 之后，差 0.13 cm）。新队 nima arki（Tier 1、Tier 2）与
  Izus_systems（Tier 1）都在 maniphys.ai 之后。maniphys.ai 名次：Tier 1 MP-SR 第 2 → 第 3（两种同分规则）；Tier 1 SP-SR 按 Kaggle 规则仍第 2（提交更早），按官网规则第 2 → 第 3（字母序）。
  读法 B：Kaggle 规则 FF 22、maniphys.ai 27（原 26）；官网规则 FF 23、maniphys.ai 30（原 28）。读法 A 两种规则都是 FF 5、maniphys.ai 7，不变。
  决定：不改、不交。Tier 1 MP-SR 要比 FF（25/30）领先 2 集才交，现在 21/30；守第 2 不在提交规矩之内（`agent-doc/strategy-2026-10-19.md` 第 1 节）。Tier 1 MPPE 的第 2 只领先 DAP 0.13 cm，
  记为风险，不为守它提交。两台卡都在跑登记过的计划（ml40 t2tm，`agent-doc/plan-t2term-2026-10-20.md`；mf4090 t3pg4），不另写计划。

- 10/20 23:01 MDT（SOP 更新时看的，`results/board/diff_1020_2301.txt`）：新队 NVSimranPatil 只交了 Tier 2（10/20 21:12 MDT）：SP-SR 0.93333、MP-SR 0.76666、MPPE 2.76526、AUC 0.49505。
  maniphys.ai 的 Tier 2 SP-SR 第 1 → 第 2、MP-SR 第 2 → 第 3、MPPE 第 2 → 第 3，AUC 仍第 2。FF 交了 Tier 3：SP-SR 0.13333 → 0.16666、MPPE 46.649 → 45.986。新队 Rohit Pardeshi（Tier 1）在后面。
  读法 B：Kaggle 规则 FF 26、maniphys.ai 30；官网规则 FF 26、maniphys.ai 33；读法 A 5 比 7。第一的榜只剩 Tier 3 SP-SR。
  决定：不交。NVSimranPatil 的 Tier 2 SP-SR、MP-SR、MPPE 离 maniphys.ai 的期望很远（0.200、0.233、12.6 cm），这三个榜的第一近期拿不回；它没交 Tier 1、Tier 3，名次和上它不是对手，
  名次和的对手仍是 FF（差 4）。mf4090 22:46 起空着（t3pg4 链结束），下一项工作另写计划。

- 10/20 23:50 MDT（`results/board/diff_1020_2350.txt`）：只有新队 Andrew Norris 进了 Tier 1 AUC（0.00000），在 maniphys.ai 之后；各榜名次不变。读法 B：Kaggle 规则 FF 26、
  maniphys.ai 30，官网规则 26、33；读法 A 5 比 7。不改、不交。ml40 在训 t2tm（`agent-doc/plan-t2term-2026-10-20.md`）；mf4090 的卡空着、CPU 在做 gb5 的重定向，
  复核过的 `agent-doc/plan-t3g5-2026-10-21.md`（第 2 版）重定向一完就起，不另写计划。

- 10/21 04:31 MDT（`results/board/diff_1021_0431.txt`；02:10 那次因额度用完没跑）：Chivatam 与 Rohit Pardeshi 在 Tier 1 各交了一次（Chivatam AUC 0.42、SP-SR 0.600、MP-SR 0.133、
  MPPE 16.95；Rohit Pardeshi MPPE 44.56），都在 maniphys.ai 之后；各榜名次不变。读法 B：Kaggle 规则 FF 26、maniphys.ai 30，官网规则 26、33；读法 A 5 比 7。不改、不交。
  两台卡在训 `agent-doc/plan-t3g5-2026-10-21.md` 的 A 段（mf4090 ep5 03:39 训完、在训 ep10；ml40 ep3 03:25 训完、在训 ep12）。

- 10/21 06:12 MDT（`results/board/diff_1021_0612.txt`）：没有变化。
- 10/21 07:01 MDT（SOP 更新时看的，`results/board/diff_1021_0701.txt`）：新队 solidSF.com 只交了 Tier 1 AUC（0.99998，10/21 06:13 MDT），Andrew Norris（0.00000）不在榜上了。
  maniphys.ai 的 Tier 1 AUC 第 4 → 第 5，FF 也后移一名，两队之间不变。读法 B：Kaggle 规则 FF 27、maniphys.ai 31，官网规则 27、34；读法 A 5 比 7。
  不改、不交：这个榜第一名 0.99998、第二名 0.96908，maniphys.ai 0.58258，差 0.39 以上，现有路线追不上；名次和的变化只来自这一个榜，FF 同样后移。
  两台卡在训 `agent-doc/plan-t3g5-2026-10-21.md` 的 A 段（mf4090 ep5、ep10 训完、在训 ep15；ml40 ep3、ep12 训完、在训 ep16）。
- 10/21 08:40 MDT（`results/board/diff_1021_0840.txt`）：DAP 在 Tier 2 四个榜各交了一次（07:25–07:31 MDT）：AUC 0.44824、SP-SR 0.53333、MP-SR 0.33333、MPPE 25.69486，
  四项都在 maniphys.ai 之后；各榜名次不变。读法 B：Kaggle 规则 FF 27、maniphys.ai 31，官网规则 27、34；读法 A 5 比 7；DAP 的名次和升到第 3（60、59）。不改、不交。
  两台卡在跑 t3g5：mf4090 训 A 段最后一集 ep27（26%，约 10:15 训完），ml40 的 B 段在冒烟最后一集 ep25。

## 附：两个循环任务的提示词（10/19 12:4x MDT 建；改了要同时改续期任务）

这里另一位成员的名字写成 <另一位成员>，完整原文在 10/26、11/02 两个续期任务里。

看榜（`10 2,5,8,11,14,17,20,23 * * *`）：

```text
V2D board watch. User request 10/19: "定时每天每间隔三小时查看一次kaggle榜单调整策略", "定时一直截止到比赛结束". This job runs every 3 hours until the leaderboard freezes at 15:00 Denver time 11/04 (17:00 EST). The arrangement and the rules are in agent-doc/board-watch-2026-10-19.md. Cron times are Denver time (MDT, MST from 11/01) because the scheduler keeps the Denver zone. The shell clock shows New York time. The servers log CST. Work in /Users/rongxuanzhou/V2D on branch track2/p1-training. Reply to the user in colloquial Chinese. Give all times in Denver time.
1. Run bash tools/board_watch.sh. It records a snapshot of the 12 Kaggle boards and a comparison with the previous snapshot under results/board/. If it fails (no network or a Kaggle error), report that in one line and stop.
2. Take a status snapshot of each server: scripts/dev/record ops/status_<machine>_<MMDD>_<HHMM> ssh <machine> 'bash -s <machine>' < tools/status_remote.sh.
3. If the output says BOARD_NO_CHANGE and both GPUs run planned work or work of another user, reply in one or two lines. Do not commit only for this.
4. If boards changed, report which team moved on which board, our gap on each board, and the rank sums for readings A and B under both tie rules. Decide if the strategy must change: which boards we can regain soonest, with which runs, and with which submission slot. Write the decision and the reasons into the execution record of the active plan, or into a new short plan.
5. If a GPU is idle and no reviewed plan waits for it, write a short plan for its next work. Give priority to the smallest board gaps that we can close soonest.
6. Keep the standing rules. New GPU work needs a short plan and an independent Fable review. Start it only after GO, or after GO WITH FIXES with the fixes in. Upload Tier 2 only when the registered criteria give confidence of first place on a board. Each Tier 1 or Tier 3 upload needs the explicit consent of the user, so ask. Never stop a process of another user. Do not use Tier 1 numbers in Tier 2 or Tier 3 methods.
7. When boards changed or new plans or records exist, run tools/name_leak_check.sh on the new files (V2D_EXTRA_NAMES="<另一位成员>", under bash -c). Then commit and push.
```

SOP 更新（`0 7,18 * * *`）：

```text
Scheduled task the user asked for ("现在定时每天早上7点晚上6点更新一次SOP网站", 10/9 15:00 MDT; 10/19: "定时一直截止到比赛结束"): update the SOP site now with the latest state. Report all times in Denver time (MDT, UTC-6; MST, UTC-7, from 11/01). Server logs use CST (UTC+8). Cron times are Denver time. The shell clock shows New York time.
Page rule (user, 10/9 20:50 MDT, "关于sop中的一些ai agent使用细节不用透露 团队leader会查看"): the team leader reads the page. The page must not show AI-agent process details. Do not write jev scores, claim records or control questions on the page. Do not write model reviews (Fable, Opus, GO WITH FIXES, MAJOR). Do not write 用户 or "the user", and do not quote chat instructions. Write an open decision as 待定 / "to be decided". Write a past decision with its date and no subject.
Person rule (user, 10/10 21:05 MDT, "sop内容上我是rxzhou 另外一个人是<另一位成员> 第三人称撰写进度"): on the page, write progress in the third person. rxzhou is the page owner and runs this work (training, retargeting, evaluation, submission). <另一位成员> is the other team member (the Tier 3 CARI4D reconstruction on ml40). Do not write 我们, 同组成员, 同事, "we", "our" or "the teammate" on the page. This rule is for the page only: records in results/, agent-doc/ files and commit messages still write <其他用户> or "the teammate" and never the teammate's name or user name.
1. Check both machines read-only. Record a snapshot with scripts/dev/record: running chains, GPU state, mf4090 disk, and the Tier 3 queue on ml40 (tools/status_remote.sh, tools/gpu_procs_remote.sh, tools/t3_queue_remote.sh). Run bash tools/board_watch.sh for a fresh snapshot of the 12 Kaggle boards. Check that no record contains another user's name. Do not sync, stop or start any chain.
2. Add every result that finished since the last SOP update to docs/site/v2d-track2.html, in both languages. Find them in the execution records of the plans that changed since the last SOP update (git log). Update the leaderboard part with the newest snapshot under results/board/: the place on each board, the gaps, and the rank sums for readings A and B. Describe running tasks honestly. Do not invent results. Mark every open decision as 待定 / "to be decided".
3. If a chain ended since the last update, pull its results and write the health record that its plan registers. Do not arm a new chain in this task. Tell the user the next step instead.
4. Run jev on the new claims, with controls. Keep the jev records in results/ only, not on the page. Before you publish, search the page text for jev, claim, Fable, Opus, review, 审查, 用户, user, coding agent, 原文, 我们, 同组成员, teammate, we and our. Fix every hit that the page rule or the person rule covers. Commit, push, and republish to https://claude.ai/artifact/Y3bxcJt4oMMMrBKAr4fkhj. Pass new media files through files, and only new ones.
5. Report to the user in Chinese, briefly.
```

- 10/21 13:40 MDT（`results/board/diff_1021_1340.txt`；不计 solidSF.com 的比较 `results/board/diff_1021_1340_ex_solidSF.txt`，`board_diff.py` 新加 `--exclude`）：
  solidSF.com 在 13:14–13:25 MDT 交了其余 10 个榜（Tier 1 MP-SR 不在第一页）：三档 AUC 都是 0.99998，SP-SR、MP-SR 1.00000，MPPE Tier 1 与 Tier 3 都是 0.07244、Tier 2 0.07628。
  NVSimranPatil 交了 Tier 1（11:13 MDT）：AUC 0.87916、SP-SR 1.00000、MP-SR 0.93333、MPPE 0.98418；Haoran Zhang233 交了 Tier 1（13:17 MDT）：AUC 0.82959、SP-SR 0.90000、MP-SR 0.83333；
  MBZUAI-RCL Group 交了 Tier 1 MPPE 9.43744；nima arki 的 Tier 1、Tier 2 涨了，仍在 maniphys.ai 之后（Tier 1 AUC 0.57840 只差 0.004）。
  计 solidSF.com：maniphys.ai 12 个榜都后移，没有第一的榜；读法 B Kaggle 规则 solidSF.com 31、FF 43、NVSimranPatil 49、maniphys.ai 50（第 4），官网规则第 4（53）；读法 A FF 8、maniphys.ai 10。
  不计 solidSF.com：Tier 1 第 6/4/5/5，Tier 2 第 2/2/3/3，Tier 3 第 3/1/2/3（AUC/SP-SR/MP-SR/MPPE）；读法 B Kaggle 规则 FF 32、NVSimranPatil 39、maniphys.ai 39（同分，提交更早者在前），官网规则 FF 34、NVSimranPatil 39、maniphys.ai 42；读法 A FF 5、maniphys.ai 7。
  解读（未核实）：solidSF.com 的 Tier 3 MPPE 与 Tier 1 逐位相同（0.07244），没有标定的 Tier 3 要做到这一点，看来用了 Tier 1 第 0 帧以外的数据；按 10/21 官方答复，Tier 3 只许用 Tier 1 第 0 帧算对齐。
  毫米级的 MPPE 也不像物理仿真里的策略 rollout。组委会封榜后用留出数据评，这样的提交能不能留在榜上要看组委会。要不要写信问组委会，由 rxzhou 决定。
  NVSimranPatil 的 Tier 1 MPPE 0.98 cm、Tier 2 2.77 cm，SP-SR 1.00 和 0.93，说明它几乎没有失败的集。maniphys.ai 的 MPPE 主要亏在少数失败集（Tier 2 的 ep25、ep4、ep28 约 290 cm），
  t2mtr 攻的正是这几集；即使三集都降到 3 cm 左右，按策略第 2 节的约 290 cm 粗算，Tier 2 MPPE 也只到约 6 cm，追不上 2.77。
  决定：不交（没有榜满足 `agent-doc/strategy-2026-10-19.md` 第 1 节的领先余量）。两台卡都在跑复核过的计划（mf4090 t2mtr ep25 68%，ml40 t3qg5b ep2 4%），不改。
  离第一最近的是 Tier 2 AUC（FF 0.51796，差 0.00417，余量要 0.010）和 Tier 3（对齐后的 CSV 已打包，等 rxzhou 决定是否上传，最早的名额 10/22 16:14 MDT）。
  NVSimranPatil 还没交 Tier 3，交了就会在名次和上超过 maniphys.ai。按“失败集决定 MPPE 与 SR”重排算力的策略改动，等 t2mtr ep25 读数（约 15:00 MDT）后另写计划。
- 10/21 14:3x MDT：SOP 页面临时改发到当前组织下的新页面 https://claude.ai/artifact/4D4PjMQTqsirvJX97CZfvh（14:01 版已发，私有，要 rxzhou 从 Share 菜单给组长开权限）。
  原页面 Y3bxcJt4oMMMrBKAr4fkhj 在 rxzhou 的另一个组织下，那个账号暂时没有额度，登录不了（rxzhou 10/21：“那个账号暂时没有额度了无法使用”）。SOP 任务重建为 924931c9（cron 不变 `31 0,8,13,18 * * *`），
  提示词改为发到新页面，发完再跑 `tools/site_preview.sh` 留一份本机预览；10/26、11/02 的续期任务提示词里仍是旧链接，续期时改用新链接，等 rxzhou 说换回再换。

- 10/21 16:40 MDT（`results/board/diff_1021_1640.txt`）：**5 个队从 12 个榜上全部消失**：solidSF.com、NVSimranPatil、Kelly To the H、Vincent_WANG_541、Vi Nguyễn Văn（Izus_systems 回到 Tier 1 AUC）。
  核过不是抓榜的问题：各榜队数 Tier 1 20 → 16、Tier 2 13 → 10、Tier 3 8 → 6，快照里没有翻页标记。原因没有核实：组委会的 GitHub 10/19–10/20 只改了榜的排序与同分、FAQ PDF、网页；
  Kaggle 讨论区要登录看不到；官网榜单的文字里没有队名。读法（推测，未核实）：被拿掉的是满分、近满分与“物体不动”（Kelly、Vincent 两队 Tier 1 AUC 都是 0.26633、MPPE 都是 49.12326）的提交。
  maniphys.ai：Tier 1 第 4/3/4/4，Tier 2 第 2/**1**/2/2，Tier 3 第 2/**1**/2/2（AUC/SP-SR/MP-SR/MPPE）；第一的榜 2 个（Tier 2 SP-SR、Tier 3 SP-SR）。
  读法 B：Kaggle 规则 FF 22、maniphys.ai 29（第 2）、DAP 57；官网规则 FF 24、maniphys.ai 31；读法 A：FF 5、maniphys.ai 7。
  差距（对 FF）：Tier 2 AUC 0.00417、MP-SR 2 集、MPPE 1.62 cm；Tier 3 AUC 0.0496、MPPE 9.00 cm，Tier 3 MP-SR 差 Open4D 1 集；Tier 1 AUC 差 MBZUAI-RCL 0.247。
  **决定**：
  1. 站立保底（`agent-doc/plan-t3static-2026-10-21.md`）有被判无效的风险：被拿掉的队里有交“物体不动”的（推测）。试点照跑（只评测、导出，不上传），但站立保底在问清楚之前不进任何要上传的清单；
     要不要写信问组委会（“机器人原地站、不去碰物体的策略是否有效”“这几队为什么被拿掉”）由 rxzhou 定。
  2. Tier 3 先考虑只对齐、不保底的 t3m1022aa（只用官方 10/21 答复允许的 Tier 1 第 0 帧）：差 FF 的 AUC 0.05、MPPE 9 cm 有一部分是世界系偏差，对齐不重训就能去掉。上传要 rxzhou 点头，最早 10/22 16:14 MDT。
  3. Tier 2 MPPE 差 FF 1.62 cm：ep25、ep28 换“不动”能降约 2.47 cm（领先 0.85 cm，不够 1.0 cm 的余量），而且同样是保底，先不做。
  两台卡：mf4090 在跑 t3static 试点（16:38 起），ml40 在训 t3g5 B 段 ep4（47%）。
- 10/21 19:03 MDT（SOP 更新时看的，`results/board/diff_1021_1903.txt`）：nima arki 交了 Tier 1、Tier 2（17:40 MDT）：Tier 1 AUC 0.72140、SP-SR 0.83333、MP-SR 0.73333、MPPE 7.47978；Tier 2 MPPE 10.84276（拿到第一）、MP-SR 0.30000。
  Chivatam 的 Tier 1 也涨了，仍在后面。maniphys.ai：Tier 1 第 5/3/5/5，Tier 2 第 2/1/2/3，Tier 3 第 2/1/2/2；读法 B：Kaggle 规则 FF 25、maniphys.ai 33，官网规则 26、35；读法 A 5 比 7。
  不交：Tier 2 MPPE 差 nima arki 4.48 cm，现有候选追不上；mf4090 空着，下一项（Tier 3 gb5 B 段的接续或 Tier 2 VOC 课程）待写计划。

- 10/26 08:4x MDT（`results/board/diff_1026_*.txt`）：10/21 19:49 之后这个会话离线，看榜与 SOP 定时任务都没有跑；两台卡分别从 10/21 17:08（mf4090）、22:40（ml40，t3qg5b 训评导出完）起空着。
  这几天别队大量提交：NVSimranPatil 回到榜上（Tier 1 近满分，Tier 2 SR 与 MPPE 领先），nima arki 交了 Tier 3 并拿下 Tier 3 四个榜，MBZUAI-RCL、Chivatam、Izus_systems 等 Tier 1 大涨。
  maniphys.ai 没有第一的榜；读法 B 第 4（Kaggle 规则 59、官网规则 61），读法 A 第 4。ml40 B 段读数：6 集里 ep23 跟上，其余仍跟丢（`results/ml40/t3g5/eval_t3qg5b_ml40.txt`）。
  不交、不起链：先向 rxzhou 报告，等定提交规矩与下一步的 GPU 工作。
- 10/26 13:20 MDT（`results/board/diff_1026_1320.txt`）：只有 wte09fl 在 Tier 1 重新提交，AUC、MPPE 小幅变好，仍在我们后面；我们 12 个榜名次不变，读法 B 59 / 61、读法 A 14 / 14，都是第 4。策略不变。
  ml40 在训 t3s43（ep5 正式训练 94%，之后 ep10、3、14，预计 21:00 MDT 前后训评导出完）；mf4090 空着，等 trajopt E 段（训练里按比例从第 0 帧起跑）的计划与复核。
- 10/26 13:33 MDT：交了 Tier 3 t3m1022aa（rxzhou 同意），四项全涨（`results/submission/submit_t3_t3m1022aa.txt`，执行记录在 `plan-t3align-2026-10-21.md`）。Tier 3 离 nima arki：AUC 差 0.10、SP-SR 差 2 集、MP-SR 同分、MPPE 差 7.6 cm。读法 B 57 / 57，读法 A 13，仍第 4。
- 10/26 19:01 MDT（`results/board/diff_1026_1901.txt`）：NVSimranPatil 从 12 个榜上全部不见了；我们没有新提交，名次因此前移：读法 B 50 / 50（Kaggle / 官网规则）、读法 A 9 / 9，都升到第 3（FF、nima arki 在前）。Tier 2 SP-SR 升到第 2（差 MBZUAI-RCL Group 2 集），Tier 2 MPPE 第 4（差 nima arki 4.5 cm）。它是被撤还是暂时不显示看不出来，回榜的话名次会退回去。t2ft2 18:51 结束，门不过，不推广、不交。
- 10/26 22:21 MDT（`results/board/diff_1026_2221.txt`）：steven kerman 新进 Tier 1 四个榜、Open4D 重交 Tier 3（只 MPPE 小幅变好），都在我们后面；我们 12 个榜名次不变，读法 B 50 / 50、读法 A 9 / 9，第 3。
  ml40 的 t3s43 20:41 训评导出完：ep5、10、14 按 S1 记“换”，ep3 不换（执行记录见 `plan-t3s43-2026-10-26.md`）。
  策略：差距最小的是 Tier 3 SP-SR（差 nima arki 2 集）与 MP-SR（同分）。最快能拿回来的是 Tier 3：下一版清单可把 ep5、10、14（t3s43）与 ep12、23（t3g5，gb5 seed 42，没有进 t3m1022aa）换进去，占本周一次 Tier 3 额度；对自己参考跟上换算成榜上能算几集估不准，够不够“有把握领先”说不清，打包、交不交由 rxzhou 定（待定）。Tier 2 SP-SR 也差 2 集，但跟丢的 8 集都是动作难，短期没有能补上的 run。
  两台卡 20:41 起空着：写了 `plan-t3s44-2026-10-26.md`（ep3、14 在 ml40、ep5 在 mf4090 换 seed 44），送独立复核，过了才起链。
- 10/27 01:01 MDT（`results/board/diff_1027_0101.txt`）：FF 重交 Tier 3，MPPE 从 46.0 降到 35.0 cm，拿下 Tier 3 MPPE 第一，我们在这个榜仍第 3、差距变大；longbot（Tier 1）、Luai Abuelsamen（Tier 2 新进）都在我们后面。读法 B 50 / 50、读法 A 9 / 9，第 3；FF 的读法 B 41 → 40。
- 10/27 01:20 MDT（`results/board/diff_1027_0120.txt`）：没变。mf4090 的 t3s44 ep5 读数 R1 不过、不换（`plan-t3s44-2026-10-26.md` 执行记录）；mf4090 暂不排新训练，理由同那里。策略不变：Tier 3 的下一版清单（ep5、10、14、12、23）仍是最快能拿回 SP-SR、MP-SR 的路，ml40 的 ep3、14 读数（约 03:40）出来后一起定，打包与上传待定（rxzhou）。
- 10/27 04:20 MDT（`results/board/diff_1027_0420.txt`）：没变。ml40 的 t3s44 03:25 结束，ep3、ep14 都不换（`plan-t3s44-2026-10-26.md` 执行记录），三集都没换上。两台空着：写了 `plan-t3far-2026-10-27.md`（Tier 3 离跟上远的 4 集在 gb5 上补训），复核后才起链。策略不变，Tier 3 下一版清单待定（rxzhou）。
- 10/27 07:23 MDT（`results/board/diff_1027_0723.txt`）：Izus_systems 05:37–05:38 MDT 重交 Tier 1、Tier 2 共 8 个榜。Tier 1 AUC、MP-SR 上它本来就在我们前面，这次越过了 FF、nima arki；Tier 2 四个榜它都还在我们后面。我们 12 个榜的名次都没变，读法 B 50 / 50、读法 A 9 / 9，第 3；FF 的读法 B 40 → 42、nima arki 45 → 46，前三的顺序不变。策略不变：Tier 1 不是近期能拿回的榜；Tier 3 下一版清单（ep5、10、14、12、23）仍是最快的路，打包与上传待定（rxzhou）。两台都在跑 t3far（mf4090 ep19 训练中，ep13 已训完；ml40 ep27 训练中，ep15 已训完），读数按 `plan-t3far-2026-10-27.md`。
- 10/27 09:01 MDT（SOP 更新时的快照，`results/board/diff_1027_0901.txt`）：domoarigato 08:02 重交 Tier 3、08:57 重交 Tier 1。Tier 3 MPPE 66.5 → 31.3 cm 拿下第一，我们在这个榜跌到第 4；Tier 3 SP-SR 与我们同分（Kaggle 规则我们在前，官网规则它在前）；Tier 1 四个榜它都越过我们，各掉一名。Kelly To the H 新进 Tier 3，在我们后面。读法 B 55（Kaggle，第 3）/ 56（官网，与 domoarigato 同分第 3）、读法 A 11（与 domoarigato 同分第 3）。策略：Tier 1 仍不是近期能拿回的榜；domoarigato 追上来以后，Tier 3 新清单（ep5、10、14、12、23）能拉开的 SP-SR、AUC、MPPE 更要紧，打包与上传待定（rxzhou）。t3far 读数（约 10:00）出来后一起定。
- 10/27 10:20 MDT（`results/board/diff_1027_1020.txt`）：Kelly To the H 重交 Tier 1 AUC 与 Tier 2 四个榜，分数都没变；我们名次不变，读法 B 55 / 56（官网与 domoarigato 同分）、读法 A 11（同分），第 3。两台 09:26 起空着（t3far 4 集都不换）。写了 `plan-gpu-idle-2026-10-27.md`：这一轮不排 GPU 训练；Tier 3 新清单按策略第 1 节重判，导出那一局最好情况也只到 14 集、余量为 0，不满足“遥遥领先”，改正此前“交了能拉开”的说法；交不交仍待定（rxzhou）。
- 10/27 13:20 MDT（`results/board/diff_1027_1320.txt`）：没变，读法 B 55 / 56、读法 A 11，第 3。两台仍空着。`plan-t3fix-2026-10-27.md` 的 A、C 在 ml40 的 CPU 上跑完（A 一个单元都没换，C 只有 ep24 一小段可改），这一版不出 `t3fx`；下一步是同一份计划里已复核的 B1（贴图分辨对称物体的翻转），要用 ml40 的 GPU 渲染，限时到 10/29 12:00 MDT。不排新训练，理由同 `plan-gpu-idle-2026-10-27.md`。
- 10/27 20:01 MDT（`results/board/diff_1027_2001.txt`；17:10 的一班晚到，与 17:00 的 SOP 更新合并做）：Luai Abuelsamen 重交 Tier 1、Tier 2，Tier 2 MPPE 17.4 → 14.1 cm 越过我们（我们 15.3 cm，第 4 → 第 5）；nima arki 重交 Tier 1、Tier 2，Tier 1 AUC、SP-SR、MPPE 与 Tier 2 AUC、SP-SR 小幅变好，名次对我们没影响；Kelly To the H 重交 12 个榜分数都没变。读法 B 56 / 57（Kaggle / 官网），仍第 3；读法 A 12，掉到第 4（FF 8、nima arki 9、domoarigato 11）。
  策略：Tier 2 MPPE 不是短期能拿回的榜（续训 t2ft2 已证明没有额外提升，差 nima arki 4.5 cm）；最快的路仍是 Tier 3，但新清单不满足第 1 节。`plan-t3fix` 的 B1 全量跑完没过 G0（负对照里 5° 转动在 ep08、ep26 被判换），不改任何集。两台空着，下一项是重定向一侧“机器人手到晚”的修法：先量 5 集跟丢集与对照集里机器人手与人手各自到物体的距离时序，再定修法，写成 `plan-t3hand` 送独立复核（正在写）。
- 10/27 22:20 MDT（`results/board/diff_1027_2220.txt`）：FF 重交 Tier 2，MPPE 13.2 → 9.3 cm 拿下 Tier 2 MPPE 第一（越过 nima arki 的 10.8），AUC、SP-SR 也小幅变好；我们 12 个榜名次都没变，读法 B 56 / 57（Kaggle / 官网，第 3）、读法 A 12（第 4）；FF 的读法 B 49 → 47，nima arki 49 → 50。
  策略不变：Tier 2 MPPE 与第一的差距拉到 6 cm，更不是短期能拿回的榜。两台在跑 `plan-t3hand` 的 P0 对照臂（mf4090 ep13、ml40 ep15，朝向终止关掉），约 01:00–01:30 MDT 出读数，按它定 P1 做不做。
- 10/28 01:01 MDT（SOP 更新时的快照，`results/board/diff_1028_0101.txt`）：FF 重交 Tier 1，AUC 0.668 → 0.740、MPPE 5.6 → 5.2 cm（SP-SR、MP-SR 没变）；我们 12 个榜名次都没变，读法 B 56 / 57（第 3）、读法 A 12（第 4）；FF 的读法 B 47 / 48。策略不变：两台在训 `plan-t3flip13` 的 ep13（ml40）与 `plan-t3ocoff` 的 ep27、ep19（mf4090）。
- 10/28 04:20 MDT（`results/board/diff_1028_0420.txt`）：Izus_systems 重交 Tier 1（04:18 MDT），AUC、SP-SR、MPPE 小幅变好、MP-SR 没变；它在 Tier 1 的位置本来就在我们之上或之下不变，我们 12 个榜名次都没动，读法 B 56 / 57（Kaggle / 官网，第 3）、读法 A 12（第 4）。差距最小的榜仍是 Tier 3 MP-SR（与 nima arki 同分）、Tier 3 SP-SR（差 2 集）、Tier 2 SP-SR（差 2 集）。
  策略不变。ml40 03:xx 空出来（`plan-t3flip13` 的 ep13 训评完：跳变穿过去了，但放下后参考里的箱子无手接触地移动，仍跟丢，ep13 记为已知），没有复核过的计划等它，这一班不排新训练，理由记在 `plan-gpu-idle-2026-10-27.md` 执行记录；mf4090 在训 `plan-t3ocoff` 的 ep19（ep27 已训完，导出在段尾一起做），约 06:00 MDT 两集读数。
