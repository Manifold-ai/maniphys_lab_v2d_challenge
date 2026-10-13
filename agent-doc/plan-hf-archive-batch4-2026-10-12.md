# 计划：mf4090 第 4 批归档到 Hugging Face（t3p3 与 t1xa 的 policy 中间份、最终 state），核对后删除（2026-10-12，第 2 版：按 Fable 5.1 审查修改）

依据：`agent-doc/plan-next-training-2026-10-12.md` 第 4a 节第 5 条（10/12 用户授权代为决定）：“HF 归档第 4 批做，在 D 的训练铺开、mf4090 不够时再做；
流程照旧（上传、核对 sha256、抽查下载、再删本地）；仓库是公开的，这批也公开。”流程与第 3b 批相同（`agent-doc/plan-hf-archive-batch3-2026-10-10.md`
第 4 版与其后的删除一节），这里只写差异与这次的判据。时间一律 UTC−6。第 1 版经 Fable 5.1 独立审查（GO WITH FIXES：0 条 MAJOR、6 条 MINOR、
3 条 NIT），逐条处理见文末。

## 1. 事实

- **为什么要腾**：D（Tier 3 交付版的训练）放在 mf4090 上，一集约 375 MB（正式 run 360 MB，加冒烟与 diag）。mf4090 13:28 可用 7677 MB
  （`results/ops/hf_batch4_candidates_mf4090_1012.txt`），交付版这一轮的重定向还在写（约 2.5 GB，`agent-doc/plan-t3-delivery-p2-2026-10-12.md` 第 1 节），
  t1xa2 的 6 条约 2.2 GB；之后约剩 3 GB（估计）。交付版写明之后还要再拼一次目录、重定向一次（约 2.9 GB）。不腾的话，D 一段链只够几集
  （链的磁盘闸：起链 ≥ 2500 MB，每条开跑前 ≥ 1200 MB）。
- **候选**（同一记录，13:28）：有 DONE、policy 多于 9 份或有 state 的正式 run 10 条，都是 35 份 policy 加 1 份 state、359–360 MB：
  t3p3 的 9 条（`t3-ep{0,15,17,18,20,22,23,26,29}-w2048-cap4m-r3a-v2-mf4090`）与 t1xa 的 `t1-ep17-w2048-cap4m-r3a-mf4090`。
  t1xa2 的 6 条（`t1-ep{21,10,13,19,3,14}-w2048-cap4m-r3a-mf4090`）预计 10/13 凌晨训完，按同一配置也会是 35 + 1。
- **规则**照第 2、3 批（`tools/hf_archive.py` 文档）：policy 每条留步数最大的 9 份，另留导出过的步数、state 的步数、`STATE_PRUNED` 里的步数；
  最终 state 挑步数最大、且它与同步数的 policy 都完整的那份，同步数的 policy 留着；`--kind` 照第 3 批用 `policy,state,final`，
  旧 state 这一类预计挑不到（候选 run 都只有 1 份 state）。这 16 条 run 导出过的步数只有 349999104（导出清单与状态记录，审查核过），在最新 9 份之内。
- **预计清单**：t1xa2 全部训完时 16 条 run，policy 16 × 26 = 416 个（步 10000384–260009984）、最终 state 16 个（步 349999104）、旧 state 0 个，
  共 432 个文件，约 4.58 GB（按第 3b 批的文件大小推算：policy 4,859,972–4,860,004 字节、state 160,120,996–160,121,108 字节，
  `results/ops/hf_archive_batch3b_precheck_mf4090.txt`；16 条时合计约 4,583.7 MB，误差在 1 MB 以内）。删完每条 run 剩约 80 MB（9 份 policy 与日志）。
- **不在这批的**：没有 DONE、但有 state 的 5 个目录（3 个 `smoke_t1_ep20_w*` 各 158 MB、`t1-ep28-w2048-cap4m-mf4090` 341 MB、
  `t1-ep7-w2048-cap4m-p185-mf4090` 241 MB，共约 1.06 GB）不在任何一条规则里，这批不动；要不要处理另议。
- **工具**：mf4090 `runs/tools/` 下 `hf_archive.py`、`hf_archive_run.sh`、`hf_archive_report.py`、`test_hf_archive.py` 的 md5 与仓库 4bc4e5b 的相同
  （同一记录），这批不改代码、不用同步。README 不经同步：同第 3b 批，从 Mac 拷到 mf4090 的 `runs/hf_readme/v2d-track2-archive.md` 再上传。
