# 计划：t3p4a 结束后在 mf4090 上自动接续第 4 批删除与 t3p4b 起链（2026-10-13，第 2 版：按 Fable 5.1 审查修改）

依据：`agent-doc/plan-d-t3hm-train-2026-10-12.md` 第 3 节第 6 步（“`t3p4a` 结束 → 拉回结果、健康记录、评测表 → 第 4 批删除（用户同意时）→ `t3p4b` 的三道核对与起链”）
与 `agent-doc/plan-hf-archive-batch4-2026-10-12.md` 第 2 节第 6 步、第 3 节的判据。这一版只把这两步的执行时机从“早上有人接手时”改成“`t3p4a` 一结束就在服务器上接着做”，
判据一条不放宽；`t3p4b` 起链前另加“`t3p4a` 全部做完”一道。时间一律 UTC−6（MDT），服务器日志是 CST（+14 小时）。第 1 版经 Fable 5.1 独立审查
（GO WITH FIXES：1 条 MAJOR、5 条 MINOR、6 条 NIT），逐条处理见文末。

## 1. 事实

- **用户同意删除**：10/13 00:09 前后用户回复“确认过HF和本地一样的就可以删”。这条只覆盖已上传到 HF 的第 4 批（297 个文件、3,151,293,348 字节，即 3005 MiB）；
  第一轮 `tier3_dlv` 的产物（1925 MB）不在 HF 上，不在这条同意之内，不删。
- **`t3p4a` 进度**（`results/t3p4/status_mf4090_1013_0018.txt`，00:12）：ep15、ep17 训完；ep1 到 300011520 步（14:12:13 CST）；ep2、ep3 未开始；
  长链标记 3 个（训练、评测、导出门）；可用 1862 MB。每条正式训练 118–135 分钟（ep15 134、ep17 118；ep1 按 90003456 → 300011520 步用时 75.7 分钟推算约 126）。
  估计 ep1 00:30、ep2 02:40、ep3 04:50 训完，评测与导出约 05:15–05:45 结束（估计）。
- **ep3 不会被磁盘闸挡下**（未落盘的临时查看，00:20 的 `du -sm`）：在训的 ep1 目录 483 MB，训完的 ep15、ep17 各 360 MB，在训时多出约 120 MB，训完缩回。
  按 360 MB 一条推算，ep3 开跑前约剩 1.6 GB，高于每条开跑前 1200 MB 的闸；即便估错，链自己的闸也会挡住，不会写满盘。`t3p4a` 全部结束后约剩 1.25 GB。
- **删除只能等 `t3p4a` 结束**：`tools/hf_archive_run.sh` 第 56–60 行在删除前查三道闸（任何 `runs/.chain-active-*`、GPU 上的计算进程、
  导出评测训练相关的进程），任何一道不过就停。第 4 批计划第 2 节第 6 步也写明“没有训练链、GPU 空闲时”。
- **起 `t3p4b` 的闸**（`stages/policy/arm_var_chain.sh`）：GPU 型号、来历干净、三段日志与标记与会话都不存在、GPU 上没有进程、可用 ≥ 2500 MB、
  两份 `fc_src` 副本在且核对通过、配置展开的 yaml 都在且配方断言全过、`precheck_expect.sh` 全过。删除前约 1.25 GB，删除后约 4.2 GB。
- **结局行的格式**：训练链最后一行 `DAY2_TRAIN_DONE（完成 x、失败 y、跳过 z、发散 v）`，显存不足、崩溃、发散、冒烟没过都照样写 DONE，只是计数不同
  （`stages/policy/day2_train_chain.sh` 第 101–149 行）；评测链 `DAY2_EVAL_DONE（成功 x、失败 y）`；导出门过了才跑导出链，导出链最后一行
  `EXPORT_CHAIN_DONE（成功 x、失败 y）`（`stages/evaluate/export_chain.sh` 第 198 行），日志 `runs/logs/cand_t3_t3p4a_mf4090.log`。
- **配置展开不占 GPU**：`stages/policy/fc_config_check.sh` 经 `scripts/dev/in-flash-chord` 起容器，只有 `V2D_GPU=1` 时才加 `--gpus`
  （`scripts/dev/in-flash-chord` 第 23 行）。mf4090 内存 114 GB、可用 106 GB，22 核，负载 1.0（00:21，未落盘的临时查看）。
