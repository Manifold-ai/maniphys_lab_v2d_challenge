# 计划：提交前全面检查两档 CSV（2026-10-03，第 2 版）

用户 10/3 22:30（UTC-6）：“先不着急提交，提交得我确认，你先全面检查一下结果。”本计划只做只读检查，不提交、不重打包覆盖已有文件、不改任何 run。
第 2 版（10/3 23:10）：按 Fable 5.1 对第 1 版的审查修改（GO WITH FIXES，2 条 MAJOR、10 条 MINOR），对照见第 6 节。
时间一律 UTC-6。

## 1. 事实

- 要交的是两份 CSV：`runs/submission/csv/track2_tier1_full30_1003.csv`（sha256 870674f4…）、`track2_tier2_full30_1003.csv`（sha256 3be33c68…），各 22,989 行，
  由 kit `update_0f2f9f4b` 的打包器从 `runs/submission/final/t{1,2}/episode_XXXXXX.{json,parquet}`（各 30 条，两台导出链 `export2_<机器>` 的结果）生成；
  上传器 `--dry-run` 两档都报 “looks valid”（`results/submission/pack/t1_full30_1003_dryrun.txt`、`t2_full30_1003_dryrun2.txt`）。
- CSV 每行：`row_id`（`track_2/e<episode>/w<world>/f<frame>/o<object>`）、物体位置与四元数（xyzw）、`eval_script_sha256`、`eval_code_sha256`、`checkpoint_sha256`、
  `packer_script_sha256`、`uploader_script_sha256`、`code_commit_url`。
- 导出 parquet：每步一行，`achieved_*` 与 `reference_*` 位姿（xyzw），schema 元数据里有 checkpoint、评测代码、评测脚本的 sha256 与训练用的 reference parquet 路径；
  导出 JSON 里有 checkpoint 路径与 sha256、1 个世界的指标、`non_finite_worlds`。
- 发布数据两档各 30 条、合计 22,990 帧（`data/challenge/track_2/<档位>/meta/episodes.jsonl`）；CSV 是 22,989 行，少的一行还没核是哪一帧。早先记过数据集有一帧不可见（ep11）。
- 打包器已核：每条 episode 的换算是一个刚体变换（残差 1e-7 量级）；Tier 1 的交叉核对报“轨迹与评测器 JSON 的 ADD-AUC 不一致”（25 条，差 0.001–0.02，预演里已有）。
- 每条 run 在 8c778f9 下有 4096 世界的评测（导出链核过候选条件）；按批量判据 Tier 1 通过 12 / 30，Tier 2 通过 7 / 30。
- 4096 世界评测的 MP-SR 是比例（例如 t1-ep7 0.653），说明同一个 checkpoint 在不同世界里结果不同；交上去的是 1 个世界的轨迹，排行榜给这条轨迹打分。
- kit 的下载地址 `https://nvidia-isaac.github.io/video_to_data/v2d_challenge/assets/v2d_submission_kit.zip`；我们用的是 10/1 13:43 重发的那版（zip sha256 0f2f9f4b…）。
  kit 的 `config/tracks.json` 里 `accepted_eval_code_sha256` 与 `accepted_eval_script_sha256` 都是空列表。

## 2. 检查与判据（执行前登记）

**判据项**：任一项不过就停下，照实报告，不改 CSV、不提交。