- **工具的约束**：`plan` 在有训练链（`runs/.chain-active-*`）时拒绝挑 policy 与最终 state；删除一步在有训练链、GPU 上有进程、有导出评测训练相关进程时停。
  t1xa2 13:21 起链，正式训练每条 124–143 分钟（`results/t3p3/pace_mf4090_t3p3c_final.txt`），三条链预计 10/13 02:10–04:30 结束（估计）。
- **仓库**：`Rongxuan-Zhou/v2d-track2-archive` 10/11 起公开，第 3b 批之后 1692 个文件、约 24.36 GB（第 3 批计划执行记录）。
  每个 HF 仓库要有根目录 README（`docs/hf/v2d-track2-archive/README.md`，`readme` 子命令上传）。
- **速度**：10/8 上传 6.57 GB 用了 19.6 分钟（约 5.6 MB/s）；第 3b 批抽查每条 run 下载最终 state 与 1 个随机文件，16 条时 32 个、约 2.64 GB。

## 2. 做法

0. 本计划提交、推送。不改代码，不同步。
1. Mac 上后台等 t1xa2 三条链的标记都清掉，记下 t1xa2 的结局（`stages/policy/chain_status_remote.sh`）。Mac 睡眠或断网时这一步顺延，不影响服务器。
   三条链的日志都写了结束行、标记却还在（残留）时，按 t1xa 结束时的查法（状态记录、`tmux ls`、GPU 进程）核实，报给用户，不自动删标记。
2. 生成清单之前，用 13:28 那条列目录的命令再记一次候选（`results/ops/hf_batch4_candidates_mf4090_<月日时分>.txt`）；
   然后 `scripts/dev/record ops/hf_archive_batch4_plan_mf4090 scripts/dev/pipe-py tools/hf_archive.py plan --kind policy,state,final --keep 9
   --out runs/hf_archive_batch4_manifest_mf4090.json`。清单按 run 逐条与新的候选记录对（run 名、26 份 policy 的步数、最终 state 的步数），
   总数与总字节与第 1 节的预计对。
3. README 加第 4 批一行，状态写“上传中，本地未删”，拷到 mf4090 的 `runs/hf_readme/v2d-track2-archive.md`，经 `tools/hf_remote.sh` 跑
   `md5sum runs/tools/hf_archive.py runs/hf_readme/v2d-track2-archive.md`、`python3 runs/tools/hf_archive.py readme --repo Rongxuan-Zhou/v2d-track2-archive
   --file runs/hf_readme/v2d-track2-archive.md --message "…" --visibility public`、`python3 runs/tools/hf_archive.py whoami --repo Rongxuan-Zhou/v2d-track2-archive
   --visibility public`（`results/ops/hf_readme_v2d_track2_archive_batch4.txt`；同第 3b 批的命令）。
4. 第一段：`tools/hf_remote.sh` 在 mf4090 上 setsid 后台运行 `timeout 7200 bash runs/tools/hf_archive_run.sh runs/hf_archive_batch4_manifest_mf4090.json
   Rongxuan-Zhou/v2d-track2-archive mf4090 runs/hf_archive_batch4_mf4090`，环境变量 `V2D_HF_ARCHIVE_STEPS=verify`、`V2D_HF_VISIBILITY=public`、
   `V2D_HF_SPOTCHECK_PER_RUN=1`、`V2D_HF_SPOT_MIN_FREE_MB=1700`、`V2D_HF_SPOT_MAX_CACHE_MB=50`、`HF_XET_CHUNK_CACHE_SIZE_BYTES=0`（与第 3b 批相同）。
   输出经 `grep --line-buffered -v -E '@|hf_[A-Za-z0-9]{20}'` 写 `runs/logs/hf_archive_batch4_run.log`。第一段期间 mf4090 上不起别的写盘任务
   （拼目录、重定向、训练链），抽查一次只下载一个文件、核完就删。
   **后备**（同第 3 批第 3 版第 6 步、第 4 版第 8 步）：抽查被“下载前可用不足”的闸停下时，用同一清单、同一前缀、`V2D_HF_SPOT_MIN_FREE_MB=300`、
   `V2D_HF_ARCHIVE_STEPS=check` 重跑（这时没有训练链，1700 MB 比链的 1200 MB 高 500 MB 的理由不成立）。被缓存闸或 `timeout` 停下，
   或上传被拒，就停下报告，不改闸、不重试。