- **代码一致**：mf4090 的来历是 a629fbdbf3e5；`git diff --stat a629fbd..HEAD -- stages tools scripts libs third_party deploy` 在本计划提交前为空。
  本计划提交后，两边只差新加的四个文件（两个脚本、两份测试），它们按 md5 复制到 mf4090 的 `runs/tools/`，不经同步；`t3p4b` 用的队列与脚本仍是服务器上的 a629fbd。
- **不接续的代价**：07:00 的 SOP 定时任务不同步、不起链；删除与 `t3p4b` 要等下一次交互。D 计划第 6 节估 `t3p4b` 08:30 起，mf4090 约空 2.5–3 小时，交互更晚就空得更久。
- **先例**：`stages/policy/queue_after.sh` 在链运行期间把新脚本复制到 `runs/tools/` 再跑，复制时记 md5，不同步仓库；第 3b 批的删除与第 4 批的第一段都经
  `tools/hf_remote.sh` 由 stdin 注入凭据、`setsid nohup` 后台跑，输出滤掉含 `@` 或 token 样式的行。
- **tmux**：mf4090 上 rxzhou 的 tmux 服务从 9/28 起一直在（会话 `v2d-train`），新会话用它的全局环境；它的全局环境里 `HF_TOKEN` 0 条（00:40 查）。

## 2. 做法

0. 代码（附测试，Mac 上全过，与本计划一起提交）：
   - `tools/hf_archive_delete_checked.sh`：第 4 批计划第 2 节第 6 步的三小步串成一条命令：`hf_archive.py verify`（写 `.precheck.json`，要 HF_VERIFY_OK）→
     演习（`delete` 不加 `--yes`，“将删”行数等于清单文件数、“跳过” 0 行）→ `V2D_HF_ARCHIVE_STEPS=delete` 跑 `hf_archive_run.sh`（最后一行 HF_ARCHIVE_DONE，
     “其中没删的 0 个”且“清单外消失的文件：无”，可用空间的增加与清单的 3005 MiB 相差不超过 50）→ `hf_archive_report.py`。三步的输出边跑边落盘
     （`runs/hf_archive_batch4_mf4090.precheck.log`、`.dryrun.log`、`runs/logs/hf_archive_batch4_mf4090_delete.log`），任何一步不过就停，后面不跑；
     删除日志已存在就不做。测试 `tools/test_hf_archive_delete_checked.py`（6 组）。
   - `stages/policy/arm_after.sh`：记下来历与 `t3p4b` 队列的 md5 → 等 `runs/.chain-active-*` 全部消失、训练与评测日志写完最后一行 → 等卡空、没有导出评测训练相关的进程
     （最多约 2 小时）→ 跑前置命令（上一条，限时 1 小时），退出码 0 才往下；前置命令不看 `t3p4a` 的结局 → 查 `t3p4a` 全部做完（训练 `完成 5、失败 0、跳过 0、发散 0`，
     评测 `失败 0`，导出 `成功 5、失败 0`）→ 来历与队列没变 → 去掉环境里的 HF 凭据、代理与前置命令 → `V2D_ARM_DRYRUN=1 arm_var_chain.sh t3p4b` 得 DRYRUN_OK
     后再 `arm_var_chain.sh t3p4b`，要 ARMED。本脚本不写长链标记（删除一步见到任何标记都会停）。测试 `stages/policy/test_arm_after.py`（8 组）。
1. `t3p4b` 的配置展开（已做，00:24，不占 GPU）：`results/t3p4/cfgcheck_t3p4b_mf4090.txt`。
2. 把两个脚本与两份测试经 ssh 的 stdin 复制到 mf4090 的 `runs/tools/`（不同步仓库），两端 md5 对比，在 mf4090 上跑两份测试（bash 5）
   （`results/t3p4/arm_after_deploy_mf4090.txt`）。
