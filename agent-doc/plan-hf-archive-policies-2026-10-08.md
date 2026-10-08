# 计划：mf4090 的 policy 中间份归档到 Hugging Face，核对后删除（2026-10-08，第 2 版：按 Fable 5.1 审查修改）

用户 10/8 的要求：“按照你的建议执行： 把 policy 的中间份归档到 HF，每条 run 留最新 9 份（最后一份加上导出最多回退的 8 份）。”
我给出的建议还包括“删之前照例再问你”，所以这次分两段执行：上传、核对、抽查之后停下，用户确认后再删除。时间一律为 UTC-6。

## 事实

- 磁盘：mf4090 系统盘 10/8 09:09 可用 1678 MB（`results/ops/mf4090_disk_1008.txt`）。若 Tier 1 在 mf4090 上再训 8 条，
  约需 2.2 GB（每条约 0.33 GB），链的磁盘下限是 1200 MB（`V2D_MIN_FREE_MB`）。
- 按 10/1 的 state 规则，这次只挑出 3 份、0.48 GB（`results/ops/hf_archive_plan_mf4090_1008.txt`）。
- policy：`runs/flash_chord` 下共 1903 份、8.8 GB（`du -m` 计）。`stages/policy/fc_run.sh` 保留全部 `policy_*`，
  跑完的正式 run 每条 35 份。
- 用到 policy 的地方：
  - 导出（`stages/evaluate/export_chain.sh`）用导出清单里的步数（取最新一份）；评测器报 must disable task failure termination 时，
    按步数从大到小往前退，最多 `V2D_FALLBACK_MAX` 份，默认 8（第 174–192 行）。
  - `stages/policy/fc_eval.sh`、`chain_status_remote.sh` 取最新一份；`check_export.py`、`trial_verdict.py`、`submission_check_remote.sh` 按给定步数读。
  - `stages/policy/ckpt_latest.py`（续训、冒烟判定）要求 state 与同步数的 policy 成对完整。
  - `ckpt_nonfinite.py` 在导出时只查要导出的那一步（`fc_export.sh`），训练时看守正在跑的 run（`fc_run_watched.sh`）；
    扫一条老 run 全部 policy 的只有诊断用法。`run_pace.py` 按 policy 的落盘时间看训练节奏；`nfg_train_inject.py` 只扫它自己的输出目录。
    归档后，对老 run 做这两种诊断只能看到剩下的 9 份。
  - `ep7_ckpt_eval.sh` 评过方盒两条发散 run 的中间 checkpoint：`t1-ep7-w2048-cap4m-p185-mf4090` 没有 DONE，这次不动；
    `t2-ep7-w2048-cap10m-p185-ml40` 在 ml40 上。
- 导出记录：`runs/exports/*.tsv` 共 4 个（`export_mf4090`、`export2_mf4090`、`cand_t1_1008`、`cand_t1_1008b`），
  导出过的步数全是 349999104，即最后一步；导出输入清单 `stages/evaluate/exports/*.tsv` 里的步数也都是 349999104。
- 没有训练链在跑（`runs/.chain-active-*` 0 个），`runs/hf_stage` 不存在（`results/ops/mf4090_runs_layout_1008.txt`）。
- 没有 DONE 的 run 有 7 条（如 `t1-ep7-w2048-cap4m-p185-mf4090` 有 15 份 policy、`t1-ep28-w2048-cap4m-mf4090` 有 6 份），这次不动。
- 演习（`results/ops/hf_archive_policy_plan_mf4090.txt`）：有 DONE 且 policy 多于 9 份的 run 共 52 条（Tier 1 37 条、Tier 2 14 条、
  ctrl-snackbox 1 条），每条 35 份。每条挑 26 份（步 10000384–260009984），留最新 9 份（步 270010368–349999104）。
  没有落在最新 9 份之外的 state、导出步数或 STATE_PRUNED 步数。共 1352 个文件、6.57 GB；清单是 mf4090 上的
  `runs/hf_archive_policy_manifest_mf4090.json`（md5 `eb895d8479c43e7ebc6842441675922e`），每个文件记了大小与 sha256。
  第 2 版工具（`tools/hf_archive.py` md5 `027ed7885644289e667b1bdd985e8d98`）重做的演习结果与第 1 版逐字节相同。