| 编号 | 检查 | 通过的判据 |
|---|---|---|
| C1 来历 | 每档 30 条：CSV 里这条 episode 的 `checkpoint_sha256`（全部行唯一一个值）= 导出 JSON 与 parquet 元数据里的 = 服务器上 `policy_349999104.safetensors` 的 sha256 = 4096 世界评测记的；JSON 的 checkpoint 路径里的 run 名 = 导出清单这一行的 run、步数 349999104；JSON 与 parquet 元数据里训练用的 reference parquet 在本档的目录（`runs/motion/tier<档位>/`），与 run 记录里的相同，sequence_id 与本档 `meta/episodes_metadata.jsonl` 里这条 episode 的一致；两档 60 条的 `eval_code_sha256` 只有一个值，等于 8c778f9 运行时的（`b1b3ebe3…`）；`eval_script_sha256`、`packer_script_sha256`、`uploader_script_sha256` 每档只有一个值且与 kit 里同名文件的 sha256 相同；`code_commit_url` 两档同一个值，指向的提交已在 origin；两档的 checkpoint 集合不相交，两档的位姿列不逐行相同（防两档打到同一个导出目录） | 全部一致 |
| C2 结构 | 本地样例 CSV 的 sha256 = `KIT_MANIFEST.json` 里记的（`9b2116be…`）；CSV 的 `row_id` 与样例逐行相同（顺序也相同）；每条 episode 只有 `w000`、`o0`；CSV 比发布数据少的帧，正好是本档发布 parquet 里物体不可见的帧（kit 的 `read_episode` 丢掉这些帧），Tier 2 只读 Tier 2 自己的 parquet | 全部满足 |
| C3 数值 | 所有位置与四元数有限；四元数模长与 1 相差不超过 1e-5（CSV 保留 6 位小数，实测偏差在 1e-6 量级；上传器只拒模长 < 1e-8，计分前会归一化）。第 1 版的“位置绝对值不超过 100 m”抓不到问题，删掉，交给 R3 | 全部满足 |
| C4 CSV 与导出一致 | 每条 episode：照打包器的构造复算（`pack_submission.py:82–130`：用导出 parquet 的 `reference_*` 与换算参考的第一帧求旋转与平移，再施加到整段 `achieved_*` 上；Tier 1 的换算参考是发布数据，Tier 2 是 v5.4 帧参考），帧按 CSV 的 `row_id` 与导出的 `reference_frame` 对齐，复算结果与 CSV 比：位置最大差不超过 5e-6 m、朝向最大差不超过 1e-5 rad（六位小数的舍入量约 1e-6）。第 1 版的 Kabsch 拟合在物体几乎不动的 episode 上病态，不用 | 60 条全部满足 |
| C5 打包可复现 | 经 `scripts/dev/record` 直接调 `pack_tier.sh --inner <档位> runs/submission/final/t<档位> runs/submission/csv/track2_tier<档位>_recheck1003.csv <10/3 打包用的代码链接 c9d4013> ''`（加 `UV_OFFLINE=1`；`--inner` 不碰上传器，Tier 2 自动加 `--frame-references`、照样滤掉本地分数那一行；它跳过外层的 kit 校验与“已存在就拒绝”，所以先核新文件名不存在、kit zip 的 sha256 仍是 0f2f9f4b），打印的依赖版本要与 10/3 相同（numpy 2.5.3、pandas 2.3.3、pyarrow 25.0.1、trimesh 5.1.1）。第 1 版用外层 `pack_tier.sh` 会把代码链接换成当前 HEAD，逐字节必然不同（Fable M1） | sha256 相同；不同时按列比较，报出是哪一列、哪些行变了，判不过 |
| C6 kit 是否更新 | 下载 kit 到内存算 sha256（694,480 字节），另把 HEAD 的 Last-Modified、Content-Length、ETag 与 10/1 记下的 `headers.txt`（`Thu, 01 Oct 2026 19:43:26 GMT`、694480、`"6abeb7de-a98d0"`）比 | 远端 sha256 仍是 0f2f9f4b；否则停下报告，提交前要先按新 kit 重核 |

**只报、不作判据**：

- R1 每条 episode 1 个世界的结果（导出 JSON：chord_sr、MP-SR、SP-SR 是 0 或 1，ADD-AUC、MPPE）与同一 checkpoint 4096 世界评测的均值并排列出；
  标出“4096 世界 MP-SR ≥ 0.5 而这 1 个世界失败”和“4096 世界 MP-SR < 0.05 而这 1 个世界成功”的 episode。Tier 2 两边都是对 v5.4 参考算的，不用干净参考。
- R2 Tier 1 每条 episode 按 kit 口径（打包器同一套 `v2dlb` 代码、干净参考）的本地分数，以及四个汇总数，作为排行榜分数的预期；说明这只是本地复算，排行榜以 Kaggle 为准。
  Tier 2 的本地分数按干净参考算，照第 5 节滤掉的解读不看（提交流程计划第 5 节）。
