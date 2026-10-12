# 计划：Tier 2 按乙逐条选 run 并打包（2026-10-12，第 2 版）

10/12 决定 Tier 2 选乙（`agent-doc/plan-next-training-2026-10-12.md` 第 4a 节第 1 条，用户授权代为决定）：每条 episode 在已评完、已导出的 run 之间
取 4096 世界 MP-SR 高者，相同取 ADD-AUC 高者，仍相同保留现在交的那条。本计划只做选择与打包，不用 GPU，不提交。时间一律 UTC-6。

第 1 版经 Fable 5.1 审查（GO WITH FIXES，1 MAJOR、3 MINOR、3 NIT），处理见文末“审查与处理”；与正文冲突处以文末为准。

## 1. 事实

- 现在交的 Tier 2：`stages/evaluate/exports/{ml40,mf4090}.tsv` 的 Tier 2 行（10/3 那份 CSV），30 条。
- 候选：现在交的 30 条；t2xa 训完的 14 条（`stages/evaluate/exports/cand_t2_t2xa_ml40.tsv`，ep23 没训）；第 3 步试验在 Tier 2 上的 16 条
  （`stages/evaluate/exports/cand_t2_r3t2_ml40.tsv`，10/12 导出 16 条 ok，`results/t2x/export_end_r3t2_ml40.txt`）。t2xb 的 9 条 10/12 10:50 起链，结束后再选一次。
- 4096 世界评测：上面 60 条在 Mac 上都有评测记录（`results/ml40/day2/eval_<run>_s349999104.txt` 或 `results/day2/…`，含 `summary_json` 行，
  其中有 `checkpoint`、`checkpoint_sha256`、`world_count`）；评测对照的是 v5.4 参考，不是干净真值。
- 导出结果表在服务器上：ml40 `runs/exports/{export2_ml40,cand_t2_t2xa_ml40,cand_t2_r3t2_ml40}.tsv`，mf4090 `runs/exports/export2_mf4090.tsv`
  （每行：档位 episode run 步数 状态 JSON parquet JSON 的 sha256 parquet 的 sha256）。10/3 拉回时存的副本在 Mac 的 `runs/submission/final/export2_*.tsv`。
- 打包：10/3 在 Mac 上打（`stages/evaluate/pack_tier.sh`，kit `update_0f2f9f4b`，Tier 2 加 `--frame-references runs/submission/frame_refs_t2`）。
  `pack_tier.sh` 要求 HEAD 已推到远端、除 `results/` 外工作树干净。官方打包器读 Tier 1 的干净参考来定行的网格并算本地分数，
  `pack_tier.sh` 把 Tier 2 的本地分数那一行在落盘、显示之前滤掉（`test_pack_tier.py` 有测试），这个分数不用于任何选择。
- `pull_submission.sh exports` 把一张结果表的 ok 与 fallback 行拉到 `runs/submission/final/t<档>/`，同名文件内容不同就拒绝，所以新选择放到新目录。
- CSV 的每一行有 `checkpoint_sha256`，row_id 形如 `track_2/e000017/w000/f000000/o0`；导出 JSON 里有 `checkpoint_sha256` 与 `world_count`。

## 2. 做法

0. **提交代码**：`select_t2.py`、`test_select_t2.py`、`check_t2_select.py`、`test_check_t2_select.py`、`pull_submission.sh` 的 `tables` 与 `select` 两个模式、本计划；推送。
1. **拉结果表**（只读，经 record）：`pull_submission.sh tables runs/submission/select_t2_b1012/tables ml40:export2_ml40 ml40:cand_t2_t2xa_ml40 ml40:cand_t2_r3t2_ml40 mf4090:export2_mf4090`。
   再把新拉的 `export2_*.tsv` 与 10/3 的副本逐字节比较，不同就停（服务器上的结果表被改过）。
2. **选**（经 record）：`select_t2.py` 读现在交的清单、上一步拉回的四张表、两个评测目录。候选资格：表里步数 349999104、状态 ok 的行恰好一行，
   且评测记录的 checkpoint 属于这条 run。每条 episode 按乙选：MP-SR（不四舍五入）高 → ADD-AUC 高 → 现在交的那条 → run 名字典序
   （第四层是为了结果确定，只在两条都不是现在交的 run 两项都相同时才用到）。输出 `stages/evaluate/exports/t2_select_b1012.tsv`
   与 `results/select_t2/select_b1012.txt`。提交、推送（打包要求工作树干净）。
