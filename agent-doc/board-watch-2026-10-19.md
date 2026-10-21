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
