# 冻结前计分提交清单（2026-11-04）

日期 2026-11-04，分支 `track2/p1-training`。依据：官方工具包 11/02 版（`third_party/v2d_submission_kit/update_7e1fdd00/`，Last-Modified 2026-11-02 18:21:47 GMT）新增的 `CONTAINER_SUBMISSION.md`。参评奖项的队伍在比赛结束后提交技术报告和 Docker 容器，容器要复现每个榜上计分的那份提交（手选的 Final Submission；没选时是分最好的那份），评测脚本、评测包、每集 checkpoint、packer、uploader 的哈希和 commit 都要与 Kaggle 收到的文件一致。官方没有写容器与报告的截止日期；Kaggle 12 个 Track 2 榜的截止是 11/04 22:00 UTC（15:00 MST）。

## 1. 各榜计分的提交

记录 `results/freeze/counted_inventory.txt`（`tools/counted_inventory.py`）。没有手选 Final Submission，按分最好的取，同分全列：

| 档位 | 计分文件（覆盖的榜） |
|---|---|
| Tier 1 | t1x1102（四个榜）；SP-SR 与 t1x1101 同分，MP-SR 与 t1x1101、t1x1018 三份同分 |
| Tier 2 | t2a1102（AUC）；b1014（SP-SR、MP-SR、MPPE），SP-SR、MP-SR 与 b1013 同分 |
| Tier 3 | t3m1104c（AUC）；t3m1029a（SP-SR、MP-SR、MPPE），MP-SR 与 t3m1022aa 同分 |

共 9 份文件，每份本地 CSV 和一份上传回执都在 `runs/submission/csv/`。9 份的 `eval_script_sha256`（160d24f5…）、`eval_code_sha256`（b1b3ebe3…）、`packer_script_sha256`（47a45895…）、`uploader_script_sha256`（fe5cb1dc…）各只有一个取值；前一个和后两个与 `third_party/v2d_submission_kit/update_0f2f9f4b/` 里的文件 sha256 相同。

## 2. checkpoint

9 份文件每集的 `checkpoint_sha256` 共 270 行。其中 267 行在 `runs/submission/` 下的 evaluator JSON 里找到 checkpoint 路径，去重后 ml40 65 个、mf4090 61 个；两台逐个核 sha256，全部 OK（`results/freeze/ckpt_check_{ml40,mf4090}.txt`，`tools/ckpt_check_remote.sh`）。没找到路径的 3 行都属于 t1x1018（ep0、5、27）。按 `results/ml40/select_t1/select_t1x1018.txt` 里选中的 run 在三台机器上找（`tools/find_ckpt_remote.sh`）：三个都在 mf4090 的 `runs/flash_chord/<run>/policy_349999104.safetensors`，sha256 与 CSV 记录相同（`results/freeze/lost_t1x1018_sha_mf4090.txt`）；ml40、l40n 上没有这三个 run 的文件。计分提交用到的 checkpoint 现在全部找到。

## 3. 待处理

- **t1x1018 的 commit 链接写错了。** CSV 里 22989 行的 `code_commit_url` 都是 `…/commit/c2dc9fbac35506e3a4bfe1e3e45047fa9b4e9c75`，这个 sha 在本地和 GitHub 上都不存在。前 12 位 `c2dc9fbac355` 对应的真实 commit 是 `c2dc9fbac3554c7f49afa354e6ce249d6fcb16a1`（10/18 11:41 EDT，在 `origin/track2/p1-training` 上，GitHub 能查到）；完整 sha 的后 28 位与真实 commit 不同，而且打包时工作区有未提交的改动（来源记作 `c2dc9fbac355-dirty`）（`results/freeze/commit_t1x1018.txt`）。t1x1018 只在 Tier 1 MP-SR 上与 t1x1101、t1x1102 同分。容器按 t1x1102 覆盖 Tier 1；11/04 14:51 MST 已手选（第 4 节），Tier 1 只选 t1x1102。
- **组织方看不到仓库。** 仓库私有，协作者里没有 Nvidia-V2D-Challenge；我们的账号只有 maintain 权限，看不到待接受的邀请，也加不了。需要 Manifold-ai 的 owner 或仓库 admin 添加。
- **9 份文件对应 9 个不同的 commit。** 容器模板里 `code` 只有一个 commit，多个 commit 怎么放，待向组织方确认或按 `skills/v2d-container/SKILL.md` 处理。其余 8 个 commit 都在远端分支上。
- 冻结后：`eval_code_sha256` 与评测镜像里的 FlashCHORD 评测包核对；Tier 3 frame references（`runs/submission/{t3m1104c,t3m1029a,t3m1022a}/frefs`）与各文件的打包记录核对；搭容器前先写计划并复核。
- 冻结期间计分文件背后的 checkpoint、rollout、frame references 和 `update_0f2f9f4b` 工具包不删、不改、不重新保存，评测镜像不升级。今天若再交 t3m1104e 并且分更高，Tier 3 AUC 的计分文件改为 e，重跑本清单。

