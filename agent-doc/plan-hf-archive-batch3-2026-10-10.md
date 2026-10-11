# 计划：mf4090 第 3 批归档到 Hugging Face（policy 中间份、旧 state、最终 state），核对后删除（2026-10-10，第 3 版：第一段撞上 HF 私有存储额度，只对已提交的部分核对与删除）

用户 10/10 23:2x 的回复：“容量不够的话 还是按照之前的流程上传到HF”。这句回答的是“Tier 3 过门槛的 10 集在 mf4090 上训、
磁盘不够”（训练计划 `agent-doc/plan-t3-v2-train10-2026-10-10.md`）。按之前的流程（10/8 第 2 批）分两段：上传、核对、抽查之后停下，
用户确认后再删。时间一律为 UTC-6。

## 事实

- 磁盘：mf4090 系统盘 10/10 23:22 可用 2625 MB（`results/ops/mf4090_disk_1010_2330.txt`），10/11 00:34 可用 2623 MB
  （`results/ops/mf4090_prearm_t3p3_1011_0010.txt`）。没有训练链，GPU 上没有进程。
- 一集 Tier 3 约占 375 MB：正式 run 360 MB（35 份 policy 约 170 MB、最终 state 153 MB、wandb 45 MB），冒烟目录 6 MB，diag 9 MB
  （`results/ops/mf4090_t3run_size_1010_2340.txt`，按 t3-ep24 两轮与 t3-ep8 第一轮实测）。
- 链的磁盘闸：起链要求可用 ≥ 2500 MB（`stages/policy/arm_var_chain.sh` 第 30 行）；每次冒烟与正式开跑前可用不到 1200 MB 就停整条链
  （`V2D_MIN_FREE_MB=1200`，`stages/policy/day2_train_chain.sh` 的 `disk_check`）。一段链要跑完 k 集，起链时要求可用
  ≥ 1200 + (k−1) × 375 + 15 MB。现有 2623 MB 只够 4 集。
- 按现有两条规则能挑的（`results/ops/mf4090_disk_1010_2330.txt`）：
  - policy 中间份（第 2 批规则，每条 run 留最新 9 份）：有 DONE 且多于 9 份的 run 9 条（`t1-ep0`、`t1-ep5`、`t1-ep15` 的 r3a 与 r3a-s43 共 6 条，
    `t3-ep8`、`t3-ep24` 第一轮与 `t3-ep24` 第二轮共 3 条），每条 35 份、挑 26 份，共 234 个文件，约 1.14 GB；
  - 旧 state（第 1 批规则）：只有 `t1-ep7-w2048-cap4m-p185g-mf4090` 的 3 份较旧的 state，约 0.48 GB。
  - 合计约 1.6 GB，删完可用约 4.2 GB。一条链只够 8 到 9 集（按 MB 还是 MiB 算差一集）；先跑 4 集、删完再跑 6 集时，第二段只够 4 集。
- 最终 state：有 DONE 的正式 run 共 62 条，每条留着步数最大的 1 份 state（各 153 MB），共约 9.9 GB。它们只在续训时用到：
  - `stages/policy/fc_run.sh` 第 44 行：run 目录有 DONE 就跳过。`stages/policy/day2_train_chain.sh` 第 131–132 行：有 DONE 跳过；
    没有 DONE 但有残留 state 记 SKIPPED（“续训不恢复 replay”），训练链不续训。
  - `stages/policy/ckpt_latest.py` 只被 `fc_run.sh`（续训）、`smoke_check.sh`（判刚跑完的冒烟）与 `day2_train_chain.sh`（删冒烟的 state）调用。
  - 删掉之后再对这条 run 跑 `fc_run.sh`：有 DONE 直接跳过；去掉 DONE 再跑，会因为“有 checkpoint 但没有一份完整的”拒绝从 0 开始
    （`fc_run.sh` 第 162–164 行），不会覆盖。
  - 导出、评测、提交核对只读 policy；`chain_health_remote.sh` 数 state 份数，只用于当前那条链的 run。
- 没有 DONE 的 run 不动：`t1-ep28-w2048-cap4m-mf4090`（2 份 state）、`t1-ep7-w2048-cap4m-p185-mf4090`（1 份）、3 个 `smoke_t1_ep20_*`（各 1 份）。
- 仓库 `Rongxuan-Zhou/v2d-track2-archive` 是私有的，10/8 第 2 批删除后有 1393 个文件，两批共 12.8 GB。这一批约 11.6 GB，传完约 24.4 GB。
  账号的私有存储额度没有查；超出时上传会报错，不会删除任何东西。
- 速度：10/8 上传 6.57 GB 用了 19.6 分钟（约 5.6 MB/s），这一批估计约 35 分钟。抽查改为有最终 state 的 run 固定抽它、再从其余文件里
  随机补 1 个（审查 m2），共 72 个文件（62 份最终 state、9 份 policy、1 份旧 state），下载约 10.1 GB，估计 30–40 分钟。
- mf4090：22 核、111 GB 内存；huggingface_hub 1.32.0、hf_xet 1.6.0；`~/.cache/huggingface` 下 hub 269 MB、xet 39 MB。
  10/8 抽查下载约 250 MB，上传与抽查前后缓存只多了约 27 MB（第 2 批计划执行记录）。
- 10/1 第 1 批是在 Tier 2 训练链同时运行时上传并删除的（第 1 批计划）。

## 做法