3. **拉选中的导出**（经 record）：`pull_submission.sh select stages/evaluate/exports/t2_select_b1012.tsv runs/submission/select_t2_b1012/tables runs/submission/select_t2_b1012/t2`，
   与第 2 步读同一份表；按表里的 sha256 核每个文件。
4. **核拉回的导出**（经 record）：`check_t2_select.py`（不给 `--csv`）：每条 episode 的导出 JSON 的 `checkpoint_sha256` 等于选中 run 评测记录里的值，`world_count` 为 1。
5. **打包**：`pack_tier.sh 2 runs/submission/select_t2_b1012/t2 select_b1012`，得到 `runs/submission/csv/track2_tier2_select_b1012.csv`，上传器只跑 `--dry-run`。
6. **核 CSV**（经 record）：`check_t2_select.py --csv …`：CSV 里每条 episode 只有一个 `checkpoint_sha256`，等于选中 run 的值；CSV 的 episode 恰好是清单里的 30 条。

## 3. 判据（执行前登记）

- 选择：每条 episode 恰好选一个；现在交的 run 必须有资格（否则停）；没有资格的候选列出、不进选择。
- 第 1 步：新拉的 `export2_*.tsv` 与 10/3 的副本逐字节相同。
- 第 4、6 步：`CHECK_T2_SELECT_OK`。
- 打包门：打包器对 30 条都成功、CSV 22,989 行；上传器 `--dry-run` 通过。
- 任何一条不满足就停，查原因，不提交。
- 只报：换了的 episode 与新旧两条的 4096 世界 MP-SR、ADD-AUC（对照 v5.4）；选中者里名字带 `-r3a-` 的条数。不拿这些分数比较档位，也不当榜上分数。

## 4. 风险与限制

- 4096 世界的 MP-SR 对照的是 v5.4，跟得更紧不等于榜上更高（第 3 步计划第 6 节）；这是 10/12 选乙时已知的限制。
- 交上去的是 1 个世界的导出，4096 世界 MP-SR 高的 run，1 世界导出也可能失败；只报，不按 1 世界的结果改选（那就成了丙）。
- 档位隔离：选择只读 Tier 2 的评测与导出、v5.4 帧参考。官方打包器读 Tier 1 的干净参考定行的网格并算本地分数，这个分数被滤掉、不用于任何选择；
  其余步骤都不读 Tier 1。

## 审查与处理（Fable 5.1，GO WITH FIXES）——第 2 版

审查另用记录模拟了乙：18 条 episode 会换，全部换成 `-r3a-` 的 run（ep26 换成 `r3a-s43`）；ep11、ep17 的 MP-SR 都是 0、按 ADD-AUC 留现在交的那条。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | 行数与预检分不出新旧 CSV，没有核 CSV 与选择一致 | 采纳：新写 `check_t2_select.py`，核导出 JSON 与 CSV 的 `checkpoint_sha256` 等于选中 run 评测里的值（第 2 节第 4、6 步）；用 10/3 的清单、导出与 CSV 做正向对照，CHECK_T2_SELECT_OK |
| 2 | MINOR | 没有提交、推送的步骤，`pack_tier.sh` 会拒绝 | 采纳：第 0 步与第 2 步各提交、推送一次 |
| 3 | MINOR | “不读 Tier 1”对打包那一步不成立 | 采纳：第 1、4 节照实写 |
| 4 | MINOR | 第 3 步读哪一份结果表不清楚 | 采纳：第 2、3 步读同一份本地副本；第 1 步把新拉的 `export2_*.tsv` 与 10/3 的副本逐字节比较 |
| 5 | NIT | 第四层平手（run 名字典序）不在决定里 | 采纳：注明是为了结果确定、何时用到 |
| 6 | NIT | 没换的 12 条不必重新拉 | 不改：每条都按结果表的 sha256 核，重新拉的量很小，流程统一更不容易出错 |
| 7 | NIT | `exports` 模式也拉 fallback 行 | 采纳：第 1 节照实写 |
