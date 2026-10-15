# Tier 3 物体转动跳变：来源定位与修复试点（2026-10-15 晚 – 10-16，分支 `track2/tier3-recon`）

接 [handoff-tier3-dynamics-2026-10-14.md](handoff-tier3-dynamics-2026-10-14.md)（dyn 系列、自检流程、best_dyn7）。
写于 10-16 00:45 CST，代码提交 `0539247`（已部署 L40S），本文随后一次提交。**交付版仍是 best_hm**，dyn7、kf2 都是候选。

路径：`$T` = L40S `/lab_data/yqchen/v2d/tier3`，`$G` = `/lab_data/yqchen/v2d/gate`。本节诊断脚本在
`stages/recovery/tier3/gate/diag/`（服务器上的副本与输出在 `$G/diag/`）。

## 用户 10-15 晚的决定

- **人工标注不可用**：Tier 3 的任何修复（包括成段翻转选哪个分支）只能来自自动方法。
- 后处理侧桥接与卡尔曼效果上没有证据说桥接更好，**用卡尔曼**（`t3_kalman_post.py`）。
- 优先从重建侧找根源（yudong：成段翻转原则上也能用对加速度的全局稳健平滑修，但 CoCoNet 的问题从根源解决更好）。

## best_dyn7 复检结果（10-15 13:50 CST 跑完，`$G/dyn/recheck_dyn7.log`）

门槛只按地面 25/30（ep3、6、7、20、25 悬空约 755–791 mm，与 dyn6 同），用我们的支撑面 30/30（`$G/logs/oursup_bdyn7.txt`）；
重定向无失败。动力学违规帧 2162（hm 5654、dyn4 1799，`$G/dyn/tier3_bdyn7.json`）。手-物：标了接触而手离物体 > 3 cm 的帧
0.49%（hm 0.44%，`$G/dyn/ho_bdyn7.json`）。

## 已查明（数据见括号内来源）

1. **dyn7 的 541 帧 `rot_jump` 不是后处理造的**：528 帧与 best_hm 同帧（±1），只有 13 帧是新的；81% 在被拿着的段，成簇出现
   （94 簇，中位 3 帧；18 簇 ≥10 帧，合计 337 帧；最大 ep02 780–871、ep28 691–776 各 50 帧）（`$G/diag/rotjump.json`、
   `shape_bdyn7.json`）。dyn4 只有 70 帧是因为错误的对称判据把跳变转进了错误朝向，不是修好了。
2. **跳变按重建方法分布**（`runs/tier3_cari4d_f830_best.selection.json`）：选 `fp`（FoundationPose 每帧配准）的 13 集 457 帧，
   ep19 `override` 83 帧，`base`/`v2sel` 的 16 集合计 1 帧。注意混杂：`fp` 只在基线跟丢的难集上被选。
3. **跳变出在 CARI4D 第 06 步 CoCoNet，不是 FoundationPose**（`t3_stage_flips.py`，单帧转角 > 24°，相机系）：
   ep03/02/28/13 的 FoundationPose 输出 3/39/31/13 帧，CoCoNet 输出 35/112/88/54 帧（与 best_hm 逐集相同）。
   FoundationPose 连续但会整段落在错误分支：ep03 第 451 帧与视频确认正确的 hm 差 128°，ep01 第 223/238/301 帧差 40/43/88°。
4. **第 07 步后优化默认冻结物体旋转**（镜像内 `learning/training/mhr_opt_refineout.py`：`freeze_object_rotation=True`，
   时序项对物体只作用于平移；ep03 上 07 与 06 的朝向差最大 0.052°）。包装层有 `--optimize_object_rotation` 打开它。
5. 「换成跟踪模式」不是新方向：基线本来就是 `register-first-then-track`，在 ep02/28/13 跟丢 0.48/0.91/0.83，每帧配准版
   0.24/0.68/0.15。每帧配准本身已有时序筛选（参考上一帧确认姿态、重试转角上限、跟丢后确认帧）。

## 卡尔曼全量（`best_kf2`）