1. 工具（`tools/hf_archive.py`）：
   - `plan` 新增 `--kind final`：有训练链在跑就不做；只看有 DONE 的正式 run（不分档位，冒烟不看）；挑步数最大的那份 state，
     条件是它与同步数的 policy 都完整，否则整个 run 不动；同步数的 policy 不动。
   - `--kind` 可以用逗号连几种，这一批用 `policy,state,final`：清单是三种的并集，同一个文件出现两次就报错，不写清单。
   - `delete`：清单里有最终 state 时，有训练链在跑就一个都不删。删每份最终 state 之前按当时的文件重算：它仍须是步数最大的 state，
     且它与同步数的 policy 都完整，否则跳过。正式 run 不写 STATE_PRUNED。
   - `spotcheck --per-run`：这条 run 有最终 state 时固定抽它，再从其余文件里随机补 1 个；没有最终 state 的 run 照旧随机抽 1 个。
   - `spotcheck` 加两道闸（默认关）：每次下载前可用空间不到 `--min-free-mb` 加这个文件的大小就停；每次下载后 xet 缓存比开始时多出
     `--max-cache-growth-mb` 以上就停。停时不写抽查结果，删除步骤因此不会运行。抽查开始与结束各打印一次 xet 缓存大小与可用空间。
   - `tools/hf_archive_run.sh`：用 `V2D_HF_SPOT_MIN_FREE_MB`、`V2D_HF_SPOT_MAX_CACHE_MB` 把两道闸传给抽查；第一行与 HF_ARCHIVE_VERIFIED 那一行
     加打印 xet 缓存大小。
   - `tools/hf_archive_report.py`：加按类别的文件数与字节，以及清单里的 run 各剩几份 state。
   - 测试（`tools/test_hf_archive.py`）新增 3 项、改 1 项：final 的挑选规则与几种连用（含重复、不认识、空的 `--kind` 报错，有训练链时不挑）；
     final 的删除（有训练链不删；计划之后多了更新的一对、或同步数的 policy 坏了就跳过；policy 留着；ARCHIVED.json；不写 STATE_PRUNED）；
     抽查的两道闸（假 hub 往 `HF_HOME/xet` 写字节模拟缓存增长）；`spot_pick` 加有最终 state 的情形。Mac 上 15 项通过，
     其中 3 项流程脚本测试要 GNU find，只在训练机上真跑。
2. 顺序（与训练计划交错）：
   1. 代码提交并同步到 mf4090 之后，把 `hf_archive.py`、`hf_archive_run.sh`、`hf_archive_report.py`、`test_hf_archive.py` 拷到 `runs/tools/`
      （同 10/1、10/8 的做法），在 mf4090 上跑全部测试，记下 md5（`results/ops/hf_archive_batch3_tests_mf4090.txt`）。
   2. 起训练链 t3p3a 之前生成清单（`plan` 在有训练链时拒绝）：
      `scripts/dev/record ops/hf_archive_batch3_plan_mf4090 scripts/dev/pipe-py tools/hf_archive.py plan --kind policy,state,final --keep 9 --out runs/hf_archive_batch3_manifest_mf4090.json`。
   3. README（`docs/hf/v2d-track2-archive/README.md`）加第 3 批，状态写“已上传、本地未删”，用 `readme` 子命令先传（`upload` 要求仓库有 README）。
   4. 起 t3p3a 之后，第一段：`tools/hf_remote.sh` 在 mf4090 上 setsid 后台运行 `timeout 7200 bash runs/tools/hf_archive_run.sh …`，
      `V2D_HF_ARCHIVE_STEPS=verify`、`V2D_HF_SPOTCHECK_PER_RUN=1`、`V2D_HF_SPOT_MIN_FREE_MB=1700`（每次下载后至少留 1700 MB，比链的 1200 MB 闸高 500 MB）、
      `V2D_HF_SPOT_MAX_CACHE_MB=50`，另设 `HF_XET_CHUNK_CACHE_SIZE_BYTES=0`（这一层是否生效没有验证，靠前面的闸兜底）。
      `timeout 7200`：2 小时还没到 HF_ARCHIVE_VERIFIED 就整组结束（审查 m5；`upload_large_folder` 出错时会一直重试），什么都不删，之后重跑同一命令续传。
      输出经 `grep --line-buffered -v -E '@|hf_[A-Za-z0-9]{20}'` 再写 `runs/logs/hf_archive_batch3_run.log`，输出前缀 `runs/hf_archive_batch3_mf4090`。
      与训练链同时运行，只占网络、CPU 与一次一个下载文件的磁盘（最大约 160 MB，核完就删）。
   5. 第一段跑完（或被停下）：日志（`results/ops/hf_archive_batch3_run_mf4090.txt`，含开始与结束时的 xet 缓存大小、可用空间）与汇总
      （`hf_archive_report.py`，`results/ops/hf_archive_batch3_results_mf4090.txt`）落盘，核对结论送 jev，报给用户并请求确认删除。
   6. 第二段：用户确认之后，等 t3p3a 整条链（训练、评测、导出门）结束、GPU 空闲，以 `V2D_HF_ARCHIVE_STEPS=delete` 和同一个输出前缀再运行
      （流程脚本在有训练链、GPU 进程、导出评测训练相关进程时会停）。删完把 README 的第 3 批改成“已删除”重新上传，然后起 t3p3b。
   7. 用户不同意删除：`rm -rf runs/hf_stage`（硬链接与上传缓存），仓库里的副本留着，本地什么都不删；t3p3b 另议。

## 判据（执行前登记）

- 开跑前：token 属于 Rongxuan-Zhou、权限 write，仓库私有（`whoami`）；生成清单时没有训练链在跑；流程脚本日志第一行的工具 md5
  与 mf4090 上测试记录里的相同。
- 清单与事实一致：policy 234 个、旧 state 3 个、最终 state 62 个，共 299 个文件、62 条 run、约 11.6 GB；
  9 条 policy run 各 26 份（步 10000384–260009984）。数字对不上就停下查原因，不改规则、不上传。