- R3 每条 episode 的物体轨迹与这一档发布输入的物体位姿逐帧相差的中位数与最大值（Tier 1 发布输入就是干净参考；Tier 2 用发布的带噪输入），列出最大值超过 1 m 的 episode，供人看是否有明显的物体飞出、掉落。
- R4 数据集是否更新：Hugging Face 数据集 `nvidia/video_to_data_challenge` 的最新提交时间与我们下载时的版本（有记录就对，没有就照实写没有记录）；挑战页面的封榜时间有没有变（只读）。
- R5 代码链接能不能被组委会打开（Fable M2）：CSV 的 `code_commit_url` 指向私有仓库 `Manifold-ai/maniphys_lab_v2d_challenge`；kit 要求它在“与 V2D 账号共享的仓库”里
  （`pack_submission.py:214–217`），规则 2.9.a 要求每份提交指明产生它的提交（`v2dlb/report_schema.py:107–109`），获奖方案与源码须以 Apache-2.0 公开（`config/tracks.json` 的 `winner_license_text`）。
  Kaggle 只核链接的格式，不会拒，所以预检过了也说明不了这一点；这是事后核验时的作废风险。报：仓库可见性（`gh api`，只读）、提交是否在 origin、上述原文；明确写成“上传前由用户决定”。
- R6 给用户的提交清单：网站政策每周 5 次、最后三天不限（`tracks.json` 的 `submission_limit`、`submission_policy`；Kaggle 上配置的是每天 5 次）；决赛最多选 2 份（`max_final_submissions`）；
  上传器把一档的 CSV 交到这一档的 4 个比赛，每个比赛各记一次；Kaggle 显示的截止是 2026-11-04 22:00（`kaggle_join_status_1003.txt`）；队伍名提交前没法用 API 核（`v2d_submit.py` 只从已有提交读 `team_name`），
  只能用户在 8 个比赛的页面上确认。
- R1 另报背景（Fable m7）：kit 假定 explicit 重置下各世界冗余、只交 1 个世界（`tracks.json` 第 11–15 行）；评测配置 `deterministic: true`（kit `flash_chord/.../configs/evaluation/flash_sac.yaml:3`），
  我们 4096 世界的 MP-SR 是分数，说明各世界的结果并不相同，交上去的是一次抽样。R2 另报口径（Fable m6）：Kaggle 与打包器都用发布 glb 按种子 0 采的 500 个顶点算 ADD
  （`v2dlb/vertices.py`、`metric_code/track_2/AUC.py`），评测器 JSON 的 add_auc 用仿真网格的顶点，两者不同是 Tier 1 交叉核对报不一致的原因（执行前先核这几处原文）。

## 3. 净室

Tier 2 的检查只读 Tier 2 的发布输入、v5.4 帧参考、导出文件与 Tier 2 的 run；C4 里 Tier 2 的换算参考用 v5.4 帧参考。第 2 版（Fable m5）：检查脚本两档分两次调用，`--tier 2` 那一次在进程开头调 `forbid_tier1()`（`libs/v2d_infra/tier_guard.py`），读 Tier 1 目录就抛错；两档之间的比较（C1 的“不相交、不逐行相同”）另用 `--cross` 只读两份 CSV 的列。kit 的样例 CSV 是公开模板，不是 Tier 1 轨迹。C5 重打 Tier 2 时打包器会读干净参考算本地分数，
照提交流程计划第 5 节在落盘与显示前滤掉那一行，不看。R2 只做 Tier 1。

## 4. 做法

- `stages/evaluate/submission_check_remote.sh <机器>`（服务器上、只读）：对本机导出清单里的每一行，打出 policy 文件的 sha256、4096 世界评测 JSON 的关键指标、run 记录第一条 start 的 parquet 路径；
  经 `scripts/dev/record` 落盘后拉回。
- `stages/evaluate/submission_check.py`（Mac，用打包时的 uv 环境，`UV_OFFLINE=1`）：`--tier 1`、`--tier 2`（进程开头 `forbid_tier1()`）分两次跑，各打出这一档的 C1–C4 与 R1、R3，
  `--tier 1` 另打 R2；`--cross` 只读两份 CSV 做两档之间的比较；`--compare A B` 给 C5 比两份 CSV（逐字节，不同时按列）；`--selftest` 在内存里改坏 Tier 1 的一条 episode，C1、C3、C4 都必须判不过。
  每次最后一行 `SUBMISSION_CHECK PASS|FAIL`。
