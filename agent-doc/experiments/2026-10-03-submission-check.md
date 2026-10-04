# 提交前全面检查两档 CSV（2026-10-03 晚，UTC-6）

计划 `agent-doc/plan-submission-check-2026-10-03.md` 第 2 版（Fable 5.1 审第 1 版 GO WITH FIXES，按意见修改后于 d4af196 登记判据）。全程只读：没有提交，没有改动要交的两份 CSV，
没有调用不带 `--dry-run` 的上传器。检查对象是 `runs/submission/csv/track2_tier1_full30_1003.csv`（sha256 870674f4…）与 `track2_tier2_full30_1003.csv`（sha256 3be33c68…）。

## 结论

- **判据项 C1–C5 两档都过**：每条 episode 的来历、行与官方样例、数值、由导出轨迹复算 CSV、按原参数重打包，全部满足登记的判据。
- **C6 不过，按判据停下报告**：官方 kit 在 10/2 00:12（UTC-6）又发了一版（sha256 b1f8f703…，695,124 字节），我们打包用的是 10/1 的 0f2f9f4b。
  逐文件比较后，新版只改了说明文档、Track 1 的计分代码与 `v2dlb/mhr_submission.py`；Track 2 用到的打包器、上传器、评测脚本、样例 CSV、`config/tracks.json` 与 Track 2 的计分代码都没变，
  CSV 里记的打包器、上传器、评测脚本的 sha256 与新 kit 里的文件逐字节相同。因此两份 CSV 在新 kit 下照样成立，不需要重打包。
- **新 kit 里与我们有关的只有一处**：私有仓库要把 GitHub 账号 Nvidia-V2D-Challenge 邀请为协作者并给仓库访问权限，确保它能看到提交对应的 commit
  （新增于 kit 的 `README.md` 与 `tracks/track_2/README.md`）。我们的仓库现在 `private=true`、`visibility=internal`，不做这一步，CSV 里的代码链接组委会打不开。
  这是规则 2.9.a 要求的提交来历，Kaggle 端不会拦，属于事后核验时的作废风险。邀请外部账号由用户决定、由用户操作。

## 判据项

| 编号 | 检查 | 结果 | 记录 |
|---|---|---|---|
| C1 来历 | 每档 30 条：CSV 的 checkpoint 哈希 = 导出 JSON 与 parquet 元数据 = 服务器上 policy 文件的 sha256 = 4096 世界评测记的；run 与步数等于导出清单；训练参考在本档目录、与 run 记录相同，sequence_id 与本档发布数据一致；评测代码哈希两档只有一个值（b1b3ebe3…）；评测脚本、打包器、上传器的哈希与 kit 文件相同；两档 checkpoint 各 30 个、互不相交，位姿没有逐行相同的；代码链接两档相同，提交 c9d4013 在 origin/track2/p1-training | 两档都过 | `results/submission/check_tier{1,2}_1003.txt`、`check_cross_1003.txt`、`check_remote_mf4090.txt`、`results/ml40/submission/check_remote_ml40.txt` |
| C2 结构 | 样例 CSV 的 sha256 = KIT_MANIFEST 记的；两份 CSV 的 row_id 与样例逐行相同（22,989 行）；只有 w000、o0；比发布数据少的一行是 ep11 第 900 帧，正是两档发布 parquet 里物体不可见的帧 | 两档都过 | 同上 |
| C3 数值 | 全部有限；四元数模长与 1 相差不超过 1e-5 | 两档都过 | 同上 |
| C4 复算 | 照打包器的构造，由导出 parquet 的 achieved 位姿复算 CSV：Tier 1 位置最大差 8.5e-7 m、朝向 1.9e-6 rad；Tier 2 位置 8.4e-7 m、朝向 1.9e-6 rad（六位小数的舍入量）。评测器系到发布系的变换平移 2.51–4.15 m、旋转 93–178°，这一步错了分数就全错 | 两档都过 | 同上 |
| C5 重打包 | 用 10/3 的代码链接经 `pack_tier.sh --inner` 重打两档，依赖版本与 10/3 相同，sha256 与原 CSV 逐字节相同；Tier 2 的输出里没有本地分数那一行 | 两档都过 | `results/submission/pack/t{1,2}_recheck1003.txt`、`results/submission/check_c5_tier{1,2}_1003.txt` |
| C6 kit | 远端 kit 是 b1f8f703（Last-Modified Fri, 02 Oct 2026 06:12:40 GMT），不是 0f2f9f4b | **不过**（影响见上） | `results/submission/kit_freshness_1003.txt`、`fetch_kit_1003.txt`、`kit_diff_0f2f9f4b_b1f8f703.txt`、`kit_b1f8f703_track2_hashes.txt` |

检查脚本自测：在内存里改坏 Tier 1 ep3（换 checkpoint 哈希、一行四元数改成非单位、一帧位置挪 1 cm），C1、C3、C4 都判不过（`results/submission/check_selftest_1003.txt`）。
Tier 2 那次在进程开头调了 `forbid_tier1()`，没有读到 Tier 1 的任何文件。

