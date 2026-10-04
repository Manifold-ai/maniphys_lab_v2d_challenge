# 执行记录：提交流程与两档各 30 条导出（10/2 凌晨部署，当天自动执行；不上传）

计划 `agent-doc/plan-submission-exports-2026-10-02.md` 第 2 版（06f41c3），按 Fable 5.1 的审查修改（GO WITH FIXES，没有 BLOCKER，计划第 9 节）。
时间一律 UTC-6；服务器日志是北京时间（UTC+8）。用户 10/1 23:50：“暂时先别提交任何内容”，本记录里的任何一步都不往 Kaggle 上传。

## 部署与预检（10/2 00:18–00:50，不占 GPU，在跑的链没动）

| 项 | 结果 | 落盘 |
|---|---|---|
| Mac 上的测试 | 第 2 版：`test_export_chain`（9 组）、`test_export_map`、`test_pack_tier`、`test_make_frame_references`（含 kit 函数读回）全过；原有的 `test_compat_8c778f9` 也过 | `results/submission/tests/*_mac_v2.txt`、`*_mac_v3.txt` |
| 拉打包数据到 Mac | Tier 1 干净参考 65 个文件、Tier 2 发布输入 36 个文件，sha256 逐个与 mf4090 一致，`PULL_OK 101` | `results/submission/pull_data_mac.txt` |
| 放新文件 | 两台各 8 个文件 md5 全对，远端来历仍是 90a73fa8e852；之后 mf4090 按需覆盖了 2 个我们自己放上去的文件（`V2D_PUSH_REPLACE_FROM=06f41c3`） | `results/submission/deploy_{mf4090,ml40}.txt`、`deploy2_mf4090.txt` |
| 服务器上的测试 | 两台 `test_export_chain` 9 组全过；mf4090 宿主机 `test_make_frame_references` 过（没有 pandas，kit 读回那部分按设计跳过） | `results/submission/tests/*_mf4090*.txt`、`results/ml40/submission/tests/test_export_chain_ml40.txt` |
| Tier 2 帧参考（第一次） | 29 / 30 通过，ep11 报 FAIL：粗核的角度差中位数是 NaN。ep11 有一帧不可见，发布的带噪输入在那一帧的四元数全零，算角度时除零。v5.4 本身在每帧有限、非零（脚本已核），打包器也只用可见帧 | `results/submission/frame_refs_t2_mf4090_try1.txt.failed`；输出目录改名 `runs/submission/frame_refs_t2.failed-10020130` 留档 |
| 修正 | 粗核只比发布输入可见、四元数非零的帧，打出排除了几帧；测试加一条同样的帧（6a26440） | `results/submission/tests/test_make_frame_references_mac_v3.txt`、`…_mf4090_v3.txt` |
| Tier 2 帧参考（第二次） | `FRAME_REFS_OK 30`。ep11 排除 1 帧；第 0 帧位置差除 ep17（14.8 mm，不穿地约束抬起）、ep10（0.3 mm）外都是 0.0 mm；逐帧角度差中位数最大 30.6°（ep18）；ep4 的 v5.4 与带噪输入几乎相同（位置、角度差中位数都是 0.0，第 0 帧角度差 0.5°） | `results/submission/frame_refs_t2_mf4090.txt` |
| 帧参考拉回 Mac | 30 个 npz 加 manifest，`PULL_OK 31` | `results/submission/pull_refs_mac.txt` |
| 起导出链 | 两台 `ARMED`，tmux 会话 `v2d-export` 在等方盒评测日志。预检 mf4090：23 行 `fc_export` 预检退出码 0，7 行还没训完（方盒 4 条与 Tier 2 ep23、25、27）；ml40：24 行可导，6 行还没训完（方盒 2 条、C 段 ep10 与 Tier 2 ep24、26、29）。两台都没有 FAIL；Tier 2 B 段已训完、还没评的几条提示“还没有干净的 4096 世界评测”，它们的评测排在导出之前 | `results/submission/exports/arm{,_dryrun}_mf4090.txt`、`results/ml40/submission/exports/arm{,_dryrun}_ml40.txt` |

## 接下来（自动）