3. 经 `tools/hf_remote.sh` 后台起接续（`results/t3p4/arm_after_launch_mf4090.txt`），写法同第 4 批第一段的起法（`V2D_PRE_CMD` 用单引号、`bash -c` 里用双引号）：
   `V2D_PRE_CMD='V2D_HF_VISIBILITY=public bash runs/tools/hf_archive_delete_checked.sh runs/hf_archive_batch4_manifest_mf4090.json Rongxuan-Zhou/v2d-track2-archive
   mf4090 runs/hf_archive_batch4_mf4090' setsid nohup bash -c 'bash runs/tools/arm_after.sh t3p4b runs/logs/t3p4a_train_mf4090.log runs/logs/t3p4a_eval_mf4090.log
   runs/logs/cand_t3_t3p4a_mf4090.log 5 2>&1 | grep --line-buffered -v -E "@|hf_[A-Za-z0-9]{20}" > runs/logs/arm_after_t3p4b_mf4090.log' < /dev/null > /dev/null 2>&1 &`。
   起完核对：日志第二行的前置命令与上面一字不差；进程在；tmux 全局环境里 `HF_TOKEN` 0 条（只数条数，不打印值）。之后到它结束前不同步 mf4090。
4. 早上（07:00 的 SOP 任务或下一次交互）：拉回接续日志与删除日志（`results/ops/hf_archive_batch4_delete_run_mf4090.txt`），跑删除后的报告
   （`results/ops/hf_archive_batch4_after_delete_mf4090.txt`）；`t3p4a` 的结果、健康记录、评测表；README 第 4 批改“已删除”并重传；jev；执行记录；提交。

## 3. 判据（执行前登记）

- **代码**：两份测试在 Mac 与 mf4090 上都全过；复制到 mf4090 的四个文件 md5 与提交的相同。
- **配置展开**（已满足）：16 份配置（8 条正式、8 条冒烟）每份“意外 0 个”；只有地面的 ep12、14、19、21（冒烟与正式共 8 份）有
  “允许 scene.support: 配方=True → 本次=False”；有桌面的 ep13、16、25、27 没有这一行。
- **开始删除的条件**：长链标记一个都没有；`t3p4a` 训练日志与评测日志都写完最后一行（DONE 或 FAILED）；GPU 上没有计算进程，也没有导出评测训练相关的进程。
  删除不看 `t3p4a` 的结局。
- **删除**：照第 4 批计划第 3 节：HF_VERIFY_OK；演习“将删”297 个、“跳过”0 个；HF_ARCHIVE_DONE，“其中没删的 0 个”、“清单外消失的文件：无”；
  可用空间的增加与 3005 MiB 相差不超过 50 MB。早上按删除后的报告再核：每条 run 剩 9 份 policy、0 份 state，DONE 与日志都在。
- **起链的条件**：删除做完；`t3p4a` 训练 `DAY2_TRAIN_DONE（完成 5、失败 0、跳过 0、发散 0）`、评测 `DAY2_EVAL_DONE（成功 N、失败 0）`（N ≥ 1）、
  导出 `EXPORT_CHAIN_DONE（成功 5、失败 0）`；来历与 `t3p4b` 队列的 md5 与起接续时相同；DRYRUN_OK，然后 ARMED；预演打印的命令里训练挂 `v040_p185_nfg`、
  评测与导出挂 `fc_8c778f9`（早上从日志核）；`arm_var_chain.sh` 自己的闸全过。
- **停**：任何一项不过，接续就停（最后一行 ARM_AFTER_STOPPED 或 HF_DELETE_CHECKED_STOPPED），后面的步骤不做；不放宽闸、不自动重试，早上查原因再定。

## 4. 风险与限制

- `t3p4b` 起链时还没人看过 `t3p4a` 的评测数字。D 计划把“跟上/没跟上”定为只报，所以它不挡 `t3p4b`；训练、评测、导出有任何失败则挡（第 3 节）。
  早上若发现系统性问题，建 `runs/.chain-stop-t3p4b_train_mf4090` 停链（剩下的冒烟与正式都不开，已完成的照常评测），最多损失几小时。
- HF 凭据在接续进程的环境里最多停留约 6–12 小时（与第 3b、4 批的后台进程相同，只经环境变量）。起链前去掉凭据与代理；新会话用的是 tmux 服务的全局环境，
  起接续时已核过其中没有 `HF_TOKEN`。
- 接续不写长链标记，挡不住同步；这期间不同步 mf4090，起链前再核来历与队列的 md5，变了就不起。
- 前置命令限时 1 小时：HF 接口卡住时到点杀掉，接续停下、不起链。杀在 `delete --yes` 途中时，已删的每个文件都是删前重算过 sha256 且仓库里有的，
  `runs/hf_stage` 的硬链接可能留下；早上看删除日志与报告收尾。
