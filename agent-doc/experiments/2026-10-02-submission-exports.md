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