| 时间（估计） | 机器 | 事件 |
|---|---|---|
| 10/2 06:15–06:30 | mf4090 | compat 跑完；之后在 Mac 上拉 t1-ep6、t1-ep8、t2-ep2 的导出做 E6、E7 预演（计划第 3.6 节） |
| 10/2 10:55 前后 | ml40 | compat 跑完；补 t1-ep12、t2-ep0 的预演 |
| 10/2 15:30 前后 | mf4090 | 方盒评测结束 → 导出链开始，约 1 小时 |
| 10/2 16:00–16:30 | ml40 | 方盒评测结束 → 导出链开始，约 1 小时 |
| 导出跑完后 | Mac | 拉回两台结果，两档打包，上传器只跑 `--dry-run`；先打包再写记录、提交（计划第 6 节第 7 步） |

## 打包预演 E6、E7（10/2 07:17–07:25，Mac，用 mf4090 兼容性验证的 3 条导出；判据 R1）

mf4090 的 compat 06:42:50 结束（`DAY2_EVAL_DONE（成功 7、失败 0）`，门槛 `完成 1`）。`pull_submission.sh compat mf4090`：`PULL_OK 6`
（t1-ep6、t1-ep8、t2-ep2 的 JSON 与 parquet，sha256 与远端一致；`results/submission/pull_compat_mf4090.txt`）。打包时工作树干净，代码链接指向 6a62bf0（已在 origin）。

| 项 | 命令 | 结果 | 落盘 |
|---|---|---|---|
| E6 Tier 1 | `pack_tier.sh 1 runs/submission/compat/t1 rehearsal 6 8` | 退出码 0，`PACK_OK（预演）`；1254 行。换算参考是发布的 Tier 1 数据，残差最大 1.02e-7 m、1.71e-7 rad；“converted 2 Track 2 episode(s) into the released frame” | `results/submission/pack/t1_rehearsal.txt` |
| E7 Tier 2 | `pack_tier.sh 2 runs/submission/compat/t2 rehearsal 2` | 退出码 0，`PACK_OK（预演）`；980 行。换算参考是 `runs/submission/frame_refs_t2`（v5.4），残差最大 8.78e-8 m、1.12e-7 rad | `results/submission/pack/t2_rehearsal.txt` |
| E7 反向对照 | `V2D_PACK_NEGCTL=1 pack_tier.sh 2 runs/submission/compat/t2 rehearsal_neg 2` | `NEGCTL_OK`：不给帧参考时打包器用发布的 Tier 2 带噪输入换算，报 “do not differ by one rigid transform（maximum residual 0.02475 m, 0.4122 rad）”，没有写出 CSV | `results/submission/pack/t2_rehearsal_neg.txt.failed`（预期中的失败） |
| 本地分数过滤 | Tier 2 两次的屏幕输出与落盘 | “locally computed” 都是 0 处（屏幕输出先存进 scratchpad 的文件，grep 计数为 0 后才显示） | 同上 |

判据 R1（mf4090 部分）：帧参考 `FRAME_REFS_OK 30`，E6、E7 退出码 0，反向对照 `NEGCTL_OK`，全部通过。ml40 的 t1-ep12、t2-ep0 等 ml40 的 compat 跑完再补。

只报：
- E6 的交叉核对：ep8 的四项与评测器的 JSON 一致；ep6 的 ADD-AUC 不一致，评测器报 0.632669，打包器按轨迹重算 0.629922（差 −0.0027，超过打包器的 1e-4 容差，所以打了 WARNING），
  ep6 的其余三项一致。原因没查（可能是打包器取网格顶点的文件或方式与评测器不同，属推测）。排行榜按轨迹计分，以打包器的数为准；本地 Tier 1 的 4096 世界 ADD-AUC 与排行榜的口径因此可能差几个千分点。
- E6 打出的 “locally computed: AUC=0.6660 SP-SR=1.0000 MP-SR=0.5000 MPPE=2.9988” 是 Tier 1 两条（ep6 单世界 MP-SR 0、ep8 为 1）的本地分数，只是预演。
- 打包器的换算残差在 1e-7 量级，说明 `check_export.py` 报的“评测器参考 vs motion parquet 朝向最大差 0.040–0.043°”是它没先归一化 motion 那一侧四元数造成的（box6 执行记录的推测由此得到证实）。
  这一项只报、不作判据；`check_export.py` 今天还要被导出链调用，先不改，链跑完后再修。
- 预演的 CSV 在 `runs/submission/csv/`（不进 git），只用于预演，不上传。

## 打包预演 rehearsal2（10/2 11:20–11:30，Mac，两台全部 5 条兼容性验证导出；判据 R1）