5. 第一段结束：日志（`results/ops/hf_archive_batch4_run_mf4090.txt`）与汇总（`hf_archive_report.py`，`results/ops/hf_archive_batch4_results_mf4090.txt`）
   落盘，核对结论送 jev（带对照题），报给用户并请求确认删除。README 第 4 批改为“已上传、已核对，本地未删”，补“校验”一节的数字，照第 3 步重传。
6. 第二段（用户确认之后，没有训练链、GPU 空闲时）：
   1. 删除前的对齐核对（只读，`results/ops/hf_archive_batch4_precheck_mf4090.txt`），经 `tools/hf_remote.sh`：
      `python3 runs/tools/hf_archive.py verify --manifest runs/hf_archive_batch4_manifest_mf4090.json --repo Rongxuan-Zhou/v2d-track2-archive --prefix mf4090
      --out runs/hf_archive_batch4_mf4090.precheck.json`；`python3 runs/tools/hf_archive.py delete --verified runs/hf_archive_batch4_mf4090.precheck.json
      --spotcheck runs/hf_archive_batch4_mf4090.spotcheck.json`，不加 `--yes`（演习，按现在的本地文件逐个重算大小与 sha256，只列“将删”）。
   2. 删除：`V2D_HF_ARCHIVE_STEPS=delete V2D_HF_VISIBILITY=public`，setsid 后台跑 `runs/tools/hf_archive_run.sh`，清单与输出前缀同第一段，
      日志 `runs/logs/hf_archive_batch4_delete.log`（`results/ops/hf_archive_batch4_delete_run_mf4090.txt`）。流程脚本删除前再核对一遍仓库、
      过三道闸（长链标记、GPU 进程、导出评测训练相关进程），每个文件删之前再按本地重算 sha256。
   3. 删除后的本地状态：`scripts/dev/pipe-py tools/hf_archive_report.py runs/hf_archive_batch4_manifest_mf4090.json runs/hf_archive_batch4_mf4090`
      （`results/ops/hf_archive_batch4_after_delete_mf4090.txt`）。
   4. README 第 4 批改为“已删除”，“与训练机上的记录对应”一节补 ARCHIVED.json 的记录时间，照第 3 步重传。
7. 用户不同意删除：`rm -rf runs/hf_stage`（硬链接与上传缓存），仓库里的副本留着，本地什么都不删；D 的磁盘另想办法。

## 3. 判据（执行前登记）

- 开跑前：`whoami` 报 HF_WHOAMI_OK，账号 Rongxuan-Zhou、token 权限 write、仓库公开；生成清单时没有训练链；流程脚本日志第一行的工具 md5
  与第 1 节记录里的相同。
- 清单：run 与第 2 步新记的候选逐条相同（有 DONE、35 份 policy 加 1 份 state 的正式 run；t1xa2 全部训完时 16 条，没训完的不进清单）；
  每条 26 份 policy、步 10000384–260009984，1 份最终 state、步 349999104；旧 state 0 个；16 条时总字节约 4,583.7 MB（误差在 1 MB 以内，
  少几条按条数折算）。对不上就停，查原因，不改规则、不上传。
- 第一段：全部文件的大小与 sha256 一致（verify）；抽查 2 × run 数个文件（16 条时 32 个），下载后 sha256 全部一致；有一个不一致就一个都不删，
  停下排查。抽查没有被缓存闸停下（被下载前可用的闸停下按第 2 节第 4 步的后备处理）。xet 缓存在日志第一行与 HF_ARCHIVE_VERIFIED 那一行的
  大小只报：这批真传 4.58 GB，缓存的硬闸是抽查期间的 50 MB（第 3 批第 4 版审查 m2 的做法）。
- 删除前：verify 全部一致（HF_VERIFY_OK）；演习列出“将删”等于清单的文件数、“跳过” 0 个。有一个对不上就停，不删，报告用户。
- 删除：删除前的重新核对通过；删除期间消失的文件只能是清单里的，其他文件一个不少（流程脚本的前后清单比对）；每条 run 删完剩 9 份 policy、
  0 份 state，DONE 与日志都在；可用空间的增加与清单总字节相差不超过 50 MB（同第 3b 批）。
- README：每次上传 HF_README_OK；仓库仍为公开；第一段之后文件数是 1692 加上传的个数。

## 4. 风险与限制

- 删除要等用户确认。确认之前 mf4090 约剩 3 GB：交付版的第二轮拼目录与重定向（约 2.9 GB）和 D 都排不开，只能等，或另删这一轮
  `tier3_dlv` 的重定向产物（交付版换成后处理版之后它就用不上了，删不删另报）。
