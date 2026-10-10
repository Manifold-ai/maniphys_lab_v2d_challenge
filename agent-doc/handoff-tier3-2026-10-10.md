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
| `$T/runs/tier3_cari4d_f830_floor{,_suspect}` | + 主机位焦距统一 830 px 再地面校正（**交付版**）。10-10 12:22 验收：离地 \|中位\| 1.09 cm、最大 3.86 cm；主机位地面倾角 3.83°、尺度 0.9856，留一法 1.38 / 2.62 cm（`runs/floor/acceptance_f830.txt`） |

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

1. ~~看 `acceptance_f830.txt`~~ 已通过（10-10 12:22）；把 `tier3_cari4d_f830_floor` 交给 rxzhou（先用干净的 13 集），提醒他改打包路径。
2. 试点跑完后看跟丢比例变化，决定是否对 13 集铺开每帧重新配准（GPU，每集时长看试点）。
3. 修掩码选物规则（ep01/06/10）。
4. 物理后处理参考 rxzhou 的 `nopen.py`（不穿地）、静置段支撑面锚定、锚定段修正量插值；参数用 Tier 3 信号重定。
5. 问组委会（用户决定发不发）：主机位是否就是世界相机；另两个机位的 6 集怎么落到世界系。

未提交改动：无（本文件随 commit 推送）。

## 10-10 晚：选物规则、重跑队列、物理检查（commit 82ec841、85154fe）

- **rxzhou 页面（10-10 07:31 UTC-6）**：他的 Tier 3 试跑用的是校正前数据（悬空 115/146 mm，MP-SR 0.000）；页面上「校正版改了什么」列为待核实；
  Tier 3 物理后处理他那边没有，归我们；t2xa 训练预计 10-10 22:00（UTC-6）结束。
- **选物规则**（`t3_masks.py`）：ep01 选了被标成 vacuum 的三脚架、ep06 选了远处的显示器、ep10 的白桌因标签含 table 被当支撑面丢掉。
  改为：检测候选按 IoU > 0.4 连成轨迹，有轨迹平移 ≥ 0.15 倍对角线时只在被挪动的轨迹里选；物体本身是桌子时，标签点名物体的框不当支撑面。
  TRACK_IOU 是在这几集上定的（0.3 / 0.5 都救不了 ep01）。缓存检测上选择变化的 8 集：01 03 06 07 10 13 19 22，其中 01/06/10/22 人眼核对过。
  `probe_prompt_pick.py`：两个注入缺陷各自让它失败。
- **重跑队列**：`t3_reselect.sh` 写到 `runs/work_v2`、`runs/tier3_cari4d_v2sel_f830{,_suspect}`、`runs/track_check_v2sel/`，基线不动，
  焦距与地面拟合沿用 `focal.json` / `floor_fit_f830.json`。由第二个监视进程（`JOB=t3_reselect.sh t3_gpu_watch.sh ...`）排在试点之后，
  日志 `logs/t3_reselect.log`，末行 `RESELECT DONE`。判据：对比 `track_check_v2sel` 与 `track_check` 的 lost_fraction；ep22 是干净集，作对照，变差说明规则有问题。
  试点若中途让卡退出（exit 4），重跑队列会接着等空闲，试点剩下的集不会自动续。
- **物理检查**（`t3_physics_check.py` + `t3_physics_all.sh`，CPU）：闸门②各条判据改写成运动学版本，读交付 parquet。注入四种缺陷全部抓到
  （首轮发现平滑把 20 cm 跳变藏掉了，补了 `pose_jump`）。结果 `runs/physics/<版本>/out/`。
  - **主要发现：人体脚底普遍陷进地面**，f830 版逐集中位 −10.5 cm（ep12）到 +2.8 cm，多数在 −1 ~ −6 cm；同集静置物体只差 1~2 cm。
    地面校正版（CARI4D 原焦距）同样或更深，所以不是焦距 830 引入的。归因未定：CARI4D 的人-物相对深度，或 MHR→SOMA 转换。
    确认方法：在相机系里比较 CARI4D 原始 MHR 脚底与 SOMA 脚底到地面的距离。
  - 物体穿地：ep14 469 帧（与验收 −3.86 cm 一致）、ep12 122 帧。无手移动大的集（01 10 13 02 03）与跟丢检出一致。
- **脚陷地归因（10-11，`t3_feet_diag.py`，结果 `runs/physics/feet_diag_f830.json`）**：两部分叠加。
  (1) world 步的实现缺口：位置以相机为原点乘 s，身体不缩放，骨盆离地高度跟着乘 s、腿长不变，脚下沉 (1−s)×骨盆高；预测与实测 29 集最大差 0.83 cm。
  主机位 s=0.9856 → 约 −1.4 cm，第二机位 s=0.935 → 约 −6.5 cm。同一机制也让手相对物体偏 (1−s)×（手到骨盆的距离），第二机位约 3 cm（推断，未量）。
  (2) world 步之前 CARI4D 自身：脚相对我们按物体接触拟合的地面，主机位中位 −0.9 cm，范围 −5.0 ~ +2.8 cm（ep03/12/22/04/13/23 在 −4 ~ −5 cm）。
  修法待用户定：整体相似变换（身体也乘 s，人变矮 s 倍，手-物关系与脚-地关系都保留）vs 保持身体尺寸、只把骨盆抬回原离地高度（与图像不再严格对齐）。

## 10-11：相似变换版、第二机位配准、兜底（commit dfac8b2、fab949f、ae06e75）

- **当前最好的版本 `runs/tier3_cari4d_f830_simreg{,_suspect}`**：world 步把人体随场景整体缩放（`_scale_body`，容差为每集自己的
  MHR→SOMA 残差，29 集全过）；第二机位 5 集按 `runs/floor/camera_register.json`（偏航 181.35°，t = (−0.374, 5.826) m，ep00 地面
  基准）配准到主机位。`tier3_cari4d_f830_sim` 是只做缩放、未配准的版本；交付版 `tier3_cari4d_f830_floor` 未动，它依赖的
  world 文件备份在 `runs/convert_world_rigid_backup/`。注意 `runs/convert/*/` 里的 world 文件现在对应 simreg。
- 物理检查（`runs/physics/<版本>/`）：脚底中位 −2.20 → −0.85 cm，脚穿地帧 8895 → 5256；物体类检查不变。主机位剩余的
  −3.7 ~ −4.9 cm 下沉是 CARI4D 自身的，不是深度误差（跨集相关 +0.06），修法待用户定。ep25 / ep28 的脚离地 8–9 cm。
- 配准方法：去人背景图上 Grounding DINO（CPU）互相检测对方三脚架，方位定偏航，脚点距离按三脚架张开修正定距离
  （`t3_walls.py plates` → `t3_gdino_cpu.py` → `t3_mutual_multi.py ... camera_register.json`）。地面胶条、墙面、天花板三条路都
  试过，因场地对称或共同视野不足没定下来，代码不在仓里（`~/v2d/tier3/scripts/`）。**ep21 所在机位还没配准。**
- 兜底：焦距配置或地面校正里没有某集时显式降级（保留 CARI4D 焦距 / 退回相机系），打 FALLBACK 并写元数据。
- GPU 队列：试点（4 集）与 8 集重新选物仍在等 rxzhou 的链结束（10-11 05:33 仍忙）。8 集重跑走 `t3_reselect.sh`，它的 world
  步还是旧调用（不带配准），这 8 集都是主机位，结果不受影响。
- 问题链的因果梳理在用户本地 `~/v2d/tier3/tier3-problem-chain-2026-10-11.md`（不进仓）。