ml40 的 compat 10:17:21 结束（`COMPAT_PASS（3 行全部符合）`，门槛 `完成 1`，结论见 box6 执行记录）。`pull_submission.sh compat ml40`：`PULL_OK 4`
（t1-ep12、t2-ep0；`results/submission/pull_compat_ml40.txt`）。打包时工作树干净，代码链接指向 3b860a0（已在 origin）。

| 项 | 命令 | 结果 | 落盘 |
|---|---|---|---|
| Tier 1 | `pack_tier.sh 1 runs/submission/compat/t1 rehearsal2 6 8 12` | 退出码 0，`PACK_OK（预演）`；1954 行；残差最大 1.02e-7 m、1.71e-7 rad；3 条都换算到发布的世界系 | `results/submission/pack/t1_rehearsal2.txt` |
| Tier 2 | `pack_tier.sh 2 runs/submission/compat/t2 rehearsal2 0 2` | 退出码 0，`PACK_OK（预演）`；1758 行；换算参考 v5.4 帧参考，残差最大 8.78e-8 m、1.40e-7 rad | `results/submission/pack/t2_rehearsal2.txt` |
| Tier 2 反向对照 | `V2D_PACK_NEGCTL=1 pack_tier.sh 2 runs/submission/compat/t2 rehearsal2_neg 0 2` | `NEGCTL_OK`：两条都报不是一个刚体变换（ep0 0.03407 m、0.5071 rad；ep2 0.02475 m、0.4122 rad），没有写出 CSV | `results/submission/pack/t2_rehearsal2_neg.txt.failed`（预期中的失败） |
| 本地分数过滤 | Tier 2 两次的屏幕输出与落盘 | “locally computed” 都是 0 处 | 同上 |

**判据 R1 两台都通过**：帧参考 `FRAME_REFS_OK 30`，两轮预演退出码都是 0，两轮反向对照都是 `NEGCTL_OK`，Tier 2 没有本地分数那一行。

只报：Tier 1 交叉核对里 ep8 一致；ep6 的 ADD-AUC 评测器 0.632669、打包器按轨迹重算 0.629922（−0.0027），ep12 评测器 0.649375、打包器 0.671161（+0.0218）。
同一条轨迹两边算出的 ADD-AUC 不同，差在 ADD 本身（取哪些网格顶点），不在轨迹；排行榜用的是 kit 的算法（与打包器同一套 `v2dlb` 代码）。
所以本地 4096 世界评测的 ADD-AUC 与排行榜口径每条可能差到约 0.02，方向不定；原因是推测（评测器从仿真里的网格取顶点，kit 从数据集的 glb 取），没核实。

## 导出链的结果与拉回（10/2 13:56、14:26 跑完；20:03 拉回 Mac）

用户 15:14 要求 15:30 前停掉要靠 Mac 的任务，原定 16:47 的收尾（拉回、打包、预检）取消，晚上补做拉回与核对；打包与预检这次不做（见下）。

| 判据 | 结果 | 落盘 |
|---|---|---|
| X1 | 两台各 30 行：29 行 `ok`（都是最终 checkpoint 349,999,104 步，没有一行走退回），1 行 `no_done`（mf4090 的 Tier 1 ep7、ml40 的 Tier 2 ep7，两条方盒 ep7 都在训练中发散、没有 DONE） | `results/submission/export_tables_final.txt` |
| X2 | 两台最后一行都是 `EXPORT_CHAIN_DONE（成功 29、失败 1）`，ml40 13:56:53、mf4090 14:26:24 | `results/box/t2ep7_divergence_ml40.txt`、`results/box/export_end_mf4090.txt` |
| X3 | 两台都 `PULL_OK 59`（29 行各一个 JSON 与 parquet，加结果表本身），sha256 都与结果表一致 | `results/submission/pull_exports_{mf4090,ml40}.txt` |
| X4、X5 | 没做：两档的打包目录各 29 条、都缺 episode 7，打包器要求 30 条齐全 | 同上 |

按第 4 节的决策表，`no_done` 交用户定。两档 ep7 的处理另见 `agent-doc/plan-ep7-eval-and-guards-2026-10-02.md`：
发散前最后一份有限的 checkpoint 已评（候选条件满足，但 ADD-AUC 低于物体不动的基线，`agent-doc/experiments/2026-10-02-ep7-ckpt-eval.md`），
带非有限防护的重训在计划 B 部分，审查中。用哪一份补 ep7，等用户定；补齐之前两档都不打包。
jev（规格 `agent-doc/experiments/2026-10-02-submission-exports-final.claims.json`，结果 `results/submission/jev_claims_exports_final.txt`）：4 条全部核实（0.88–0.98），3 道对照题方向都正确。