## 只报

**R1 交上去的 1 个世界与 4096 世界评测。** kit 假定 explicit 重置下各世界冗余、只交 1 个世界（`config/tracks.json:13`），评测配置是 `deterministic: true`；
但我们 4096 世界的 MP-SR 是比例，说明各世界的结果并不相同，交上去的轨迹是一次抽样。

- Tier 1：1 个世界 MP-SR 成功 8 / 30（ep7、ep8、ep12、ep18、ep22、ep23、ep24、ep26），4096 世界 MP-SR 的 30 条平均 0.265。标出 ep6：4096 世界 MP-SR 0.562，这 1 个世界失败。
  反过来，ep18 的 4096 世界 MP-SR 只有 0.152，这 1 个世界成功。
- Tier 2：1 个世界 MP-SR 成功 1 / 30（ep22，4096 世界 0.724），30 条平均 0.054，没有标出的。这些分数对照的是 Tier 2 v5.4 参考，不和 Tier 1 比。

**R2 Tier 1 按 kit 口径的本地分数**（发布网格的顶点、干净参考，与打包器同一套代码）：AUC 0.3780、SP-SR 0.5333、MP-SR 0.2667、MPPE 25.1706 cm，与打包器打印的相同。
kit 写明 Kaggle 计分用从发布 glb 按种子 0 采的 500 个顶点，评测器自己的采样来自仿真网格，两者不一致时“treat any small AUC discrepancy as this mismatch”（`v2dlb/vertices.py:10–21`），
这就是 Tier 1 打包时交叉核对报 ADD-AUC 不一致（差 0.001–0.02）的原因，不是计分错误。排行榜分数以 Kaggle 为准。Tier 2 的本地分数按干净参考算，照提交流程计划第 5 节的解读不看。

**R3 与本档发布输入的位置差。** Tier 1 有 8 条最大差超过 1 m（ep2 2.14、ep3 1.43、ep4 2.04、ep9 1.16、ep11 1.44、ep16 1.11、ep25 1.62、ep28 1.42 m），都是 1 个世界 MP-SR 失败、
物体没被带到位的 episode；Tier 2 有 9 条（对照的是带噪输入）。没有飞出几十米之类的异常值。

**R4 数据与日期。** Hugging Face 数据集 `nvidia/video_to_data_challenge` 当前 main 是 5f68335…（lastModified 2026-09-22），本地 track_2 下 101 个文件与它逐个相同；
挑战页面上的封榜时间仍是 2026-11-04 17:00 EST。

**R5 代码链接。** CSV 里的链接指向 c9d4013，在 origin 上；仓库 `private=true`、`visibility=internal`。kit 要求链接在“与 V2D 账号共享的仓库”里（`tools/pack_submission.py:216`），
规则 2.9.a 要求每份提交指明产生它的 commit（`v2dlb/report_schema.py:108`），获奖方案与源码须以 Apache-2.0 公开（`config/tracks.json:335`）。10/2 的新 kit 写明了做法：邀请 Nvidia-V2D-Challenge 为协作者。

**R6 提交清单。** 网站政策每周 5 次、最后三天不限（`config/tracks.json:304、333`；Kaggle 上配置的是每天 5 次，`:325`）；决赛最多选 2 份（`:326`）；上传器把一档的 CSV
逐个交到这一档的 4 个比赛（`submit/v2d_submit.py:533–538`），每个比赛各记一次；Kaggle 显示的截止是 2026-11-04 22:00（`results/submission/kaggle_join_status_1003.txt`）；
队伍名提交前没法用 API 核（上传器只从已有提交读 `team_name`，`v2d_submit.py:269–270`），只能在比赛页面上确认。

## 提交之前还差的（都由用户定）

1. 邀请 Nvidia-V2D-Challenge 为仓库协作者（或另定让组委会看到代码的办法），并确认它能打开 c9d4013。
2. 什么时候交、交哪一档；每次上传会占用这一档 4 个比赛各一次的配额。
3. Tier 2 的本地分数照现在的解读滤掉，以及 Tier 2 排行榜的反馈怎么用。
4. 以后再打包时可以换成新 kit（Track 2 的结果不变）；`pack_tier.sh` 现在核的是 0f2f9f4b 的 zip，换的话要改这一处并重跑它的测试。

## jev

规格 `agent-doc/experiments/2026-10-03-submission-check.claims.json`，结果 `results/submission/jev_claims_check_1003.txt`（第 2 轮）：12 条全部核实（0.70–0.98），3 道对照题方向都正确。
第 1 轮（`…_run1.txt`）有一条没过：“改动的文件里没有打包器、上传器……”这种否定式只得 0.59，证据里也漏了“两版各 55 个文件”那一行；改成用证据原话逐个列出改动的文件、补上那一行后整批重跑，0.98。
“新 kit 要求邀请 Nvidia-V2D-Challenge”那条是 0.70，正好在线上：README 的原句跨了几行，证据只截到含账号名的那几行；原文见 `kit_diff_0f2f9f4b_b1f8f703.txt` 的 README.md 一节。