- 52 条 run 里已有 `ARCHIVED.json` 的 19 条（10/1 归档 state 时写的），全机带 `ARCHIVED.json` 的 run 共 38 条。
- 开跑前（`results/ops/hf_archive_policy_precheck_mf4090.txt`）：长链标记 0 个，GPU 进程 0 个，`runs/hf_stage` 不存在，可用 1670 MB。
- 凭据与路线：token 有效，账号 Rongxuan-Zhou，权限 write；仓库 `Rongxuan-Zhou/v2d-track2-archive` 是私有的，
  现有 40 个文件、6.24 GB（`results/ops/hf_whoami_mf4090_1008.txt`）。上传经 `V2D_PROXY`；10/1 实测约 4 MB/s，6.24 GB 用了 17.6 分钟。
- HF 私有仓库的存储额度没有查；超出时上传会报错，不会删除任何东西。

## 做法

1. 工具（`tools/hf_archive.py`）：
   - 新增 `plan --kind policy --keep 9`。只看有 DONE 的 run（名字含 `t2-` 的也算，Tier 2 第 1 批早已跑完），有训练链在跑就不做。
     每条 run 留下步数最大的 9 份，以及有 state 的步数、`runs/exports/*.tsv` 里导出过的步数、STATE_PRUNED 记的步数；
     步数最大的那份 policy 不完整时，整条 run 不动。
   - `delete` 处理 policy 行：删除时按当时的文件重算保护集；有训练链在跑就一个都不删；`ARCHIVED.json` 追加，不覆盖 10/1 的记录；
     STATE_PRUNED 只在清单里有 state 时才写。
   - 保护集同时读导出结果表 `runs/exports/*.tsv` 与导出输入清单 `stages/evaluate/exports/*.tsv`。
   - `spotcheck --per-run`：每条 run 随机下载 1 个文件回来重算 sha256。
   - 新增 `whoami`：查 token 的账号与权限、仓库是否私有、仓库里现有多少文件。
2. 流程脚本（`tools/hf_archive_run.sh`）：新增 `V2D_HF_ARCHIVE_STEPS`（`all` 默认、`verify`、`delete`）、`V2D_HF_SPOTCHECK_N`
   与 `V2D_HF_SPOTCHECK_PER_RUN`。第一行打印工具与清单的 md5。`delete` 步骤先重新核对一遍仓库（`.reverified.json`），再按它删除。
   删除前遇到这几种情况就停：有训练链在跑、GPU 上有进程、有 fc_export、fc_eval、fc_run、export_chain、case_clip 进程
   （它们会删 `runs/flash_chord` 下的临时文件，让全量比对误报）。删除前后比对 `runs/flash_chord` 下的全部文件，
   消失的只能是清单里的文件，并报出清单里没删掉的个数（原来只比对 t2 目录，那是给 10/1 训练同时在跑的情况用的）。
3. 凭据（`tools/hf_remote.sh`）：把 10/1 手敲的做法写成脚本，从 `.env` 读 `HF_TOKEN` 与 `V2D_PROXY`，经 ssh 的 stdin 传过去，
   远端 export 后执行命令，`HF_ENDPOINT` 固定为 https://huggingface.co，输出里含 `@` 或 token 样式的行一律滤掉。
4. 测试（`tools/test_hf_archive.py`）新增 8 项：policy 挑选规则、删除的各道闸与效果、最新一份坏了整条跳过、导出输入清单的保护、
   按 run 抽查的挑法，以及流程脚本的 verify 步骤、delete 步骤（缺核对结果、有训练链、GPU 上有进程都停，正常时先重新核对再删）、
   多删一个清单外文件时全量比对报错。流程脚本的测试用桩工具代替上传与核对，用假 nvidia-smi 控制 GPU 检查。
   在 mf4090 上用最终版 11 项全过（`results/ops/hf_archive_policy_tests_mf4090.txt`，三个文件的 md5 记在开头）。
5. 第一段：用 `tools/hf_remote.sh` 在 mf4090 上 setsid 后台运行 `hf_archive_run.sh`，`V2D_HF_ARCHIVE_STEPS=verify`、
   `V2D_HF_SPOTCHECK_PER_RUN=1`（52 个文件，约 250 MB）。流程脚本的输出先经 `grep --line-buffered -v -E '@|hf_[A-Za-z0-9]{20}'`
   再写进 `runs/logs/hf_archive_policy_run.log`，服务器上的日志也不留代理地址与 token。输出前缀 `runs/hf_archive_policy_mf4090`。
   `upload_large_folder` 出错时会一直重试而不退出，所以要看日志时间有没有往前走，不能只等结束标记。
   仓库内路径为 `mf4090/runs/flash_chord/<run>/policy_<步数>.safetensors`。
