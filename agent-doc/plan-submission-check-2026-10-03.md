# 计划：提交前全面检查两档 CSV（2026-10-03，第 1 版）

用户 10/3 22:30（UTC-6）：“先不着急提交，提交得我确认，你先全面检查一下结果。”本计划只做只读检查，不提交、不重打包覆盖已有文件、不改任何 run。
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
| C1 来历 | 每档 30 条：CSV 里这条 episode 的 `checkpoint_sha256`（全部行唯一一个值）= 导出 JSON 与 parquet 元数据里的 = 服务器上 `policy_349999104.safetensors` 的 sha256；JSON 的 checkpoint 路径里的 run 名 = 导出清单这一行的 run、步数 349999104；JSON 与 parquet 元数据里训练用的 reference parquet 在本档的目录（`runs/motion/tier<档位>/`），sequence_id 与发布数据这条 episode 的一致；两档 60 条的 `eval_code_sha256` 只有一个值，等于 8c778f9 运行时的（`b1b3ebe3…`）；`eval_script_sha256`、`packer_script_sha256`、`uploader_script_sha256` 每档只有一个值且与 kit 里同名文件的 sha256 相同；`code_commit_url` 每档只有一个值，指向的提交已在 origin | 60 条全部一致 |
| C2 结构 | CSV 的 `row_id` 集合与 kit 自带的这一档官方样例 CSV 完全相同（逐行比较 row_id 的集合与顺序）；每条 episode 只有 `w000`、`o0`；帧号与样例一致；少的那一行是哪条 episode 的哪一帧、为什么，照实写出 | row_id 与样例逐个相同 |
| C3 数值 | 所有位置与四元数有限；四元数模长与 1 相差不超过 1e-4（CSV 只保留 6 位小数）；位置的绝对值不超过 100 m | 全部满足 |
| C4 CSV 与导出一致 | 每条 episode：用导出 parquet 的 `achieved_*` 位姿与 CSV 的位姿按帧对齐，求一个刚体变换（位置用 Kabsch，朝向用四元数的相对旋转），残差位置不超过 1e-4 m、朝向不超过 1e-3 rad；变换与打包器对“reference 对到发布输入”求的是同一个（Tier 1 用发布的干净参考，Tier 2 用 v5.4 帧参考，取第 0 帧） | 60 条全部满足 |
| C5 打包可复现 | 用同一个 kit、同样的参数把两档各重打一次，写到新文件名（`…_recheck1003`），与已有 CSV 逐字节比较；上传器不跑 | sha256 相同 |
| C6 kit 是否更新 | 对 kit 的下载地址发 HEAD 取 Last-Modified 与长度；与本地 zip 不同就下载到临时目录算 sha256 | 远端仍是 0f2f9f4b；否则停下报告，提交前要先按新 kit 重核 |

**只报、不作判据**：

- R1 每条 episode 1 个世界的结果（导出 JSON：chord_sr、MP-SR、SP-SR 是 0 或 1，ADD-AUC、MPPE）与同一 checkpoint 4096 世界评测的均值并排列出；
  标出“4096 世界 MP-SR ≥ 0.5 而这 1 个世界失败”和“4096 世界 MP-SR < 0.05 而这 1 个世界成功”的 episode。Tier 2 两边都是对 v5.4 参考算的，不用干净参考。
- R2 Tier 1 每条 episode 按 kit 口径（打包器同一套 `v2dlb` 代码、干净参考）的本地分数，以及四个汇总数，作为排行榜分数的预期；说明这只是本地复算，排行榜以 Kaggle 为准。
  Tier 2 的本地分数按干净参考算，照第 5 节滤掉的解读不看（提交流程计划第 5 节）。
- R3 每条 episode 的物体轨迹与这一档发布输入的物体位姿逐帧相差的中位数与最大值（Tier 1 发布输入就是干净参考；Tier 2 用发布的带噪输入），列出最大值超过 1 m 的 episode，供人看是否有明显的物体飞出、掉落。
- R4 数据集是否更新：Hugging Face 数据集 `nvidia/video_to_data_challenge` 的最新提交时间与我们下载时的版本（有记录就对，没有就照实写没有记录）；挑战页面的封榜时间有没有变（只读）。

## 3. 净室

Tier 2 的检查只读 Tier 2 的发布输入、v5.4 帧参考、导出文件与 Tier 2 的 run；C4 里 Tier 2 的换算参考用 v5.4 帧参考。C5 重打 Tier 2 时打包器会读干净参考算本地分数，
照提交流程计划第 5 节在落盘与显示前滤掉那一行，不看。R2 只做 Tier 1。

## 4. 做法

- `stages/evaluate/submission_check_remote.sh <机器>`（服务器上、只读）：对本机导出清单里的每一行，打出 policy 文件的 sha256、4096 世界评测 JSON 的关键指标、run_record 第一条 start 记录的 parquet 路径；
  经 `scripts/dev/record` 落盘后拉回。
- `stages/evaluate/submission_check.py`（Mac，用打包时的 uv 环境，要 pyarrow、numpy）：读两份 CSV、导出文件、导出清单、两台的远端记录、kit 的样例 CSV 与发布数据的 meta，
  逐项打出 C1–C4 与 R1–R3 的结果，最后一行 `SUBMISSION_CHECK PASS|FAIL`。带一个自测：把一条 episode 的 checkpoint 哈希改掉、把一行四元数改成非单位，必须判不过。
- C5：`pack_tier.sh` 写到新名字（不跑上传器那一步，用它已有的“给 episode 时只打包”的方式不合适，改用 `--inner`；见第 6 节审查后定）。
- C6、R4：`stages/evaluate/kit_freshness.sh`（Mac，只读）。
- 结果写进执行记录 `agent-doc/experiments/2026-10-03-submission-check.md`，过 jev，向用户回报。全程不调不带 `--dry-run` 的上传器。

## 5. 审查

请 Fable 5.1 独立审第 1 版（重点：检查有没有漏掉会让提交被拒或分数失真的点；判据是否可判定；净室）。审查意见与处理写在第 6 节。
EOF
cd /Users/rongxuanzhou/V2D && git add agent-doc/plan-submission-check-2026-10-03.md && git commit -q -m "plan(submission): pre-submission check of both CSVs, v1 (read-only; criteria registered before running)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git log --oneline -1