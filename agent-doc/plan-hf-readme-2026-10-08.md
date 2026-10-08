# 计划：给上传过的 HF 仓库补 README（2026-10-08，第 1 版）

用户 10/8 的要求：“目前所有的上传HF的都要在HFrepo中写简单的README”。时间一律为 UTC-6。

## 事实

- 账号 Rongxuan-Zhou 下共 15 个仓库（`results/ops/hf_repos_1008.txt`）。属于本项目的只有 `Rongxuan-Zhou/v2d-track2-archive`：
  私有，1392 个文件（39 份 state 共 6,244,721,044 字节，1352 份 policy 共 6,570,689,816 字节，外加 `.gitattributes`），没有 README.md。
- 其余 14 个属于别的项目（lewm、forge、pusht、ogbench、force-lewm），其中 9 个没有 README，4 个是公开的
  （`lewm-archive`、`ogb-cd-3k`、`ogb-ct-3k`、`force-lewm-datasets`）。它们的来历不在本仓库里，这次不动，向用户确认范围。
- 本仓库里只有 `tools/hf_archive.py` 往 HF 上传（grep `upload_file|upload_folder|upload_large_folder|create_repo|push_to_hub`）。
- mf4090 上有 `hf` 命令（`~/.local/bin/hf`）。README 里的 `ARCHIVED.json` 示例取自训练机上的
  `runs/flash_chord/t1-ep16-w2048-cap4m-mf4090/ARCHIVED.json` 原文。
- 第 2 批（policy）的本地删除还在等用户确认。README 里第 2 批的本地副本写“截至 10/8 仍在，待确认后删除”，
  第二段跑完后更新 README 再传一次。

## 做法

1. README 源文件放在 `docs/hf/v2d-track2-archive/README.md`（进 git），内容包括：仓库里有什么（两批的日期、文件数、大小、本地副本状态），
   目录结构，与训练机上 `ARCHIVED.json` 的对应，下载与放回，sha256 校验，相关代码与记录。已用 humanizer-zh 过一遍。
2. `tools/hf_archive.py` 新增 `readme` 子命令：仓库不存在就建成私有的，把文件传成仓库根的 README.md，再下载回来比 sha256。
   `upload` 遇到不存在或根目录没有 README.md 的仓库就停，用机制守住用户的要求。
3. 新版工具部署到 mf4090 的 `runs/tools/`，用部署的版本重跑测试并记下 md5。第 2 批第二段也用这一版（删除路径没有改动）。
4. README 经 scp 放到 mf4090 的 `runs/hf_readme/v2d-track2-archive.md`，用 `tools/hf_remote.sh` 跑 `readme` 子命令，
   结果落盘到 `results/ops/hf_readme_v2d_track2_archive.txt`。
5. README 里的事实送 jev 核对；Fable 5.1 审 README 与代码改动。
6. 记一条 memory：上传过的 HF 仓库都要有 README。

## 判据（执行前登记）

- 仓库根目录出现 README.md，下载回来的 sha256 与 `docs/hf/v2d-track2-archive/README.md` 一致（HF_README_OK）。
- 仓库仍为私有，文件数为 1393（1392 加 README.md）。
- 部署版本的测试在 mf4090 上全部通过。
- README 里的数字（文件数、字节数、日期、核对与抽查结果、路径）经 jev 核实，均不低于 0.7，对照题正常。

## 审查与处理

Fable 5.1 独立审查：GO WITH FIXES，没有 BLOCKER。审查逐项核对了 README 里的数字、步数范围、`ARCHIVED.json` 格式与核对结果，
确认没有泄漏凭据，`readme` 子命令正确，上传前的检查不会挡住第 2 批第二段（删除步骤不调用 upload）。
- MAJOR README 里手敲的 `hf download` 不固定 `HF_ENDPOINT`，训练机 `.env` 把它指向下载镜像，token 会发给第三方
  → 训练机上一律经 `tools/hf_remote.sh` 执行；其他机器先确认 `HF_ENDPOINT` 未设置或等于 https://huggingface.co。
- MINOR 恢复目录 `restore/` 不在 `.gitignore` 里 → 改成 `runs/restore`。
- MINOR `upload` 先建暂存硬链接、后查仓库，查不过会留下 `runs/hf_stage` → 先查仓库再建暂存目录。
- MINOR 测试没覆盖 `readme` 与上传前的检查 → 加一个测试，用假的 huggingface_hub 覆盖四种情况。
- MINOR 第 2 批计划登记的工具 md5 是第一段的版本 → 在那份计划里改判据。
- MINOR 表头日期没写时区 → 改成“归档日期（UTC-6）”。

## 执行记录（10/8 10:52–11:08 UTC-6）

- 实测 README 里的下载命令（`results/ops/hf_restore_test_mf4090.txt`）：第一次报 127，`tools/hf_remote.sh` 走的是非登录 shell，
  找不到 `~/.local/bin/hf`。在 `hf_remote.sh` 的远端 PATH 前面加上 `~/.local/bin` 后重测：下载 1 个文件，
  下回来的文件、本地原文件与清单的 sha256 一致，测试副本已删。
- 测试：工具 md5 `a7f6ce8272e482a5b0f3449f0d55bb89`，12 项在 mf4090 上全过（`results/ops/hf_archive_tests_readme_mf4090.txt`）。
- jev（`results/ops/jev_claims_hf_readme.txt`，规格 `agent-doc/experiments/2026-10-08-hf-readme.claims.json`）：第 3 轮 8 条全部核实
  （0.91–0.99），3 道对照题正常。第 1 轮有两条 claim 把好几件事塞在一起、数字带千分位，拆开后第 2 轮剩“每条 run 26 份”只有 0.37
  （要 jev 自己数 52 行）；第 3 轮改由 `tools/hf_archive_report.py` 算出“清单按 run 分”的结果再核。前两轮留档为 `_run1`、`_run2`。
- 上传（`results/ops/hf_readme_v2d_track2_archive.txt`）：README（md5 `7ed78bacd82ae8873db17fbee2aae9e8`）传到仓库根目录，
  下载回来 sha256 一致（HF_README_OK）；仓库仍为私有，1393 个文件，共 12.82 GB。判据全部满足。
- 账号下其余 9 个没有 README 的仓库属于别的项目。用户 10/8 决定不补（“其他不要补充”），这条要求只管本项目上传过的仓库。
- 10/8 11:28：第 2 批本地删除后，README 的状态改成“10/8 已删除”，补了 `ARCHIVED.json` 记录时间的换算，重新上传，HF_README_OK。