- 第一段：全部文件的大小与 sha256 一致（verify），每条 run 各抽 1 个下载后 sha256 一致（spotcheck）。有一个不一致就一个都不删，停下排查。
- 第一段期间：t3p3a 不因磁盘停链；抽查没有被两道闸停下；xet 缓存在日志第一行与 HF_ARCHIVE_VERIFIED 那一行的大小相差不超过 50 MB。
  被闸或 `timeout` 停下时什么都不删，报告原因，不改闸值重跑。
- 第二段只在用户确认后、t3p3a 整条链结束后运行。删除后：
  - 删除前重新核对全部一致；
  - `runs/flash_chord` 下消失的文件正好是清单里的：清单外消失 0 个，清单里没删的 0 个；
  - 可用空间增加约清单总字节数（±150 MB）；
  - 清单里的 run：最新一份 policy 的步数与删除前相同（第一段后与删除后的汇总各记一次；有一条 resumetest 只有 2 份 policy，不是 349999104 步），
    9 条 policy run 各剩 9 份、最新是 349999104 步，62 条 run 都剩 0 份 state；
  - 清单里的 62 条 run 都有 ARCHIVED.json，清单文件全部记进去；`runs/hf_stage` 已删除；
  - README 重新上传，HF_README_OK，仓库仍为私有。

## 风险

- 上传与抽查约 1.5 小时，与训练同时进行，占网络、CPU（22 核）与少量磁盘。
- HF 存储额度没查，超出时第一段停在上传，不删任何东西。
- 删掉最终 state 后，这 62 条 run 不能直接续训；需要时按 ARCHIVED.json 从 HF 下载（每份约 160 MB），本仓库的链本来也不续训。
- 以后若要从更早的 policy 导出，或对这 9 条 run 做按步数的诊断，要先从 HF 下载（第 2 批计划已说明）。
- huggingface_hub 提示 `upload_large_folder` 已弃用，但仍可用；中断后重跑同一命令可以续传。
- Mac 断开不影响：任务在服务器后台运行，日志在服务器上。

## 审查与处理（第 2 版）

Fable 5.1 独立审查（两份计划一起审）：GO WITH FIXES，没有 BLOCKER、MAJOR。审查确认：仓库里没有代码路径读有 DONE 的正式 run 的 state；
`cmd_delete` 在一条 run 混有 policy、旧 state、最终 state 时，保护集与 `keep_state`、`final_state` 都在删除前算好，导出要用的 policy 删不到；
清单数字（62 条 run、65 份 state = 62 + 3、234 份 policy）与记录一致；`plan` 必须在起链前跑、`delete` 在有链时停，顺序正确。

| 编号 | 级别 | 问题 | 处理 |
|---|---|---|---|
| m1 | MINOR | 判据“清单里的 run 最新一份 policy 仍是 349999104 步”对 resumetest（只有 2 份 policy）不成立 | 改为“与删除前相同”，349999104 只对 9 条 policy run 说 |
| m2 | MINOR | 9 条 policy run 的最终 state 被随机抽到的概率只有 1/27，而 verify 比的 sha256 是上传时客户端自报的 | `--per-run` 有最终 state 时固定抽它，再随机补 1 个；加测试 |
| m4 | MINOR | 缓存与磁盘只有事后判据，抽查下载可能在训练中途把盘撑满 | 抽查加两道闸（下载前留 1700 MB、xet 缓存涨 50 MB 就停），日志记开始与结束时的缓存大小；加测试 |
| m5 | MINOR | 第一段若卡住（上传出错一直重试），会拖到第 3、4 集开跑时 | 外面套 `timeout 7200`，到时整组结束，什么都不删 |
| m6 | MINOR | 两处数字：测试项数；“一条链只够 8 集”按公式是 8 到 9 集 | 改正 |

m3 属于训练计划，见 `agent-doc/plan-t3-v2-train10-2026-10-10.md`。

## 第 3 版：撞上私有存储额度之后（10/11 00:50 起草）

### 事实

- 00:31 第一段停在上传（HF_ARCHIVE_STOPPED upload，`results/ops/hf_archive_batch3_run_mf4090.txt`）：HF 的提交接口返回
  “Private storage limit reached for user Rongxuan-Zhou, please upgrade your plan to increase your private storage limit”，
  `upload_large_folder` 连续 8 次失败后退出。没有核对、抽查，什么都没删；t3p3a 照常在跑。
- 账号是免费账号（`isPro=False`）。私有仓库合计 99.96 GB，公开仓库合计 434.87 GB（`results/ops/hf_storage_1011_0040.txt`，
  `hf_archive.py storage` 逐个仓库查 usedStorage；第一次用列表接口查被 400 拒绝，`_run1` 留档）。本仓库 18.24 GB；
  另外两个大的私有仓库（61.66 GB、19.38 GB）不属于本项目，不动。
- 本仓库从 1393 个文件、12.82 GB 变成 1518 个、18.24 GB：撞上额度之前已经提交了一部分。`hubsubset`
  （`results/ops/hf_archive_batch3a_subset_mf4090.txt`）：清单 299 个里 125 个已在仓库且大小与 sha256 一致，最终 state 28 个、旧 state 3 个、
  policy 94 个（`t1-ep0-w2048-cap4m-r3a-mf4090` 16 个，`t1-ep5-w2048-cap4m-r3a-mf4090`、`t1-ep15-w2048-cap4m-r3a-s43-mf4090`、
  `t3-ep24-w2048-cap4m-r3a-mf4090` 各 26 个），共 5420591292 字节、28 条 run；不一致 0 个；仓库里没有的 174 个。
  子清单 `runs/hf_archive_batch3a_manifest_mf4090.json`，md5 `24a3e13278af54fef24d8e43f0dc9948`。
- 磁盘：t3p3a 4 集跑完时可用约 1.1 GB（起链 2617 MB 减 4 × 375 MB）。删掉这 125 个再腾出约 5.4 GB，第二段 6 集起链时要求可用 ≥ 3090 MB，够。

