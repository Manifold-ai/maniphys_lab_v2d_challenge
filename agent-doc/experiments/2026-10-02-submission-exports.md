# 执行记录：提交流程与两档各 30 条导出（10/2 凌晨部署，当天自动执行；不上传）

计划 `agent-doc/plan-submission-exports-2026-10-02.md` 第 2 版（06f41c3），按 Fable 5.1 的审查修改（GO WITH FIXES，没有 BLOCKER，计划第 9 节）。
时间一律 UTC-6；服务器日志是北京时间（UTC+8）。用户 10/1 23:50：“暂时先别提交任何内容”，本记录里的任何一步都不往 Kaggle 上传。

## 部署与预检（10/2 00:18–01:50，不占 GPU，在跑的链没动）

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
