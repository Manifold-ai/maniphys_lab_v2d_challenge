# 计划：mf4090 第 3 批归档到 Hugging Face（policy 中间份、旧 state、最终 state），核对后删除（2026-10-10，第 2 版：按 Fable 5.1 审查修改）

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

## 执行记录

（待执行）