`$T/runs/tier3_cari4d_f830_best_kf2{,_suspect}`，`t3_kalman_post.py`（部署 `52542c8`）以 best_hm 为输入；重定向+门槛+动力学
在 `$G/dyn/run_kf2.sh`（日志 `run_kf2.log`，末行 KF2_DONE），结果 `$G/dyn/tier3_bkf2.json`（支撑面用 bhm 的）。

| 项 | dyn7 | kf2 |
|---|---|---|
| `rot_jump` / `rot_torque` | 541 / 541 | 189 / 259 |
| `rot_drift` / `lin_airborne` | 986 / 432 | 1122 / 542 |
| 违规帧合计 / 零违规集 | 2162 / 7 | 2080 / 5 |
| 门槛（地面） | 25/30 | 25/30（同 5 集不过） |

卡尔曼共 200 次朝向重置（连续 5 帧拒收后从观测重启），即它处理不了的成段翻转，集中在 ep02 35、ep19 27、ep28 25、ep03 21、
ep01 20 等 `fp` 集（`$G/dyn/kf2_post.log`）。

**两项变多的原因**（`gate/diag/kf_drift.py`、`ep06_sup.py`）：
- `rot_drift`（ep01 26→106、ep03 0→50、ep27 99→121）：静置段里卡尔曼仍逐帧用 3° 噪声的观测更新朝向，零角速度伪观测管不住
  朝向本身。ep03 第 0–92 帧重建慢慢转了 41°（dyn7 锁定记录 `turn_removed_rad` 0.711、替换 36 帧翻转），kf2 段首到段尾跟着转了
  42°，单帧都 < 24°；ep01 第 650–747 帧静置段里重建翻转 29 帧，kf2 重置后跟着翻，第 697 帧一步 91°。
  拟议改法（**未做，待用户定**）：静置段沿用 dyn7 的锁定（稳健均值、翻转帧替换、段内不重置），卡尔曼只管被拿着/空中的段与衔接。
- `lin_airborne`（ep06 0→91，第 455–545 帧）：检查用的是 bhm 的支撑面，范围 x 从 −1.352 起；dyn7 锁在 hm 位置，质心 x −1.343；
  kf2 平滑后 −1.356，出界 4 mm，于是按到地面算间隙 765 mm。高度没错。训练会把支撑面建成薄板，质心出板在仿真里会翻，所以要用
  kf2 自己的支撑面复检：**正在跑**（见下）。

## 试点与复检结果（10-16 02:05 CST，两项后台任务都已跑完）

**旋转优化试点**（`t3_rot_pilot.sh`，23:53–01:58，`$T/runs/work_rot/`，日志 `$T/logs/t3_rot_pilot.log` 末行 ROT PILOT DONE；
6 集都只重跑了 07、08 步）。对比用 `gate/diag/rot_compare.py`（v2d_cari4d 镜像内，挂 `work_fp` 与 `work_rot`）：

| 集 | 冻结旋转（原版）>24° / >60° / >90° | 优化旋转 >24° / >60° / >90° | 相对 CoCoNet 的改动 中位 / 最大 |
|---|---|---|---|
| ep03 | 35 / 5 / 3 | 18 / 4 / 2 | 2.9° / 8.5° |
| ep04 | 65 / 35 / 26 | 55 / 32 / 25 | 2.4° / 8.7° |
| ep01 | 56 / 19 / 15 | 47 / 18 / 15 | 1.4° / 7.7° |
| ep02 | 112 / 56 / 35 | 85 / 48 / 32 | 3.4° / 9.8° |
| ep28 | 88 / 44 / 33 | 87 / 40 / 31 | 1.6° / 8.7° |
| ep13 | 54 / 31 / 26 | 44 / 28 / 23 | 0.6° / 9.7° |
| 合计 | 410 / 190 / 138 | 336 / 170 / 128 | |

结论：打开旋转优化只去掉刚过门槛的小跳变（>24° 少 18%），>90° 的翻转只少 7%；任何一帧相对 CoCoNet 都没改超过 10°，
ep04 的三帧翻转（313/509/669）仍是翻的，ep03/ep01 原本对的帧改动 ≤ 8°。**这条路修不了成段翻转。**
为什么改动封顶在 10° 左右（学习率与步数，还是损失形状）没查；即使放开，梯度优化也只能从 CoCoNet 初值附近走，换不了分支（推断）。

