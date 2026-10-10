# Tier 3 交接（2026-10-10，分支 `track2/tier3-recon`）

目标：用官方 CARI4D 从 30 段 exo 视频重建 Track 2 Tier 3 参考，交给 rxzhou 训练。机器：L40S（`ssh manifolds_l40s`），
根目录 `/lab_data/yqchen/v2d/tier3`（下文 `$T`）。部署副本 `$T/code`，`$T/code/DEPLOYED` 记 commit。

## 已定的规则口径

- Tier 2 的任何轨迹（人体也算）不进 Tier 3 链路（用户 10-10，Kaggle 2.8.c「easier tier's input」）。开发期也不再用 Tier 2 测误差；
  `t3_world_probe.py` / `t3_world_eval.py` / `t3_track_check_score.py` 是此前用过 Tier 2 的开发工具，结论只当背景。
- 只用 Tier 3 输入：exo 视频、官方网格、发布的 `ground_plane`、CARI4D 输出。

## 现在的数据版本（parquet，Tier 2 同 schema）

| 目录 | 内容 |
|---|---|
| `$T/runs/tier3_cari4d{,_suspect}` | 冻结基线：相机系当世界系（W=I） |
| `$T/runs/tier3_cari4d_floor{,_suspect}` | + 地面校正（CARI4D 原焦距），验收：静置物体离地 \|中位\| 1.14 cm、最大 3.86 cm（W=I 是 13.95 / 22.11 cm） |
| `$T/runs/tier3_cari4d_f830_floor{,_suspect}` | + 主机位焦距统一 830 px 再地面校正（10-10 11:20 起批处理，见下） |

「正式/可疑」是旧的剪影中位数门划分。按跟丢检出真正干净的约 13 集：ep00/05/08/12/14/18/20/21/22/23/24/26/29
（ep12/14/21 是另两个机位，水平位置离世界系几米，跟踪干净但不计分）。

## 后台进程（都在 L40S 上 setsid 脱钩，与会话无关）

1. `t3_world_all.sh`（焦距 830 → 重拟合地面 `runs/floor/floor_fit_f830.json` → world → assemble），日志 `$T/logs/t3_world_all_f830.log`，末行 `ALLDONE`。
2. `t3_after_f830.sh`：等 1 结束后自动验收，结果写 `$T/runs/floor/acceptance_f830.txt`（末行 `DONE`），含三个版本的离地高度对比。
3. `t3_gpu_watch.sh`：等 rxzhou 的 ml40 链真正结束（无 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs/.chain-active-*`、
   无 `flash_chord` 容器、空闲显存 ≥ 44 GB，连续 30 分钟）才启动重新配准试点 `t3_fp_pilot.sh`
   （ep28 刮水器、ep27 编织篮、ep19 手杖、ep03 杯子）。不抢他单集之间的停顿；试点每集开始前再查，他回来就让卡。
   日志 `$T/logs/t3_gpu_watch.log`、`$T/logs/t3_fp_pilot.log`（末行 `PILOT DONE`）。取消：`touch $T/WATCH_STOP`。
   试点结果：`$T/runs/track_check_fp/<ep>.json`（跟丢比例，对比 `$T/runs/track_check/<ep>.json`）、`$T/runs/tier3_cari4d_fp_pilot_f830/`。

## 本日结论（细节与数字在各脚本 docstring 与 commit message）

- 机位：3 个（`t3_camera_groups.py`）。主机位 24 集，3–6 月没动；第二机位 ep12/14/16/25/28；ep21 单独。
- 地面：我们重建的地面比发布地面多倾 ~4°，离相机越远越悬空，这就是 rxzhou 试跑里 ep8/ep24 悬空 115/146 mm 的原因。
  `t3_floor_fit.py` 每机位拟合，留一法验收 1.1 cm。
- 焦距：几何（天花板网格消失点）815–850 px；MoGe 821；DA3 868–897（ep05）；GeoCalib 942（单集不可靠）。用户定主机位用 830。
  另两个机位没有几何估计，保留 CARI4D 焦距。
- 单集剪影深度修正不做：地面给出的单集尺度一致到 ~1%（std 0.0072），剪影因子 std 0.06、相关 0.18，后者主要是掩码/网格偏差。
- 跟丢（`t3_track_check.py`，只用 Tier 3 信号）：整集错 ep01/10/28（+ep06 无产出）；大段丢 ep02/04/11/13/17/19/25/27；
  部分丢 ep03/07/09/15/16。ep01/06/10 是掩码选错物体，重新配准救不了，要改选物规则（选人在交互的物体）。
- rxzhou 的打包脚本 `stages/recovery/tier3_pack_remote.sh:12` 写死读 `runs/tier3_cari4d`（W=I 旧版），要请他改到新目录。

## 下一步

1. 看 `acceptance_f830.txt`；没问题就把 `tier3_cari4d_f830_floor` 交给 rxzhou（先用干净的 13 集）。
2. 试点跑完后看跟丢比例变化，决定是否对 13 集铺开每帧重新配准（GPU，每集时长看试点）。
3. 修掩码选物规则（ep01/06/10）。
4. 物理后处理参考 rxzhou 的 `nopen.py`（不穿地）、静置段支撑面锚定、锚定段修正量插值；参数用 Tier 3 信号重定。
5. 问组委会（用户决定发不发）：主机位是否就是世界相机；另两个机位的 6 集怎么落到世界系。

未提交改动：无（本文件随 commit 推送）。