### 做法

1. 工具：`hf_archive.py` 加 `storage`（只读，逐个仓库查已用存储）与 `hubsubset`（只读，挑出清单里已在仓库且一致的行，仓库里有同路径但不一致的就退出码 1）；
   `hf_archive_run.sh` 加 `check` 步骤（核对与抽查，不上传，停在删除前）。测试 16 项在 mf4090 上全过（`results/ops/hf_archive_batch3a_tests_mf4090.txt`）。
   第一次在 mf4090 上跑时，删除步骤的测试被机器上真在跑的训练进程挡下（`_run1.txt.failed` 留档）：那道闸生效了，是测试不封闭。
   测试里加了假 pgrep，并补一条“有训练相关进程就停”的断言。
2. 第 3a 批第一段（只对已提交的 125 个）：`tools/hf_remote.sh` 在 mf4090 上 setsid 后台运行 `timeout 7200 bash runs/tools/hf_archive_run.sh`，
   `V2D_HF_ARCHIVE_STEPS=check`、`V2D_HF_SPOTCHECK_PER_RUN=1`、`V2D_HF_SPOT_MIN_FREE_MB=1700`、`V2D_HF_SPOT_MAX_CACHE_MB=50`、
   `HF_XET_CHUNK_CACHE_SIZE_BYTES=0`，清单用子清单，输出前缀 `runs/hf_archive_batch3a_mf4090`，日志 `runs/logs/hf_archive_batch3a_run.log`。
   抽查 28 份最终 state，另外 5 条有其他文件的 run（4 条 policy run 与 p185g）各随机 1 个，共 33 个、约 4.5 GB。
3. 报给用户，请用户定两件事：删不删这 125 个（第 3a 批）；其余 174 个怎么办（升级 HF、用户自己腾出私有空间、或者先不归档）。
4. README：改成“第 3 批计划 299 个，10/11 提交到 125 个（5.42 GB）时账号私有存储额度用完，本地副本尚未删除”，重新上传。
   README 的提交也可能因为额度被拒；被拒就记下，等额度问题解决后再传。
5. 用户确认删除后，等 t3p3a 整条链结束，用子清单与同一前缀以 `V2D_HF_ARCHIVE_STEPS=delete` 运行。没提交的 174 个本地文件不动。
   以后额度有了，用 `hubsubset --rest-out` 写出的第 3b 批清单 `runs/hf_archive_batch3b_manifest_mf4090.json`（174 行，6124514088 字节，
   md5 `28e156b9…`）上传。删过第 3a 批之后原来的 299 个清单不能再用来上传（`upload` 要给每一行建硬链接，删掉的文件建不了）。
6. 后备（审查 M1，现在登记）：check 若被“下载前可用不足”的闸停下，等 t3p3a 整条链结束（没有链要保护）后，用同一子清单、同一前缀、
   `V2D_HF_SPOT_MIN_FREE_MB=300` 再跑一次 check。1700 MB 的来由是比链的 1200 MB 闸高 500 MB，没有链在跑时这个理由不成立。
   这一条不算事后改闸；被缓存闸或 `timeout` 停下仍按原判据处理。

### 判据（第 3 版，执行前登记）

- check 之前与 README 重传之后各跑一次 `whoami`：HF_WHOAMI_OK，仓库仍为私有。
- check：125 / 125 一致（HF_VERIFY_OK）；抽查 33 个全部一致（HF_SPOTCHECK_OK）；没有被缓存闸或 `timeout` 停下（被下载前可用的闸停下按第 6 步重跑）；
  xet 缓存在日志第一行与 HF_ARCHIVE_VERIFIED 那一行相差不超过 50 MB；流程脚本结束后 `runs/hf_spotcheck` 不在。
- 删除只在用户确认、且 t3p3a 整条链结束后运行。删除后：删除前重新核对 125 / 125；`runs/flash_chord` 下消失的正好是子清单的 125 个
  （清单外 0 个、没删的 0 个）；可用空间增加约 5420591292 字节（±150 MB）；28 条 run 都有 ARCHIVED.json，125 个文件都记进去；
  28 条 run 各剩 0 份 state；4 条 policy run 最新一份 policy 仍是 349999104 步，`t1-ep0-w2048-cap4m-r3a-mf4090` 剩 19 份、其余 3 条各 9 份；
  `runs/hf_stage` 已删除；没提交的 174 个文件仍在本地。

### 审查与处理（第 3 版）

Fable 5.1 独立审查：GO WITH FIXES，没有 BLOCKER。审查确认：子清单只含 main 上已提交、大小与 sha256 一致的文件；check 一定跳过上传，
核对或抽查失败就停；t1-ep0 只删 16 份 policy 时，受保护的最新 9 份与 state 配对的 policy 都留着；125、28、33 与剩余份数的数字对；
删除步骤最后删掉整个暂存目录，5.42 GB 能真正释放。

| 编号 | 级别 | 问题 | 处理 |
|---|---|---|---|
| M1 | MAJOR | 训练在持续占盘，check 的“下载前可用 ≥ 1700 MB 加文件”约在 ep29 写第一份 state 后就再也满足不了；被闸停下后又不许改闸，t3p3b 会卡住 | 00:49 立即开跑；登记第 6 步后备：链结束后用 300 MB 重跑 |
| m2 | MINOR | “以后用原 299 个清单接着上传”在删过第 3a 批后不成立 | `hubsubset --rest-out` 写出第 3b 批清单（174 行）；改第 5 步说法；加测试 |
| m3 | MINOR | `timeout` 杀在抽查中途会留下下载到一半的文件 | 流程脚本加 `trap 'rm -rf runs/hf_spotcheck' EXIT`；加测试 |
| m4 | MINOR | 第 3 版判据少了“仓库仍为私有” | check 前（00:48，HF_WHOAMI_OK，私有）与 README 重传后各跑一次 whoami，写进判据 |