- 长链标记残留（链已结束、标记还在）：接续最多等 12 小时后停，不删不起。
- `t3p4a` 结束后有别人的进程占卡：最多等 2 小时后停，早上手动做。删除与起链之间被别人占卡：预演或起链停下，删除已经做完，早上再起。
- Mac 离线不影响（全在服务器上）。时长与时刻都是估计。

## 5. 不在本计划

- ml40：B（t2xb）估计 07:00–07:30 结束。Tier 3 数据转发见 D 计划第 8 节；同步 ml40 与 `t3qa` 起链按 D 计划第 7、9 步做，不在这次接续里。
- `tier3_dlv` 的删除仍待用户决定。

## 6. 时间（估计）

复制与测试约 5 分钟；起接续约 2 分钟。`t3p4a` 约 05:15–05:45 结束；删除前核对、演习、删除约 15 分钟；预演与起链约 5 分钟；`t3p4b` 约 06:00–06:15 起，
8 集约 19 小时，10/14 01:00 前后结束。

## 审查与处理（第 2 版）

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| M1 | MAJOR | 起链只看训练、评测日志最后一行是不是 DONE，不看计数；显存不足、崩溃、发散照样写 DONE，评测可能有失败，导出门可能停；D 计划第 4 节“每集”与“停”被绕过 | 采纳：前置命令（删除）之后、预演之前查训练 `完成 5、失败 0、跳过 0、发散 0`、评测 `失败 0`、导出 `成功 5、失败 0`，不过只删不起；测试补 8 种结局 |
| m2 | MINOR | 前置命令不限时，HF 接口卡住会整夜挂着、不报 | 采纳：`timeout 3600`；杀在删除途中的后果写进第 4 节 |
| m3 | MINOR | 实际删除时有文件被跳过也算 DONE；“每条 run 剩 9 份”“可用空间 ±50 MB”推到早上，那时 `t3p4b` 已起 | 采纳：删除一步另要“其中没删的 0 个”“清单外消失的文件：无”、可用空间增加与清单 3005 MiB 相差不超过 50；每条 run 的剩余份数仍在早上按报告核（不挡起链：删除只动清单里的文件） |
| m4 | MINOR | 每步输出先进变量、结束才打印，中途被杀没有记录 | 采纳：三步都边跑边 `tee` 落盘，删除日志 `runs/logs/hf_archive_batch4_mf4090_delete.log` |
| m5 | MINOR | 等待期间没有标记挡同步，起链前也不再核来历，同步过的话会用与配置展开不同的代码起链 | 采纳：起接续时记来历与 `t3p4b` 队列、导出清单的 md5，起链前再比，变了就停；测试补一例 |
| m6 | MINOR | 测试缺：评测 FAILED、非 GPU 的忙进程、nvidia-smi 出错、卡忙后空出、日志最后一行晚到、代理变量清掉的断言；删除一步非 0 退出、演习自己退出、FILES_CHECK_FAILED、“将删”多于清单 | 采纳：全部补上（删除 6 组、接续 8 组） |
| n1 | NIT | “第 3b、4 批的删除”——第 4 批还没删 | 采纳：改成“第 3b 批的删除与第 4 批的第一段” |
| n2 | NIT | 483/360 MB 与内存负载没有落盘记录 | 采纳：标为“未落盘的临时查看”，注明不是判据（链自己的 1200 MB 闸兜底） |
| n3 | NIT | 起法的引号嵌套写不出来，写错会改掉前置命令 | 采纳：照第 4 批第一段的写法；起完核对日志里的前置命令一字不差 |
| n4 | NIT | 只查了 `.spotcheck.json`，没查 `.verified.json`；报告失败也写 DONE | 采纳：两个都查；报告的退出码记进日志（报告只报，不挡） |
| n5 | NIT | 提交后 HEAD 与 a629fbd 差四个新文件，早上“与 Mac 上提交的相同”会被误读 | 采纳：第 1 节写明 |
| n6 | NIT | 去掉凭据只在本脚本起 tmux 服务时有效；已有服务时新会话用它的全局环境 | 采纳：查过 tmux 全局环境里 `HF_TOKEN` 0 条；起接续时再查一次并记录（只数条数） |