- C5：见第 2 节，经 `scripts/dev/record` 跑 `pack_tier.sh --inner`。
- C6、R4：`stages/evaluate/kit_freshness.py`（Mac，只读：下载 kit 到内存、HF 只读 API、挑战页面）。
- R5、R6：`stages/evaluate/submission_rules_facts.sh`（Mac，只读：kit 原文摘录带行号、`gh api` 查仓库可见性、`git branch -r --contains`）。
- 结果写进执行记录 `agent-doc/experiments/2026-10-03-submission-check.md`，过 jev，向用户回报。全程不调不带 `--dry-run` 的上传器，也不跑上传器的 `--dry-run`（这次用不到）。

## 5. 审查

请 Fable 5.1 独立审第 1 版（重点：检查有没有漏掉会让提交被拒或分数失真的点；判据是否可判定；净室）。审查意见与处理写在第 6 节。

## 6. 第 2 版对 Fable 5.1 审查意见的处理（GO WITH FIXES）

| 意见 | 处理 |
|---|---|
| M1 C5 用外层 `pack_tier.sh` 重打，代码链接换成当前 HEAD，逐字节必然不同 | C5 改用 `--inner` 并传 10/3 的代码链接；不同时按列比较 |
| M2 漏了“组委会能不能打开代码链接”，Kaggle 不拦，事后核验时作废 | 加 R5，写明上传前由用户决定 |
| m1 C4 别用 Kabsch，照打包器的构造复算；阈值可收到 5e-6 m / 1e-5 rad | 照改（审查人预跑的 5 条：位置最大差 8.3e-7 m、角度 1.9e-6 rad，只作参考，不计入本次结果） |
| m2 少的那一行是 ep11 第 900 帧（发布 parquet 只有它不可见）；加样例 CSV 的 sha256 与 KIT_MANIFEST 比 | 两项都写进 C2，由脚本核 |
| m3 C3 阈值收到 1e-5；“≤ 100 m”抓不到东西 | 照改，删掉 100 m |
| m4 sequence_id 的来源写清；加两档 checkpoint 不相交、位姿不逐行相同 | sequence_id 取本档 `episodes_metadata.jsonl`；两项加进 C1，用 `--cross` 做 |
| m5 两档分两次调用，Tier 2 那次套 `forbid_tier1()` | 照改（第 3 节） |
| m6 R2 写清 AUC 的顶点口径 | 加进 R1/R2 的背景，执行前先核原文 |
| m7 R1 报 kit 的“各世界冗余”假定与 `deterministic` | 加进 R1 的背景 |
| m8 C6 三个响应头一起比 | 照改 |
| m9 加给用户的提交清单 | 加 R6 |
| m10 第 1 版文件尾部残留了命令行 | 删掉 |


## 执行记录（10/13，R5 组委会账号的仓库权限）

- 10/13 17:28（UTC-6）用户决定邀请 GitHub 账号 Nvidia-V2D-Challenge 为仓库协作者。kit `update_b1f8f703` 的 `README.md:30–33` 要求：私有仓库邀请该账号为协作者并授予仓库访问权限，保证它能看到提交对应的 commit。
  该账号存在（`gh api users/Nvidia-V2D-Challenge`：type User，name “V2D Challenge”，company “Nvidia”，创建于 2026-10-01）。按最小权限申请 Read（`permission=pull`），能查看 commit 即可。
- 结果：没有邀请成功。`PUT repos/Manifold-ai/maniphys_lab_v2d_challenge/collaborators/Nvidia-V2D-Challenge` 返回 404（`results/ops/github_invite_nvidia_1013.txt.failed`）。
  原因：仓库属于组织 Manifold-ai，visibility 为 internal；本账号 Rongxuan-Zhou 是该仓库的外部协作者，权限为 maintain，admin 为 false（`gh api repos/Manifold-ai/maniphys_lab_v2d_challenge` 的 `permissions`）。
  列出仓库邀请的接口同样返回 403 “Must have admin rights to Repository.”。添加协作者需要仓库 admin 或组织所有者操作；GitHub 文档另说明组织与企业管理员可以限制邀请外部协作者。
- 待办：由组织 Manifold-ai 的所有者或仓库 admin 在仓库 Settings → Collaborators and teams 中添加 Nvidia-V2D-Challenge（Read）；邀请须由该账号接受后才生效。此前两份待交 CSV 里的 commit（66a8f0d、5888a41）组委会仍无法打开。