6. 第一段跑完后，日志（去掉含 `@` 与 token 样式的行）落盘到 `results/ops/`，核对结论送 jev，然后向用户报告并请求确认删除。
7. 第二段：用户确认后，以 `V2D_HF_ARCHIVE_STEPS=delete` 和同一个输出前缀再运行一次。
8. 用户不同意删除时：`rm -rf runs/hf_stage`（1352 个硬链接与上传缓存），仓库里的副本留着，本地什么都不删。

## 判据（执行前登记）

- 开跑前：token 属于 Rongxuan-Zhou、权限 write，仓库私有（已满足）；没有训练链在跑。流程脚本日志第一行的工具 md5 是
  `027ed7885644289e667b1bdd985e8d98`，清单 md5 是 `eb895d8479c43e7ebc6842441675922e`、1352 个文件。
- 第一段：1352 个文件的大小与 sha256 全部一致（verify），52 条 run 各抽 1 个下载后 sha256 一致（spotcheck）。
  有一个不一致就一个都不删，停下来排查。
- 第二段只在用户确认后运行。
- 删除后：
  - 删除前重新核对 1352 / 1352 一致；
  - `runs/flash_chord` 下消失的文件正好是清单里的 1352 个：清单外消失 0 个，清单里没删的 0 个（流程脚本的全量比对）；
  - 可用空间增加约 6265 MB（6.57e9 字节，允许 ±100 MB）；
  - 52 条 run 各剩 9 份 policy，最新一份仍是 349999104 步；
  - 带 `ARCHIVED.json` 的 run 从 38 条变为 71 条：已有的 19 条保留 10/1 的记录、末尾多一条这次的记录，其余 33 条新建；
  - `runs/hf_stage` 已删除。

## 审查与处理（第 2 版）

Fable 5.1 独立审查：GO WITH FIXES，没有 BLOCKER。审查确认留最新 9 份不会删到现有工具要用的文件（导出回退、续训、提交核对），
删除时重算保护集的做法正确，`tools/hf_remote.sh` 在命令行、进程表与 record 头里都没有凭据。
- MAJOR 测试记录对应的工具版本（md5 25a3de2d…）不是将要运行的版本 → 用最终版重跑全部测试并记下 md5；开跑判据加上工具与清单的 md5。
- MINOR 第二段只看第一段落下的核对结果，两段之间可能隔几小时 → `delete` 步骤先重新核对一遍仓库。
- MINOR 全量比对会被同时运行的单个 GPU 作业误报（fc_export、fc_run 会删临时文件）→ 删除前查 GPU 进程与相关进程，有就停；
  另外报出清单里没删掉的个数，“正好 1352 个”不用靠人数。
- MINOR 随机抽 10 个几乎抓不到单个损坏的对象 → 每条 run 抽 1 个，共 52 个。
- MINOR 服务器上的日志写入时没有过滤 → 流程脚本的输出先过 grep 再写日志。
- MINOR 判据措辞：14 条 Tier 2 与 10/6 的 r3a、s43 run 没有 10/1 的记录 → 改成 38 → 71 条的写法；“清单与演习一致”改成比 md5。
- MINOR 用户不同意删除时没有收尾 → 第 8 步删暂存目录。
- 顺手：保护集加读导出输入清单 `stages/evaluate/exports/*.tsv`；补了流程脚本 verify 步骤与全量比对的阴性用例。

## 风险

- 上传时没有训练在跑，只占网络与少量 CPU；mf4090 的 GPU 空闲。
- 1352 个小文件由 `upload_large_folder` 分批提交；HF 对提交频率有限制，可能变慢。中断后重跑同一命令可以续传。
- huggingface_hub 1.32.0 提示 `upload_large_folder` 已弃用（10/1 日志），但仍可用；失败时停在 upload，不会删除任何东西。
- 归档后，老 run 的 `run_pace.py`、`ckpt_nonfinite.py` 只能看到最后 9 份；需要时按 `ARCHIVED.json` 记的位置从 HF 下载。
- 以后若要从更早的 checkpoint 导出（回退超过 8 份，或改用某个中间步数），要先从 HF 下载。
- Mac 断开不影响：任务在服务器后台运行，日志也在服务器上。