改后的工具（`hf_archive.py` md5 `fa0a4117…`、`hf_archive_run.sh` `281ab98b…`）在 mf4090 上 16 项测试全过
（`results/ops/hf_archive_batch3a_tests_mf4090.txt`；改前一版留作 `_v1`）。子清单用改后的工具重新生成，与改前逐字节相同（md5 `24a3e132…`）。

## 执行记录

### 第一段（10/10 23:54 起，UTC-6）

- 23:54 代码已同步到 mf4090（来历 17d6397），`runs/tools/` 下 4 个文件与仓库相同（`hf_archive.py` md5 `15ce9fd4…`、`hf_archive_run.sh` `164610ff…`）。
  测试在 mf4090 上全过：`test_hf_archive.py` 15 项（含 3 项流程脚本测试），`test_make_var_queue.py` 8 项（`results/ops/hf_archive_batch3_tests_mf4090.txt`）。
- 23:54 生成清单（`results/ops/hf_archive_batch3_plan_mf4090.txt`），当时没有训练链：policy 234 个（9 条 run 各 26 份，步 10000384–260009984）、
  旧 state 3 个（`t1-ep7-w2048-cap4m-p185g-mf4090` 的 320012288、330012672、340013056 步）、最终 state 62 个；共 299 个文件、62 条 run、
  11545105380 字节（11.55 GB）。清单 `runs/hf_archive_batch3_manifest_mf4090.json` 的 md5 是 `98f48b166bf8d17aa2ebbff5f9ac72a0`。与登记的数字一致。
- 23:57 t3p3a 起链（训练计划执行记录）。
- 23:57 README 加第 3 批（状态“尚未删除”）后上传，HF_README_OK；`whoami`：账号 Rongxuan-Zhou，token 权限 write，仓库私有，1393 个文件、12.82 GB
  （`results/ops/hf_readme_v2d_track2_archive_batch3.txt`）。
- 23:58 第一段开跑（`results/ops/hf_archive_batch3_launch_mf4090.txt`）：日志第一行的工具 md5 `15ce9fd4…` 与测试记录相同，清单 md5 `98f48b16…`、
  299 个文件；可用 2594 MB，xet 缓存 39 MB。
- 00:31 停在上传：账号私有存储额度用完（见第 3 版）。本仓库多了 125 个文件、5.42 GB；本地什么都没删。xet 缓存 00:35 是 64 MB（比开始多 25 MB）。

### 第 3a 批第一段（check，10/11 00:48 起）

- 00:48 子清单与第 3b 批清单（`results/ops/hf_archive_batch3a_subset_mf4090.txt`）：125 个一致、174 个仓库里没有、不一致 0 个；`whoami` HF_WHOAMI_OK，
  私有，1518 个文件、18.24 GB。
- 00:49 check 开跑（`results/ops/hf_archive_batch3a_launch_mf4090.txt`）：日志第一行的工具 md5 `fa0a4117…` 与测试记录相同，子清单 md5 `24a3e132…`、
  125 个文件；可用 2257 MB，xet 缓存 64 MB。
- 01:06 check 结束，HF_ARCHIVE_VERIFIED（`results/ops/hf_archive_batch3a_run_mf4090.txt`、汇总 `results/ops/hf_archive_batch3a_results_mf4090.txt`）：
  125 / 125 一致（HF_VERIFY_OK）；抽查 33 个全部一致（随机种子 1791701360，HF_SPOTCHECK_OK），即 28 条 run 各自的最后一份 state，
  另 4 份 policy 与 1 份旧 state；没有被闸或 `timeout` 停下。xet 缓存日志首行 64 MB、末行 65 MB；可用 2257 → 2224 MB；`runs/hf_spotcheck` 已不在。
  第 3 版 check 的判据全部满足。
- 本地：125 / 125 仍在，ARCHIVED.json 里记进去 0 / 125，`runs/hf_stage` 还在（299 个硬链接）。删除后每条 run 留下的 policy：26 条各 9 份、
  `resumetest-t1-ep20-cap1m-mf4090` 2 份（它的最后一份是 20000768 步）、`t1-ep0-w2048-cap4m-r3a-mf4090` 19 份，共 255 份，头部都完整；28 条 run 的 state 都会是 0 份。
- jev（`results/ops/jev_claims_hf_archive_batch3a.txt`，规格 `agent-doc/experiments/2026-10-11-hf-archive-batch3a.claims.json`）：7 条全部核实（0.84–0.98），
  3 道对照题正常。
- 01:10 README 改为“第 3 批提交到 125 个时额度用完，本地副本尚未删除”后重新上传，HF_README_OK；`whoami` HF_WHOAMI_OK，私有，1518 个文件、18.24 GB
  （`results/ops/hf_readme_v2d_track2_archive_batch3a.txt`）。
- 等用户定：第 3a 批（125 个、5.42 GB）删不删；第 3b 批（174 个、6.12 GB）怎么办。

### 用户 10/11 的回复与公开前的核对（10/11 03:20 前后）

- 用户回复：“可以删除 HF不需要private”。前半句回答第 3a 批（125 个文件、5.42 GB）的本地副本删不删：按第 3 版做法第 6 步，
  等 t3p3a 整条链（训练、评测、导出门）结束、GPU 空闲后，以 `V2D_HF_ARCHIVE_STEPS=delete`、子清单 `runs/hf_archive_batch3a_manifest_mf4090.json`、
  输出前缀 `runs/hf_archive_batch3a_mf4090` 运行；删完把 README 第 3 批的本地副本一栏改成已删除并重新上传，然后起 t3p3b。