**kf2 用自己的支撑面复检**（`$G/dyn/kf2_sup.sh`，末行 KF2SUP_DONE，`$G/dyn/tier3_bkf2_ownsup.json`）：结果与用 bhm 支撑面
几乎相同（违规帧 2080，ep06 仍 91 帧悬空）。原因：`t3_support_usda.py` 的支撑面来自固定的 `runs/support/tier3_cari4d_f830_best_v2`，
不随物体轨迹版本变，bkf2 与 bhm 的 ep06 支撑面完全相同（x −1.352 起）；kf2 的显示器质心 x −1.356，**确实在板外 4 mm**，仿真里
会从板边翻下。rxzhou 的门槛（`oursup_bkf2.txt`）判 ep06 过（底面间隙 −0.8 mm）：`stages/retarget/check_support_alignment.py`
是坐标系对齐检查，每集只判一次——取网格最低的 5% 帧，用这些帧全部顶点的 xy 均值（几何中心，不是质心）找它下方的板，
|间隙| < 20 mm 即过；不逐帧、不用质心。逐帧按质心 xy 选板的是我们的 `t3_dynamics_check.py`（`under` 用 `com`），ep06 就是它查出的。
之前「换成版本自己的支撑面就好」的说法不成立。静置段沿用锁定后 ep06 会回到 hm 的位置（dyn7 是 −1.343，板内 9 mm），这是推断。

## CoCoNet 推理侧还没试过的（10-16 查，不需重训）

- 滑窗：`clip_len` 96、`coconet_stride` 96，窗不重叠，`overlap_policy` first_occurrence。ep02/03/13/28 的 289 帧 CoCoNet 跳变里
  只有 9 帧落在 96 的整数倍上（随机约 3 帧），窗边界不是主因。重叠窗加投票预计收益小（推断）。
- 初值：CoCoNet 的输入含按初始姿态渲染的 RGB 分支（镜像内 `run_mhr_wild_inference.py`）。这 4 集 FoundationPose 的 86 个跳变帧
  有 80 个在 CoCoNet 里原样出现（`$G/diag/stage_flips_episode_*.json`）。推断：CoCoNet 的分支跟着初值走，换初值（基线跟踪版、
  对称/翻转候选）并按与分割掩码的一致性逐窗自动挑选，可能是不重训的根源修法；未验证，要 GPU。

## 接手怎么做

- （已做，见上）试点跑完后统计 6 集（在 v2d_cari4d 镜像里，CPU）：
  ```
  cd $T/runs/work_rot; A=""; P=""; for e in ep03_contigo_coffee_mug ep04_baseball_bat ep01_vacuum ep02_blue_easter_basket ep28_squeegee ep13_snack_box; do s=$(printf episode_%06d $((10#${e:2:2}))); A="$A -v $PWD/$e/cari4d/$s:/w/$e/$s:ro"; P="$P /w/$e/$s"; done
  docker run --rm --network none --user $(id -u):$(id -g) -e HOME=/tmp --entrypoint "" $A -v $T/code/stages/recovery/tier3:/s:ro -v $G/diag:/o v2d_cari4d:latest python /s/t3_stage_flips.py $P --out /o/stage_flips_rot.json
  ```
  对照 work_fp 的同一命令（10-15 的数字见上）。要看：大跳变（>90°）是否减少、对照帧（ep03/ep01 hm 对、ep04 hm 翻）有没有转错、
  `08_render` 出的视频（`inference/*_before_after.mp4`）里物体轮廓是否变差。
- 试点若只减小跳变：成段翻转仍需后处理兜底，方向是去掉重置的全局稳健平滑（yudong 思路）加上静置段锁定；要定「可拉回的最长
  翻转段」与区分真实快速转动的判据。试点若有效：把 07 改为打开旋转优化后的整条转换链（decode→world→assemble）在这 6 集上跑，
  再过自检流程。
- ep12 Q2 种子复核（rxzhou，10-15 23:20 CST）：dyn4 seed 43 MP-SR 0.000（seed 42 是 0.562），dyn4s seed 43 也是 0.000，
  `results/day2/eval_t3-ep12-…-dyn4{,s}-s43-ml40_s349999104.txt`（他的仓）。dyn4 在 ep12 上的提升没复现。