## 4. Final Submission（11/04 14:51 MST 定稿）

官方提交表单（Google Form，“Final leaderboard submission IDs or URLs” 一项）原文：“Ensure you select the same single submission on each leaderboard for a given track or tier. Failure to do so can result in the delay or forfeiture of your prize if eligible.” 代码版本一项：Track 2 各档用不同 commit 时，按 Tier 1、Tier 2、Tier 3 分行给链接。表单没有写截止时间；私有仓库要在填表前把 Nvidia-V2D-Challenge 加为可访问。

14:1x MST 先在每个榜选了两份（Kaggle 每榜最多 2 份，选不满时按公开分自动补），看到表单后，经 rxzhou 同意，14:3x–14:51 MST 改成每档只选同一份：

| 档位 | 四个榜都选 | commit |
|---|---|---|
| Tier 1 | t1x1102 | b59f6a6cb3f97fc53ebdb28e2e8496534478c108 |
| Tier 2 | b1014 | c4f248dc60f39f4c7b03c535fbace6ae6b422bc9 |
| Tier 3 | t3m1029a | 2175e83e0c13b9ae2391d724f3d1c80c392b73d3 |

t2a1102、t3m1104c 当时只交了 AUC 一个榜，四个榜选同一份时选不了。按 14:18 MST 的快照估计：Tier 1、Tier 2 各榜名次不变；Tier 3 AUC 按 t3m1029a（0.28173）计约第 7（t3m1104c 是第 5）。Kaggle 页面上空着的第二个位置仍标为“自动候选”（Tier 1 MP-SR 标的是 t1x1018），我们勾选的只有上表这一份。容器只需复现这 3 份文件、3 个 commit；三份的 checkpoint 都在第 2 节核过。11/04 14:00 MST 起 12 个比赛的队名是 Maniphys Lab（`results/board/teamname_1104_1400.txt`）。

## 5. 技术报告与容器（11/04 15:37 MST）

- 容器 `maniphys-lab-v2d-submission:final`（image sha256:d870d3ab…）：三档各一份 manifest 与代码目录，90 个 checkpoint sha256 全对，FlashCHORD 8c778f9 放在 `/workspace`；`run.sh verify` 三档都是 11 项通过、0 项不过（`results/container/verify_1104.txt`）。压缩包 8.4 GB，sha256 d0f6d4018d4d893886f405c22404e80caf7e7ac644df6a82f3c3b4f68d410d91，与技术报告一起放在 HF 公开仓库 `Rongxuan-Zhou/maniphys-lab-v2d-track2-submission`；公开链接可下载，HF 记录的 sha256 相同，报告 PDF 从公开链接取回与本地新版逐字节相同。
- 技术报告第 5 节照实写明 ep12、ep27 选对称分支用到了 Tier 1 第 0 帧、进了训练参考（`plan-t3b2` 里的待定项，11/04 15:4x MST rxzhou 定为照实写）。
- 表单（Google Form）由 rxzhou 提交；提交前 GitHub 仓库要先给 Nvidia-V2D-Challenge 开访问权限（需 Manifold-ai 的 owner 或 admin）。