- 后半句回答第 3b 批（174 个文件、6.12 GB）怎么办，即把归档仓库改为公开（公开仓库不占私有存储额度）。改之前核对了规则与文件内容：
  - 规则原文（`results/ops/kaggle_rules_sharing_1011.txt`，Track 2 Tier 3 MP-SR 与 Tier 1 AUC 两个比赛，Kaggle 附加规则的页面 sha256 相同）：
    Kaggle 附加规则“6. SUBMISSION CODE REQUIREMENTS”的 b 款（Public Code Sharing）允许公开分享 Competition Code，但要求分享在这个比赛的
    Kaggle 讨论区或 notebook 里；a 款把 Competition Code 定义为源代码或可执行代码，原文没有提到模型权重或 checkpoint。
    checkpoint 算不算 Competition Code，是我们的解读，组委会没有说过。
  - 比赛规则 2.7：外部数据须公开、所有参赛者免费可得，预训练模型按外部数据对待。解读：仓库公开后，其他队伍可以按这一条使用其中的权重。
  - 文件内容（`results/ops/ckpt_exposure_batch3_mf4090.txt`）：最终 state 含有同步数 policy 的全部张量（第 3a 批 28 / 28，第 3b 批 34 / 34），
    即仓库里已经有 28 条 run 的最终策略；文件头 metadata 没有凭据、邮箱、`/home` 路径与网址，有 W&B 的 entity 与 project。
  - jev（`results/ops/jev_claims_hf_public_check.txt`，规格 `agent-doc/experiments/2026-10-11-hf-public-check.claims.json`）：6 条全部核实（0.88–0.99），
    3 道对照题正常。第一轮（`_run1`）“最终 state 含有 policy”一条写进了记录里没有的上传状态，0.57，按记录改写后重跑。
- 仓库可见性暂不改动，先把以上情况报给用户确认。建议：仓库保持私有，第 3b 批暂时留在 mf4090（t3p3b 不依赖这部分空间），封榜（11/04）后再议公开。
  第 3b 批的上传、核对与删除，等用户回复后另行计划。

### 第 3a 批删除（10/11 09:21 起，UTC-6）

- 09:15 t3p3a 整条链结束（训练计划执行记录）。
- 09:21 删除，流程脚本删除前的三道闸（长链标记、GPU 上的进程、导出评测训练相关的进程）都没有拦下（`results/ops/hf_archive_batch3a_delete_launch_mf4090.txt`、`results/ops/hf_archive_batch3a_delete_run_mf4090.txt`）：流程脚本与工具的 md5
  （`281ab98b…`、`fa0a4117…`）与第 3 版测试过的相同，子清单 md5 `24a3e132…`、125 个文件。删除前重新核对 125 / 125 一致（HF_VERIFY_OK）；
  `runs/flash_chord` 删除前 4402 个文件、删除后 4281 个，消失 125 个，清单外 0 个、没删的 0 个（多出的 4 个应是第一次写入的 ARCHIVED.json：
  28 条 run 中正好 4 条只有 1 条记录）；可用 1126 → 6297 MB，增加 5171 MB（清单 5420591292 字节，即 5169 MB）；HF_ARCHIVE_DONE。
- 删除后的本地状态（`results/ops/hf_archive_batch3a_after_delete_mf4090.txt`）：清单里的文件还在本地的 0 / 125；28 条 run 各剩 0 份 state；
  ARCHIVED.json 记进去 125 / 125（28 条 run 按记录条数：1 条的 4 条、2 条的 15 条、3 条的 9 条）；留下的 policy 是 26 条各 9 份（最新 349999104 步）、
  `resumetest-t1-ep20-cap1m-mf4090` 2 份、`t1-ep0-w2048-cap4m-r3a-mf4090` 19 份，共 255 份，头部都完整；`runs/hf_stage` 不在。
  第 3b 批的 174 个文件仍在本地（`results/ops/hf_archive_batch3b_local_mf4090.txt`，174 / 174）。第 3 版的删除判据全部满足。
- 09:23 README 第 3 批的本地副本一栏改为“10/11 已删除（已提交的 125 个；没有上传的 174 个仍在训练机上）”，补第 3 批 ARCHIVED.json 的记录时间与
  删除前的重新核对，重新上传：HF_README_OK；`whoami` HF_WHOAMI_OK，私有，1518 个文件、18.24 GB
  （`results/ops/hf_readme_v2d_track2_archive_batch3a_deleted.txt`）。
- 09:26 t3p3b 起链（训练计划执行记录）。jev 与训练结果一起做（`results/t3p3/jev_claims_t3p3a_result.txt`），删除、README 与起链的 6 条都核实。
- 仓库可见性没有改动；第 3b 批（174 个、6.12 GB）的去向仍等用户回复。

## 第 4 版：用户同意公开之后（10/11 12:30 起草，UTC-6）

### 事实

- 用户 10/11 中午回复“可以公开”。此前（03:20 前后）已报告：Kaggle 附加规则 6.b 的原文、比赛规则 2.7、最终 state 含有同步数 policy 的全部张量
  （第 3a 批 28 / 28、第 3b 批 34 / 34）、文件头 metadata 含 W&B 的 entity 与 project，并建议保持私有、封榜后再议。用户看过这些之后决定公开。
- 仓库现状（09:23 `whoami`）：私有，1518 个文件，18.24 GB。账号是免费账号；00:40 私有合计 99.96 GB，其中本仓库 18.24 GB；
  公开合计 434.87 GB（`results/ops/hf_storage_1011_0040.txt`）。另外两个大的私有仓库不属于本项目，不动。
- 第 3b 批清单 `runs/hf_archive_batch3b_manifest_mf4090.json`：174 个文件、35 条 run、6124514088 字节，md5 `28e156b9…`；
  最终 state 34 个（5444115248 字节），policy 140 个（680398840 字节）；09:22 时 174 / 174 都在本地（`results/ops/hf_archive_batch3b_local_mf4090.txt`）。
  按 run 分：29 条只有最终 state，5 条有最终 state 与 26 份 policy，1 条只有 10 份 policy。