## ep7 补齐之后：两档各 30 条的导出、打包与上传器预检（10/3 18:05–18:10，UTC-6）

两档 ep7 用带非有限防护的重训补上（`agent-doc/experiments/2026-10-03-ep7-nfg-retrain.md`：两条都跑完、最终 policy 有限、评测没有非有限世界、按批量判据通过）。
`export_map.py` 按 10/3 加的规则（同 episode 有 `-p185g-` 的 run 时只用它）重新生成清单，只有两档 ep7 两行变了（4f983e4）。两台用新日志名 `export2_<机器>`
各起一次导出链（`V2D_FC_SRC=<fc_8c778f9 副本>`，预检都是 `EXPORT_DRYRUN_OK`）：已有完整结果的 29 行由 `fc_export.sh` 直接复用，只新导 ep7。
打包时工作树干净，代码链接指向 c9d4013（已在 origin）。

| 判据 | 结果 | 落盘 |
|---|---|---|
| X1 | 两台各 30 行全部 `ok`，都是最终 checkpoint 349,999,104 步、没有退回；ep7 两行导出与核对都过，候选条件满足（4096 世界评测 world_count 4096、非有限世界 0、step_count 896、checkpoint 相同） | `results/submission/export2_tables.txt`、`results/submission/exports/export2_mf4090_*`、`results/ml40/submission/exports/export2_ml40_*` |
| X2 | 两台最后一行都是 `EXPORT_CHAIN_DONE（成功 30、失败 0）`（mf4090 18:07:13、ml40 18:07:33） | `results/submission/export2_end_mf4090.txt`、`results/ml40/submission/export2_end_ml40.txt` |
| X3 | 两台都 `PULL_OK 61`（30 行各一个 JSON 与 parquet，加结果表），sha256 都与结果表一致；两档打包目录各 30 个 JSON、30 个 parquet | `results/submission/pull_exports2_{mf4090,ml40}.txt`、`results/submission/export2_tables.txt` |
| X4 | Tier 1、Tier 2 打包退出码都是 0，各写出 22,989 行；换算残差最大 1.68e-7 m、1.71e-7 rad（Tier 1），1.52e-7 m、1.63e-7 rad（Tier 2）；Tier 2 的落盘与屏幕输出里 “locally computed” 0 处 | `results/submission/pack/t{1,2}_full30_1003.txt` |
| X5 | Tier 1：上传器预检 “looks valid”、四个排行榜各 “5 left today”、“--dry-run: nothing submitted.”，过。Tier 2：CSV “looks valid”，但预检停在 “You have not accepted the rules for” tier2-auc，按判据记为**用户待办**，不算流程失败；没有提交任何东西 | `results/submission/pack/t1_full30_1003_dryrun.txt`、`results/submission/pack/t2_full30_1003_dryrun.txt.failed` |

CSV 在 `runs/submission/csv/track2_tier1_full30_1003.csv`（sha256 870674f4…）与 `track2_tier2_full30_1003.csv`（sha256 3be33c68…），不进 git。

只报、不作判据：
- Tier 1 打包器按 1 个世界的轨迹算的本地分数：AUC 0.3780、SP-SR 0.5333、MP-SR 0.2667、MPPE 25.17（kit 的口径，每条 episode 1 个世界，与本地 4096 世界的评测不是同一个数）。
  Tier 2 的本地分数按干净参考算，照第 5 节滤掉，没有看。
- Tier 1 的交叉核对报“轨迹与评测器 JSON 不一致”，列出 10 条、另有 15 条，ADD-AUC 差 0.001–0.02。预演里已有同样的现象，ep6、ep12 两条的数与今天逐位相同
  （评测器 0.632669 对 0.629922、0.649375 对 0.671161），所以与这次 uv 装上的 trimesh 5.1.1（预演是 5.1.0）无关；原因仍按上一节的推测（两边取的网格顶点不同），没核实。

**第 1 步的现状**：两档各 30 条都导出、打好了 CSV；Tier 1 的 X1–X5 全过；Tier 2 的 X1–X4 过，X5 等用户在浏览器里接受 tier2-auc 的规则后重跑预检
（`pack_tier.sh` 不重打包的话，可以直接跑 kit 的 `v2d_submit.py <csv> --track track_2_tier2 -m … --dry-run`）。什么时候真提交、提交哪一档，由用户定；没有用户同意不上传。
