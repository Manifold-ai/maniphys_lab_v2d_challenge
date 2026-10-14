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

## 执行记录（10/12，时间 UTC-6）

- 第 0 步：代码与本计划第 2 版提交 1640c05，推送。
- 第 1 步：四张结果表拉回（`results/select_t2/tables_b1012.txt`：ml40 export2 ok 30、t2xa ok 14 与 no_done 1、试验 ok 16，mf4090 export2 ok 30）；
  两张 `export2_*.tsv` 与 10/3 的副本逐字节相同（`results/select_t2/tables_cmp_b1012.txt`）。
- 第 2 步：`results/select_t2/select_b1012.txt`：没有资格的候选 0 条；换了 18 条，全是名字带 `-r3a-` 的 run（ep26 是 `r3a-s43`）；
  ep11、ep17 留现在交的。选择清单 `stages/evaluate/exports/t2_select_b1012.tsv` 提交 adfa1a0、推送（打包用的代码 URL 就是这个 commit）。
- 第 3、4 步：拉回 30 条（60 个文件，按表里的 sha256 核过，`results/select_t2/pull_b1012.txt`）；导出核对 CHECK_T2_SELECT_OK（`results/select_t2/check_exports_b1012.txt`）。
- 第 5 步：`pack_tier.sh` 里 uv 联网解析依赖失败三次（Mac 连不上 PyPI；离线模式缺 pandas 2.x；失败的记录被之后成功的同名记录替换，没有留下）。
  改用 uv 缓存里 10/3 打包时同一组版本的环境（Python 3.12.14、numpy 2.5.3、pandas 2.3.3、pyarrow 25.0.1、trimesh 5.1.0、kaggle 2.2.4，kit 的依赖都能导入），
  经 `V2D_PACK_PYTHON` 传给 `pack_tier.sh`，打包器与参数不变。CSV `runs/submission/csv/track2_tier2_select_b1012.csv`：22,989 行、30 条 episode，
  sha256 befa4565…；上传器 `--dry-run` 通过，没有提交（`results/submission/pack/t2_select_b1012{,_dryrun}.txt`）。
- 第 6 步：CSV 核对 CHECK_T2_SELECT_OK（`results/select_t2/check_csv_b1012.txt`）；负对照（同一份清单对 10/3 的 CSV）报 18 处不符，正是换了的 18 条
  （`results/select_t2/check_csv_negctl_b1012.txt`）。

## 执行记录（10/13，标签 b1013：加 t2xb 的候选再选一次，时间 UTC-6）

计划 D 第 3 节第 7 步要求 t2xb 结束后用它的候选重做一次乙。做法、判据与 10/12 相同，只多一张结果表 `cand_t2_t2xb_ml40`，现在交的清单仍是 10/3 那份。

- 第 1 步：五张结果表拉回（`results/select_t2/tables_b1013.txt`：ml40 export2 ok 30、t2xa ok 14 与 no_done 1、试验 ok 16、t2xb ok 9，mf4090 export2 ok 30）；
  两张 `export2_*.tsv` 与 10/3 的副本、t2xa 与试验两张与 10/12 的副本逐字节相同（`results/select_t2/tables_cmp_b1013.txt`；第 1 次的输出在 Mac 的 bash 3.2 下
  把变量名后面的中文吃掉了，比较本身照常，留档 `_run1`）。
- 第 2 步：`results/select_t2/select_b1013.txt`：与 10/3 相比换了 24 条，全是名字带 `-r3a-` 的 run；与 10/12 的清单相比只差 ep2、9、13、14、19、28 六条
  （`results/select_t2/diff_b1012_b1013.txt`），都换成 t2xb 的 run：ep13 MP-SR 0.130、ep2 0.011，其余四条 MP-SR 都是 0、按 ADD-AUC 换
  （ep9 0.206 → 0.274、ep14 0.303 → 0.432、ep19 0.180 → 0.318、ep28 0.077 → 0.105）；ep1、ep4、ep25 的 t2xb run ADD-AUC 更低，留现在交的。
  选择清单 `stages/evaluate/exports/t2_select_b1013.tsv` 提交 5888a41、推送。
- 第 3、4 步：拉回 30 条（60 个文件，`results/select_t2/pull_b1013.txt`）；导出核对 CHECK_T2_SELECT_OK（`results/select_t2/check_exports_b1013.txt`）。
- 第 5 步：同 10/12 用 uv 缓存里的环境（`V2D_PACK_PYTHON`）。CSV `runs/submission/csv/track2_tier2_select_b1013.csv`：22,989 行、30 条 episode，sha256 770a1101…；
  上传器 `--dry-run` 通过，没有提交（`results/submission/pack/t2_select_b1013{,_dryrun}.txt`）。
- 第 6 步：CSV 核对 CHECK_T2_SELECT_OK（`results/select_t2/check_csv_b1013.txt`）；负对照（这份清单对 10/12 的 CSV）报 6 处不符，正是新换的 6 条
  （`results/select_t2/check_csv_negctl_b1013.txt`）。
- 只报：ep9 换上的 t2xb run ADD-AUC 更高，但 MPPE 29.44 → 56.92 cm 变差（`results/t2x/eval_table_t2xb.txt`）；乙只看 MP-SR 与 ADD-AUC，照登记的规则不改。
- jev：`results/t3q/jev_claims_t1x1013_b1013_t3qa.txt` 的 t2_* 四条核实（0.90–0.99）。交不交、什么时候交仍由用户定。

## 提交（10/14，时间 UTC-6）

- 10/14 00:00 前后用户确认 Tier 2 四个比赛的队名无误，同意提交 b1013 并看排名。这次同意只针对 b1013 这一次提交。
- 00:04 上传器 `--dry-run` 通过，CSV md5 与打包时相同（68be09b0…），4 个榜当天各剩 5 次（`results/submission/dryrun_b1013_1014_0004.txt`）。
- 00:05 提交，4 个榜一次都 ACCEPTED（submission 57169480、57169488、57169498、57169505），公榜分 AUC 0.51379、SP-SR 0.73333、
  MP-SR 0.53333、MPPE 16.54028 cm（`results/submission/submit_b1013.txt`；回执复制到 `results/submission/receipts/`）。
  Tier 2 打包时只算了 4096 世界的选择指标，没有单世界的本地复算分，这次没有本地分可对照。
- 00:07 的榜（`results/submission/leaderboard_1014_0007.txt`）：AUC、SP-SR、MP-SR 三项 maniphys.ai 排第一；MPPE 排第二，Xueyi Wang (FF) 15.34253 cm，
  差 1.20 cm（30 条 MPPE 总和约差 35.9 cm）。CHORD 基线 0.37374、0.53333、0.06666、20.52402 cm，四项都超过。按成功条数：SP-SR 22 / 30（基线与 FF 都是 16 / 30），
  MP-SR 16 / 30（FF 8 / 30，基线 2 / 30）。
- jev：`results/submission/jev_claims_t2_submit_1014.txt`（11 条核实 0.94–0.99，4 个对照正常）、`results/site/jev_claims_sop_page_1014_0000.txt`（4 条核实，3 个对照正常）。