- mf4090 上的 huggingface_hub 是 1.32.0，`HfApi.update_repo_settings(repo_id, private=…, repo_type=…)` 可用。
- 工具（bb24477）：`whoami`、`readme`、`upload` 加 `--visibility private|public`（默认 private，仓库实际可见性不同就停或报 FAIL）；
  新增 `visibility` 子命令：只改本工具建的归档仓库（根目录有 README.md，且至少有一个 `<机器名>/runs/flash_chord/<run>/(state|policy)_<步数>.safetensors`），
  `--confirm` 必须与 `--repo` 相同，不加 `--yes` 只演习，已是目标可见性不重复改，改完重新读，对上才报 HF_VISIBILITY_OK。
  流程脚本把 `V2D_HF_VISIBILITY` 原样传给 `upload`。拷到 mf4090 的 `runs/tools/` 后 18 项测试全过，md5 与提交的一致
  （`results/ops/hf_archive_v4_tests_mf4090.txt`）。
- README（`docs/hf/v2d-track2-archive/README.md`）改成公开版：删掉“仓库为私有，不要改为公开”，写明 10/11 起公开；按比赛规则写明训练数据
  是比赛数据（公开发布的比赛数据按 CC BY 4.0 使用与分享）；第 3 批拆成 3a、3b 两行，3b 标明上传与核对完成后再更新；下载一节改为不需要 token；
  删掉私有代码仓库的网址，只保留仓库内的路径。
- 磁盘：12:2x 可用 5760 MB。t3p3c 4 集约用 1.5 GB，结束时约 4.2 GB。上传用硬链接，不多占盘；抽查一次下载一个文件，最大约 160 MB，比完就删。

### 做法

1. 改可见性之前先传公开版 README（`readme --visibility private`，此时仓库仍私有），让仓库公开的那一刻 README 已是公开版。
2. `whoami --visibility private`：HF_WHOAMI_OK。
3. `visibility --repo Rongxuan-Zhou/v2d-track2-archive --to public --confirm Rongxuan-Zhou/v2d-track2-archive` 先演习（HF_VISIBILITY_DRYRUN），
   再加 `--yes`（HF_VISIBILITY_OK）。
4. `whoami --visibility public`：HF_WHOAMI_OK，文件数与大小不变。`storage`：本仓库计入公开；私有合计约 99.96 − 18.24 = 81.72 GB。
5. 第 3b 批：`tools/hf_remote.sh` 在 mf4090 上 setsid 后台运行 `timeout 7200 bash runs/tools/hf_archive_run.sh`，清单用第 3b 批清单，
   仓库同上，机器名 mf4090，输出前缀 `runs/hf_archive_batch3b_mf4090`，日志 `runs/logs/hf_archive_batch3b_run.log`。环境：
   `V2D_HF_ARCHIVE_STEPS=verify`（上传、核对、抽查，停在删除前）、`V2D_HF_VISIBILITY=public`、`V2D_HF_SPOTCHECK_PER_RUN=1`、
   `V2D_HF_SPOT_MIN_FREE_MB=1700`、`V2D_HF_SPOT_MAX_CACHE_MB=50`、`HF_XET_CHUNK_CACHE_SIZE_BYTES=0`（与第 3a 批 check 相同的两道闸）。
   抽查 40 个：29 条只有最终 state 的 run 各 1 个，5 条有最终 state 与 policy 的 run 各 2 个（最终 state 加随机 1 份 policy），只有 policy 的 1 条 run 1 个。
   与 t3p3c 同时运行，同第 3a 批。
6. 第 3b 批核对、抽查通过后，README 的 3b 一行改为已提交，“校验”一节补第 3b 批的核对与抽查数字，`readme --visibility public` 重传，
   再跑一次 `whoami --visibility public`。
7. 报告用户。第 3b 批的本地副本这一版不删：删除要用户另行同意，且要等训练链都结束（删除步骤见到长链标记就停）。
8. 后备：抽查被“下载前可用不足”的闸停下时，等 t3p3c 整条链结束后，用同一清单、同一前缀、`V2D_HF_SPOT_MIN_FREE_MB=300`、
   `V2D_HF_ARCHIVE_STEPS=check` 重跑（同第 3 版第 6 步）。被缓存闸或 `timeout` 停下，或上传被拒（例如公开存储也有额度），就停下报告，不改闸、不重试。
   改公开之后若要改回私有，用同一子命令 `--to private`；已被下载或缓存的副本收不回来。

### 判据（第 4 版，执行前登记）

- 第 1–4 步：README 传完 HF_README_OK（下载回来 sha256 一致）；改之前 whoami 为私有；`visibility` 的演习不改动仓库，`--yes` 报 HF_VISIBILITY_OK；
  改后 whoami 为公开、HF_WHOAMI_OK，仍是 1518 个文件、18.24 GB；`storage` 里本仓库计入公开。任何一条不过就停，不传第 3b 批。
- 第 5 步：流程脚本日志第一行的工具 md5 与第 4 版最后一次在 mf4090 上测过的版本相同（`results/ops/hf_archive_v4_tests_mf4090.txt`），
  清单 174 个文件、md5 `28e156b9…`；HF_UPLOAD_DONE；核对 174 / 174（HF_VERIFY_OK）；抽查 40 / 40（HF_SPOTCHECK_OK），没有被抽查的两道闸停下
  （缓存闸只算抽查期间的增长）；最后一行 HF_ARCHIVE_VERIFIED；流程脚本结束后 `runs/hf_spotcheck` 不在；本地 `runs/flash_chord` 下
  第 3b 批的 174 个文件都还在；同时在跑的 t3p3c 训练链没有因磁盘停链。日志第一行到 HF_ARCHIVE_VERIFIED 那一行的 xet 缓存增长只报：
  这次含上传（第 3 批第一段上传 5.42 GB 时缓存 39 → 64 MB），这一版也不删除。