- 仓库公开：checkpoint 公开是 10/11 用户同意的口径，这批照旧；归档里只有 checkpoint，没有数据集文件。README 在上传前只写“上传中”，
  上传被拦下时公开页面上没有不实的说法。
- `timeout 7200`：上传卡住（`upload_large_folder` 出错会一直重试）时 2 小时后整组结束，什么都不删，之后用同一命令续传。

## 5. 时间（估计）

候选与清单约 3 分钟；上传约 4.58 GB 约 15 分钟；核对约 5 分钟；抽查 32 个文件约 2.64 GB、约 10–20 分钟；删除前核对与演习约 5 分钟；删除约 5 分钟。
t1xa2 结束后约 1 小时到“请求确认删除”。

## 审查与处理（第 2 版）

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| m1 | MINOR | 上传之前 README 就写“已上传”，上传被拦下时公开页面的说法是假的 | 采纳：第 3 步写“上传中，本地未删”，第 5 步核对通过后改“已上传、已核对，本地未删” |
| m2 | MINOR | 少了第 3b 批删除前的对齐核对与删除演习（用户 10/11 要求“删之前检查下HF有没有对齐本地”） | 采纳：第 2 节第 6 步第 1 小步与判据“将删 = 清单数、跳过 0” |
| m3 | MINOR | 清单判据“那时有 DONE 的 run 数”没有记录可比，13:28 的候选不含 t1xa2 | 采纳：生成清单前用同一命令再记一次候选，清单逐条对 |
| m4 | MINOR | 1700 MB 的闸来由是比链高 500 MB，这次没有链；剩约 3 GB 时余量不到一倍，被闸停下没有后备 | 采纳：登记第 3 批的后备（同清单、同前缀、300 MB、`check` 重跑） |
| m5 | MINOR | “xet 缓存首尾差 ≤ 50 MB”在第 3 批第 4 版已改为含上传时只报，这批真传 4.58 GB | 采纳：首尾差只报，硬闸仍是抽查期间的 50 MB |
| m6 | MINOR | README 不经同步怎么到 mf4090 没写 | 采纳：拷到 `runs/hf_readme/v2d-track2-archive.md`，`readme --file` 用这条路径，记录带 md5（同第 3b 批） |
| n1 | NIT | “约 4.5 GB”混用 MiB 与 MB | 采纳：按第 3b 批的文件大小写成约 4,583.7 MB（4.58 GB），抽查约 2.64 GB；审查给的 policy 大小 4,859,992 字节与记录不符，记录里是 4,859,972–4,860,004 字节 |
| n2 | NIT | 抽查个数与可用空间增加量没有进判据 | 采纳：抽查 2 × run 数；可用空间增加与清单总字节相差不超过 50 MB |
| n3 | NIT | Mac 睡眠会让整批顺延；标记残留时 `plan` 永远拒绝，没写怎么判 | 采纳：第 2 节第 1 步注明顺延无害；残留标记按 t1xa 的查法核实后报给用户，不自动删 |

## 执行记录（时间 UTC−6）

- 10/12 17:24–17:41 上传、核对与抽查：297 / 297 一致，抽查 22 个一致，本地副本留着（`results/ops/hf_archive_batch4_run_mf4090.txt`、
  `results/ops/hf_archive_batch4_verified_mf4090.txt`）。
- 10/13 00:09 前后用户同意删除（“确认过HF和本地一样的就可以删”）。删除要在没有训练链时做，交给 `t3p4a` 结束后的接续进程
  （`agent-doc/plan-mf4090-handover-2026-10-13.md`）。
- 10/13 05:09–05:10 删除：删前对仓库再核对 297 / 297 一致，演习将删 297、跳过 0；删后消失 297 个（其中没删的 0 个），清单外消失的文件无；
  可用空间增加 3006 MB，与清单 3005 MiB 相差 1；11 条 run 各剩 9 份 policy、0 份 state，DONE 与日志都在。第 3 节的判据全部满足
  （`results/ops/hf_archive_batch4_delete_run_mf4090.txt`、`results/ops/hf_archive_batch4_after_delete_mf4090.txt`、`results/ops/hf_archive_batch4_done_logs_mf4090.txt`）。
- 10/13 07:35 README 第 4 批改为“10/13 已删除”，重传 `HF_README_OK`（`results/ops/hf_readme_v2d_track2_archive_batch4_deleted.txt`）。