- 第 6 步：HF_README_OK；whoami 公开、HF_WHOAMI_OK，1692 个文件，约 24.36 GB（18.24 + 6.12）。

### 审查与处理（第 4 版）

Fable 5.1 独立审查：GO WITH FIXES，没有 BLOCKER、MAJOR。审查确认：`visibility` 不加 `--yes` 不调修改接口，`--confirm` 与归档仓库的结构两道闸都有测试；
默认 `--visibility private` 时 whoami、readme、upload 与流程脚本的行为与改前相同；公开版 README 在仓库仍私有时上传，翻转那一刻没有不实的说法，
没有 token、`/home` 路径与网址；40、174、1692、24.36 GB 与记录和抽查规则一致；磁盘余量够 t3p3c 与抽查同时进行。

| 编号 | 级别 | 问题 | 处理 |
|---|---|---|---|
| m1 | MINOR | 判据少了前几版都有的两条：流程脚本日志首行的工具与清单 md5、t3p3c 不因磁盘停链 | 补进第 5 步判据 |
| m2 | MINOR | “xet 缓存首尾相差 ≤ 50 MB”这次含上传，第一段上传 5.42 GB 时就涨了 25 MB，余量不到一倍 | 改为只报；抽查期间的缓存闸照旧 50 MB |
| m3 | MINOR | `readme --visibility public` 遇到不存在的仓库会新建公开仓库，仓库名写错就多出一个公开仓库；没有测试 | `readme` 遇到这种情况就停，不新建公开仓库；加测试 |
| m4 | MINOR | 公开版 README 没有 `license`，HF 页面会显示没有许可；正文只写了比赛数据按 CC BY 4.0 | 许可条款由用户定（待定），这一版不加 |

### 第 4 版执行（10/11 12:35 起，UTC-6）

- 改后的工具（`hf_archive.py` md5 `3ef5989f…`，`hf_archive_run.sh` `acb54bf5…`，测试 `f8c19898…`）拷到 mf4090 的 `runs/tools/`，18 项测试全过
  （`results/ops/hf_archive_v4_tests_mf4090.txt`）。同步后仓库里的 `tools/hf_archive.py` 与 `runs/tools/` 的 md5 相同。
- 12:37 公开版 README（md5 `9f7c9f90…`）在仓库仍私有时上传：HF_README_OK；whoami 私有、1518 个文件、18.24 GB、HF_WHOAMI_OK
  （`results/ops/hf_readme_v2d_track2_archive_public1.txt`）。
- 12:38 `visibility` 演习：现在私有，1518 个文件，其中归档文件 1516 个，HF_VISIBILITY_DRYRUN（`results/ops/hf_visibility_dryrun_1011.txt`）。
- 12:38 加 `--yes`：重新读到公开，HF_VISIBILITY_OK；whoami 公开、1518 个文件、18.24 GB、HF_WHOAMI_OK；`storage`：本仓库计入公开，
  私有合计 81.73 GB（预期约 81.72），公开合计 453.11 GB（434.87 + 18.24）（`results/ops/hf_visibility_public_1011.txt`）。第 1–4 步的判据都满足。
- 12:38 第 3b 批起跑（`results/ops/hf_archive_batch3b_launch_mf4090.txt`）：日志第一行的工具 md5 `3ef5989f…`、清单 174 个文件、md5 `28e156b9…`，
  可见性 public，可用 5820 MB，xet 缓存 65 MB；开始上传 174 个文件到公开仓库（6.12 GB）。
- 12:39 上传结束，用时 0.4 分钟（HF_UPLOAD_DONE）。这么快的原因没有核实；推测是 10/11 00:31 第一段撞上额度之前，这些文件的数据块已经传上去，
  只是提交被拒。核对 174 / 174 一致（HF_VERIFY_OK）；抽查 40 个，40 个一致（HF_SPOTCHECK_OK，随机种子 1791743981，覆盖 35 条 run）；
  12:58 写 HF_ARCHIVE_VERIFIED，停在删除前，可用 4797 MB（`results/ops/hf_archive_batch3b_run_mf4090.txt`）。xet 缓存 65 → 77 MB（只报，m2）；
  抽查的缓存闸从抽查开始时的 75 MB 算，没有触发。`runs/hf_spotcheck` 不在。
- 核对后的本地状态（`results/ops/hf_archive_batch3b_verified_mf4090.txt`）：清单里的 174 个文件还在本地 174 / 174；记进 ARCHIVED.json 0 / 174；
  暂存目录 `runs/hf_stage` 里是这 174 个文件的硬链接（删除步骤最后清掉）；可用 3857 MB。t3p3c 的训练日志里没有“磁盘只剩”的停链行。
- 13:5x README 的 3b 一行改为已提交，“校验”一节补第 3b 批的数字（md5 `c956c8c1…`），经 `runs/hf_readme/` 上传（有长链标记，不能同步）：
  HF_README_OK；whoami 公开、1692 个文件、24.36 GB、HF_WHOAMI_OK（`results/ops/hf_readme_v2d_track2_archive_public2.txt`）。第 4 版的判据全部满足。
- jev（`results/t3simreg/jev_claims_hf_public_simreg.txt`，规格 `agent-doc/experiments/2026-10-11-hf-public-simreg.claims.json`）：13 条全部核实（0.86–0.99），
  4 道对照题正常。第一轮（`_run1.txt.failed`）真对照题 0.42：证据截取只留了 ep0、ep12 两个集标题，其余各集的行混在 ep12 下面；
  截取改为保留所有集标题后重跑，主张与对照题都没改。
- 第 3b 批本地副本的删除等用户确认，且要等 mf4090 上的训练链都结束。
