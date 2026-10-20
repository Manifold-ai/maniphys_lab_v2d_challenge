# Tier 3 物体转动跳变：来源定位与修复试点（2026-10-15 晚 – 10-16，分支 `track2/tier3-recon`）

接 [handoff-tier3-dynamics-2026-10-14.md](handoff-tier3-dynamics-2026-10-14.md)（dyn 系列、自检流程、best_dyn7）。
写于 10-16 00:45 CST，代码提交 `0539247`（已部署 L40S），本文随后一次提交。**交付版仍是 best_hm**，dyn7、kf2 都是候选。（10-18 起交付版是 `tier3_cari4d_gb4_best_dr2s_dyn7`，见下第一个「交付」节。）

路径：`$T` = L40S `/lab_data/yqchen/v2d/tier3`，`$G` = `/lab_data/yqchen/v2d/gate`。本节诊断脚本在
`stages/recovery/tier3/gate/diag/`（服务器上的副本与输出在 `$G/diag/`）。

## 交付：gb4_best_dr2s_dyn7（10-18 14:01 CST，当前交付版）

**交付版由 `tier3_cari4d_gb_best_dr2s_dyn7` 换成 `tier3_cari4d_gb4_best_dr2s_dyn7`**（用户 10-18 决定）。与 gb3 的唯一区别是 focal 步的修正
（下文「手物偏差的修复与重生成」，`e5ab7e5`）。**命名改了**：用户 10-18 改为另起名 gb4、不同名换入（rxzhou 已复制 gb3，同名换入要额外解释），
gb3 系列原地保留（`tier3_cari4d_gb_best_dr2s_dyn7` 在 versions.json 改标 kept，`gb_best`、`gb_best_dr2s` 仍是 candidate 并注明被取代）。
交付报告：版本目录 `DELIVERY.md`，仓库副本 [delivery-tier3-gb4_best_dr2s_dyn7-2026-10-18.md](delivery-tier3-gb4_best_dr2s_dyn7-2026-10-18.md)
（spec `$T/dev/audit/spec_gb4dyn7.json`）。支撑面 usda 来自 `$G/support_usda_gb4dyn7`。
**给 rxzhou：** 打包白名单需要加入 `tier3_cari4d_gb4_best_dr2s_dyn7` 与 `_suspect`；手持物体的集（ep01/02/04/07/09/16/25 等）接触帧有变化，可能要重训。

**怎么来的**：隔离根 `$T/dev/gbfix/root` 里全量重算（`gbfix.sh e5ab7e5`，focal 54 个转换目录 0 失败，人体顶点 p90 中位 12.5 mm、最大 23.0 mm），
配准步第一次因隔离根漏了只读输入 `runs/camera_groups`、`runs/moge_ground` 失败，补硬链接后只重跑配准（`gbfix.sh` 已改）。结果以新名移入
`runs/`：`convert{,_v2,_fp,_pivot}_gb4`（30/8/15/1 集）、`runs/floor/{floor_fit,camera_register}_gb4.json`、`dev/kgb/gb4_summary.txt`，日志 `$T/logs/gb4/`。
`t3_gb_chain.sh` 加了版本参数（`29a6d97`），`t3_gb_chain.sh gb4` 产出 `tier3_cari4d_gb4_best{,_dr2s,_dr2s_dyn7}`、门槛集 `gb4dyn7`
（日志 `$T/logs/gb_chain_gb4.log`）；`t3_align_check.py` 的 WORK 映射补了 `_gb4`（`3c021a9`）；自检 `$G/dyn/gb4_selfcheck.sh`（gb_selfcheck.sh 的副本）。
每集 `world_calib.json` 里地面文件的挂载路径仍写 `floor_fit_gb3.json`（隔离根里生成后改名），`floor_fit_sha256` 与 `floor_fit_gb4.json` 一致。

**结果（对 gb3 / f830）**：门槛 25/30 与 gb3 相同；标了接触的帧 18133（gb3 16496、f830 18263），手持集逐集回到 f830 水平；
ep16 第 130 帧 IoU 0.549 → 0.824、静置锁定 0–106 + 115–126（gb3 0–128）；动力学违规帧 2105（gb3 2056、f830 2189），变化大的集回到 f830 水平
（ep01 82/199/85、ep13 321/109/309）；轮廓 IoU 均值 0.806 → 0.805，IoU < 0.5 抽样帧 530 → 568（ep01 跨 0.5 阈值，三版都贴着 0.5）。
地面校正：主机位 0.964°/0.982（gb3 1.222°/0.984），二机位倾角 2.173°（gb3 1.181°），配准偏航二机位 181.53°、ep21 84.94°。

**已知问题（新）：ep11 的重定向。** 人手贴书（相机系右手到书中位 0.3 cm），但我们的重定向副本（rxzhou 的 eps.sh + 官方 `run_soma_to_g1.py`）在
右手 39 帧、左手 2 帧让机器人手离书 3.1–4.9 cm（第 551–558、636–693 帧）；gb3 在 655–688 帧机器人手是贴着的。重定向归 rxzhou 一侧，
推断是手臂姿态变化让 G1 的手落到另一个解，未核实。图 `$T/dev/gbfix/review/ep11_hand_gb3_gb4.png`（脚本同目录 `ep11_hand_render.py`、
`ep11_robot_extract.py`、`ho_frames.py`、`ep11_hand.py`，未入库）。ep16 第 105–125 帧 CARI4D 原始手离瓶 10 cm 仍在，另立。

## 交付：gb_best_dr2s_dyn7（10-17 22:49 CST，10-18 被上节取代，kept）

**交付版由 `tier3_cari4d_f830_best_dr2s_dyn7` 换成 `tier3_cari4d_gb_best_dr2s_dyn7`**（用户 10-17 决定：先给训练用，已知问题写明，之后修）。
自检六条第 1–5 条过、第 6 条看图未过（ep16），见 [selfcheck-tier3-gb_best_dr2s_dyn7-2026-10-17.md](selfcheck-tier3-gb_best_dr2s_dyn7-2026-10-17.md)。
交付报告：版本目录 `DELIVERY.md`，仓库副本 [delivery-tier3-gb_best_dr2s_dyn7-2026-10-17.md](delivery-tier3-gb_best_dr2s_dyn7-2026-10-17.md)
（spec `$T/dev/audit/spec_gbdyn7.json`，未交付时的草稿 spec 留在 `spec_gbdyn7.draft.json`）。支撑面 usda 来自 `$G/support_usda_gbdyn7`。
世界系是标定内参 GB（三台相机），与 rxzhou 的 kfix 主机位逐位相同。旧交付版原地保留（versions.json 标 kept）。
**给 rxzhou：** 打包白名单需要加入 `tier3_cari4d_gb_best_dr2s_dyn7` 与 `_suspect`。

**已知问题（主要一条，要修）：手物距离。** `t3_convert_ep.py` 的 focal 步里物体按点映射 `M = (f_new/f_used)·K_new⁻¹K_used`，人体只让骨盆按
`M`、其余部位随骨盆刚体移动。`M` 不是刚体（深度乘 k ≈ 1.04–1.09，主点平移 66 px 带来剪切），手偏 1–6.5 cm（主要沿视线，画面上约 1 px），
手持物体的集手物拉开：dr2s 层手到物体表面中位 ep01 1.9→7.1 cm、ep16 5.1→10.9 cm，ep02/04/07/09/10/19/25 0.4–1.8 cm；大件不变。
ep16 的看图失败是它的后果（握住判定 105→129 帧，静置锁定多 23 帧）。拆分（相对理想映射 `M`，握住帧）：接触手 3D 偏 2–5 cm，
物体最远点小件 ≤ 2 cm、大件 4–8 cm（ep10 书桌 8.1、ep00 吧凳 6.0）。诊断脚本与输出 `$T/dev/focal_hand/`（`focal_hand_diag.py`、`reproj_diag.py`）。
拟议修法（待用户定）：物体对 `M` 映射后的表面点做刚体最小二乘拟合；握住帧用手臂 IK 把接触手送到 `M·h0`。修后**以原名重生成** gb 系列（用户：不要 gb4）。**10-18 作废：用户改为另起名 gb4，见顶部交付节。**
另：自检第 5 条（标接触而手离 > 3 cm）没反映这个偏差，原因未查。

## 手物偏差的修复与重生成（10-17 夜 – 10-18，已完成，产出 gb4，见顶部交付节）

**修法（`f92c6b6`，已部署）**：focal 步不再让人体随骨盆刚体移动、物体绕中心转，改为各自拟合到点映射 `M` 下的自己——物体对映射后的
表面点做 Kabsch，人体用 SOMA `PoseInversion` 拟合映射后的网格（手、脚权重 5），拟合后按下游方式重建并对映射网格量偏差（p90 > 3 cm 拒绝）。
`focal` 多一个参数（官方网格），`t3_focal_all.sh` / `t3_world_all.sh` 已跟着改。

**试点证据（ep16、ep01，`$T/dev/focal_hand/`）**：相对 `M` 映射，接触手 p50 1.5–1.7 cm → 0.2–0.4 cm，脚底 4.5–6.0 cm → 0.3–0.4 cm，
骨盆 0 → 0.6–0.9 cm；握住帧手物距离（cam 系）ep16 p50/p90 0.59/5.29 → 0.41/1.92 cm（原始 0.36/1.62），ep01 2.15/8.93 → 1.00/2.62（原始 0.94/2.09）。
隔离根里跑完 dr2s + dyn7（`pilot/root`）：物理检查手物中位 ep16 10.8 → 6.8 cm、ep01 7.2 → 2.3 cm；脚低 0.1–0.2 cm（低于地面 2 cm 的帧
ep16 11.9% → 12.8%，ep01 2.4% → 3.3%）。对比图 `$T/dev/scene/compare_ep{16,01}_post.png`（`t3_scene_compare.py`，脚本在 `$T/dev/scene/`，未入库）。
新代码在 ep16 上与试点逐项一致（物体差 1e-7，人体顶点最大差 0.19 mm）。

**ep16 剩下的不是转换问题**：第 105–125 帧 CARI4D 原始结果手离瓶 10.4–10.8 cm（视频里已握住），试点版 115–127 帧仍判未握、dyn7 仍锁定，
锁定段从 0–128 缩到 0–107 + 115–127。要在 CARI4D 或握住判定（视频证据）那层修，另立。

**自检第 5 条的盲区（已修，同一提交）**：「标了接触但手离 > 3 cm」只数重定向标了接触的帧，手被拉开后标签跟着丢，帧从分母里消失
（交付版 ep01 217 → 156，比例 0.45% → 0.48% 不动）。交付报告现在逐集比较接触帧数，比上一交付版少 10% 以上的集列出来；在当前交付版上复跑列出 13 集。

**10-18 01:13 更新**：第一轮（`f92c6b6`，只有解析拟合）有 4 集（ep09/11/23/26）被 p90 > 3 cm 拦下；诊断（`$T/dev/gbfix/diag/`）显示只做解析拟合时
ep26 的手比旧刚体还远（p50 1.89 vs 1.03 cm），加 20 步 autograd 后 ep26/ep11 全身 p90 2.30/1.48 cm、手 p50 0.71/0.64、脚 0.81/0.63
（ep26 小腿 p50 3.5 cm，比刚体 1.2 cm 差）。改为解析 + 20 步 autograd（`e5ab7e5`，已部署），第一轮停掉（日志留 `gbfix_ag0.log`），
`gbfix.sh e5ab7e5` 在新隔离根从头重跑，预计约 2 小时。**这次换 autograd 是 agent 定的、事先没问用户**，用户回来时要汇报并听意见。
脚本跑到 GBFIX_DONE（或任一集被拦下时 GBFIX_FAILED）为止，不做任何换入、归档或交付。
**更正与腿部复核（10-18）**：上面的「ep26 小腿 p50 3.5 cm」其实是**大腿**（SOMA 的 `LeftLeg` 是髋/大腿，`LeftShin` 才是膝，诊断分组按名字分错）。
按正确关节在 ep26 复量（`$T/dev/gbfix/knee_check.py`）：加 autograd 后膝屈曲角相对原始改变 p50 约 3°、p95 约 9°、最大 9.7°（p95 角 87° → 93–96°）；
膝离 `M` 目标 p50 1.7–2.2 cm、p95 5.1–5.4 cm（旧刚体 2.8–2.9）；踝 p50 1.3–1.4 cm（旧刚体 2.5–3.9）；站立帧踝每帧位移 p95 4.7–4.9 → 6.0–6.4 mm。
**用户 10-18 判「还行」，接受 autograd 版。** 未验证：膝角只量了大小、分不出过伸；只测了 ep26；世界系下脚的穿地/悬空等整链物理检查。

**正在跑**：`$T/dev/gbfix/gbfix.sh`（日志 `gbfix.log`，末行 GBFIX_DONE/FAILED），隔离根 `$T/dev/gbfix/root`：四个 convert 源全量 focal →
`t3_gb3_register.sh`（地面拟合、两次配准、world、汇总 `root/dev/kgb/gb3_summary.txt`）。只读输入是硬链接，会被写的目录是真复制。
**之后（用户 10-17 同意的计划）**：新地面校正数值先给用户看（旧：主机位 1.222°/0.984，与 rxzhou GB1 一致）→ 旧 gb 系列与 `convert_*_gb3`、
两份 `_gb3` 地面文件归档进 `runs/archive/`（记 `MOVED.tsv`）→ 新的以原名换入 `runs/` → `t3_gb_chain.sh` → 自检 → 交付。**不起新名字（用户：不要 gb4）。** **10-18 作废：改为以 gb4 新名移入、不归档 gb3，已交付，见顶部交付节。**

## 交付：best_dr2s_dyn7（10-16 13:48 CST，已被上节取代）

**交付版由 best_hm 换成 `tier3_cari4d_f830_best_dr2s_dyn7`**（用户 10-16 下班前授权，按事先登记的规则选定）。交付报告（自检结果与基本数据）：
版本目录里的 `DELIVERY.md`，仓库副本 `agent-doc/delivery-tier3-best_dr2s_dyn7-2026-10-16.md`。支撑面 usda 由 `runs/support/tier3_cari4d_f830_best_v3`
生成，放在版本目录的 `support_surface/`（每集元数据 `support_surface` 路径），门槛用它 30/30。best_hm 原样保留。
**给 rxzhou：** 你的打包脚本按白名单读目录名，需要加入 `tier3_cari4d_f830_best_dr2s_dyn7` 与 `_suspect`；我们不改你的代码。
**规矩（用户 10-16）：** 以后每个交付版本都带 `DELIVERY.md`，由 `stages/recovery/tier3/gate/t3_delivery_report.py` 从各检查的结果文件生成，
`stages/recovery/tier3/t3_deliver.sh` 放支撑面并写报告。

**为什么不是 best_dr2s3_dyn7：** 用 v3 支撑面重做深度修正（`best_dr2s3`，当前代码 `14e2e3b` 先以 v2 支撑面逐表复现了 dr2s，然后换 v3），
只改了支撑面扩大的 5 集。交付规则第 1 条（相对 dr2s_dyn7 只许物体位姿变）没过：ep06/07/11 的人体平移也变了（`--move-human=3d`
让人跟随物体的深度修正，属设计行为，规则写窄了），按规则交付 dr2s_dyn7。dr2s3_dyn7 的其余检查在跑（`$G/dyn/regen_dr2s3.log`），
ep06 有 105 帧可见改动 > 5 cm（最大 12 cm），要用户看图后再决定是否换上。

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
   FoundationPose 连续但会整段落在错误分支：ep01 第 223/238/301 帧与视频确认正确的 hm 差 40/43/88°。（原写「ep03 第 451 帧与正确的 hm 差 128°」：10-16 用贴图渲染发现 hm 在 451 帧本身上下颠倒，见「对照帧检查」，作废。）
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
6 集都只重跑了 07、08 步；`work_rot` 已于 10-16 07:05 删除，统计结果保留在 `$G/diag/`）。对比用 `gate/diag/rot_compare.py`（v2d_cari4d 镜像内，挂 `work_fp` 与 `work_rot`）：

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

## 初值试点（10-16 06:35 起，等卡中）

**`fp_reliable` 的含义**（镜像内 `cari4d/prep/run_foundationpose_mhr_export.py` 逐帧循环、`foundationpose_pose_selection.py`
的 `filter_ranked_candidates`）：FoundationPose 每帧生成约 200 个候选（ep04 中位 202），按 FP 分数排序、取掩码 IoU 前若干名。
为 True 的情况：首轮在这些候选里找到与上一确认姿态转角 < 15°+2.5°×(距上次可见的帧数)、平移在自适应门槛内的候选，且物体最近
可见（时序过滤生效）；或重新捕获后连续若干帧一致而确认；或 register-first 模式的首帧。为 False：首轮没有合格候选而走重试
（交替 rgb/depth 细化，门槛放宽，最后一次接受任何候选）、沿用上一确认姿态（carried）、物体久不可见只按 IoU 选、深度无效。
即「与上一确认姿态连续」，不是「对」：错误分支被连续跟住时仍是 True（ep03 第 117 帧可靠而与正确的 CoCoNet 差 56°）。
不可靠帧绝大多数是重试帧：ep13 84/86、ep28 309/323、ep04 214/218；CoCoNet 跳变端点落在重试帧上 ep13 100/108、ep28 124/176。
连续不可靠段：ep13 最长 41 帧，ep28 ≤60 帧的段覆盖 253/323，ep04 最长 31，ep02 有 117–156 帧的长段。

**做法**（`t3_fp_init.py`，`7440c73` 之后 `84fa744` 部署）：CoCoNet 读 stage-05 pkl 的 `obj_pose_world`（`run_mhr_wild_inference.py:553`）。
每段 ≤ 60 帧的不可靠段，旋转在两侧可靠帧之间 slerp（段在首尾则沿用一侧），绕网格包围盒中心转，物体中心位置不变；
`fp_poses_cam` 按各帧相机重写；更新 05 阶段标记的输出身份，使 01–05 复用、06–08 重跑。`t3_init_pilot.sh` 在 `runs/work_init/`
的副本上做；`t3_yield_wait.sh` 等 rxzhou 的链结束、卡空 30 分钟后启动它，让卡退出（3/4）后重新等。

**干跑**（`$G/diag/init_dry/`，只改 pkl，不跑 GPU）：替换帧数 ep13 86、ep04 218、ep03 58；初值单帧 >24° 跳变 ep04 48→31、
ep13 13→8、ep03 3→2。对照帧：ep04 313/509/669（CoCoNet 头尾颠倒）新初值与 CoCoNet 差 114/175/155°（原 FP 128/59/70），
像是落到了正确一侧；ep03 第 451 帧新初值与 CoCoNet 差 162°（原 FP 128°）。原先把 451 当作「CoCoNet 对、会被带坏」的反例，
10-16 发现 hm/CoCoNet 在 451 本身上下颠倒，这个反例作废；451 的正确朝向要看试点输出的贴图渲染。

**判据（10-16 14:00 登记，试点出结果前定死）**：试点有效要同时满足——ep04 第 313/509/669 帧球棒翻正、ep03 第 117/131/345 帧不被改坏（用户看
`t3_pose_overlay.py` 坐标色图确认，对照 `checked_frames.json`）；被替换段内 CoCoNet（06）单帧 > 24° 跳变明显减少（`t3_pilot_compare.py`）；
轮廓 IoU 不变差。有效则对选择表里 `fp` 的 13 集重建初值、从 06 重跑（08 渲染可省，约 4–5 h GPU，与 rxzhou 错开），转换、组装新 best（其余 16 集
不动），再走 v3 支撑面 → dr2s 方法 → dyn7 → 自检 → `t3_deliver.sh`。修不了：长不可靠段（ep02，> 60 帧跳过）、FoundationPose 自信地错的帧
（ep03 第 451 帧），要靠每帧留多候选、全时间线选择。

**状态与恢复**：等卡日志 `$T/logs/t3_yield_wait.log`（末行 WAIT DONE），试点日志 `$T/logs/t3_init_pilot.log`（末行 INIT PILOT DONE），
集顺序 ep13、ep28、ep04、ep03。进程 `pgrep -af t3_yield_wait`。断了重挂（已完成的集跳过）：
```
cd $T/code/stages/recovery/tier3 && setsid nohup ./t3_yield_wait.sh t3_init_pilot.sh ep13_snack_box ep28_squeegee ep04_baseball_bat ep03_contigo_coffee_mug > /dev/null 2>&1 < /dev/null &
```
跑完后用 `t3_pilot_compare.py`（`runs` 挂 `/r`、官方网格挂 `/m`，参数 `/r work_init /m <out json> <集...>`；在 `work_rot` 上验证过，数字与 `rot_compare.py` 一致）统计，并与 `work_fp` 比较：06/07 的跳变数、被替换段内的跳变与轮廓重合度、
对照帧（ep04 应翻过来约 180°，ep03 117/131/345 不应变，451 现有各版本都错、看能否变对）；用 `t3_pose_overlay.py ... tex=1` 看贴图渲染。

**试点结果（GPU 14:40–16:16 CST 跑完；统计 21:37，`$T/dev/init_pilot/pilot_compare.{json,log}`）**，base = `work_fp`，pilot = `work_init`：

| 集 | 06 跳变 全部 base→pilot | 被替换段内 | 被替换帧轮廓 IoU p50 | 被替换帧 好/坏 >0.05 | 抽样帧 IoU p50 |
|---|---|---|---|---|---|
| ep13 | 54→48 | 51→45 | 0.334→0.375 | 26/15 | 0.902→0.897 |
| ep28 | 88→70 | 68→53 | 0.213→0.152 | 40/102 | 0.428→0.424 |
| ep04 | 65→48 | 52→32 | 0.676→0.616 | 19/63 | 0.809→0.814（1/8） |
| ep03 | 35→32 | 11→4 | 0.816→0.808 | 0/0 | 0.813→0.813 |

07 的跳变数与 06 相同（后优化冻结旋转）。对照帧：ep04 313/509/669 与 base 差 113/170/166°（IoU 0.56→0.51、0.57→0.52、0.33→0.43）；
ep03 117/131/345 差 0°（未被改动），451 差 162°。对照判据逐条：跳变在被替换段内减 12–64%；轮廓 IoU 在 ep28、ep04 的被替换帧上变差
（坏多于好 2.5–3.3 倍），这一条不满足；朝向要看贴图渲染，但 `t3_pose_overlay.py` 读组装后的版本，试点还没过转换与组装，图未出。

**贴图渲染（22:02，ep04 与 ep03，待用户判）**：只转换物体——`convert_fp` 整份复制，`object_cam.npz` 换成 work_init `refined.pth` 的
`pose_abs @ S2A`（`$T/dev/init_pilot/decode_object.py`），再跑原 focal（`focal.json`）、world（`floor_fit_f830.json` + `camera_register.json`）、
assemble 到 `$T/dev/init_pilot/root/runs/pilot_{ctrl,init}`（`runs/` 只读，未登记版本）。对照：`pilot_ctrl` 是同一条链不换物体，
`object_world.npz` 与 `convert_fp` 逐位相同（max abs diff 0.0）。人体沿用 fp，图里只看物体。构建脚本 `$T/dev/init_pilot/build_review.sh`；
宿主 venv 缺 h5py，装在 `$T/dev/init_pilot/pydeps`（`PYTHONPATH`），venv 未改。图：`$T/dev/init_pilot/tex_checked/`（ep04 313/509/669）、
`tex_checked3/`（ep03 117/131/345/451），列为 video | pilot_ctrl | pilot_init | best_dr2s_dyn7；`tex_auto/` 是 ctrl 与 init 差最大的 6 帧加首尾帧。

**用户判（22:10，记入 `checked_frames.json`，版本键 `init`）**：ep04 313/509/669 球棒朝向 init 全对，位置偏差大（拉低 IoU）；ep03 451 init 对
（坐标色图 `col_ep03/`）。**逐帧 IoU**（`$T/dev/init_pilot/frame_iou.py`，出图同一坐标系，`frame_iou_ep0{3,4}.jsonl`），ctrl / init / dr2s_dyn7：
ep03 451 0.52 / **0.63** / 0.50，452 0.57 / **0.71** / 0.59，117/131/345/435 三者差 ≤ 0.015；ep04（扣人体可见 IoU）312 0.51 / **0.55** / 0.52，
313 **0.56** / 0.51 / 0.56，458 0.46 / **0.59** / 0.50，509 0.57 / 0.52 / **0.60**，669 0.33 / **0.43** / 0.36。ctrl 的数与 `pilot_compare` 的 base 一致
（313 0.557/0.558），两条路径互证。**IoU 判据的盲区**：ep03 持杯帧的掩码几乎全在人体掩码里（可见像素 0–117），扣人体的 IoU 全部跳过，
`pilot_compare` 的被替换帧统计里持杯翻转帧缺席；球棒头尾翻转轮廓相近，IoU 主要反映位置。

## 版本整理（10-16 07:00–07:10）

版本的状态与用途只记在 `stages/recovery/tier3/versions.json`，`t3_versions.py` 据此和目录生成 `$T/runs/VERSIONS.md` 并核对
（目录里有却没登记、登记了却不在该在的位置，都报出来、退出码 1）。被取代的版本立刻归档。本次把 21 个过程版或废弃版（深度系列
d/dw/dc/dr/dr2/dr3/dr2s，高度 h/hchk/hm2，动力学 dyn/dyn1/dyn2/dyn3/dynr/dyn5/dyn6，kf1，sim，v2sel_f830，fp_pilot_f830）
连同 `_suspect` 与记录文件移入 `$T/runs/archive/`（57 项），它们在门槛环境的重定向副本移入 `$G/archive/`（39 项），每一项移动记在
各自的 `MOVED.tsv`。rxzhou 工具按名字直接读的 16 个目录（`tier3_pack_remote.sh` 白名单）原地不动，已逐个核对。删除只有
`runs/work_rot`（55G）。

## 卡尔曼静置锁定（`best_kf3`）

`t3_kalman_post.py` 加静置段锁定（`86ce869`/`889628a`）：静置段按 dyn7 的方式锁定（稳健均值、翻转帧替换、中位质心），滤波器把锁定
姿态当近乎精确的观测、不设门控；进入锁定段时若与预测差过门槛，就像重置一样切段，反向平滑不跨过去（否则 ep01 第 251 帧被拖了
153°）。`--no-lock` 与 kf2 逐位相同（4 集验证）。第一轮全量（`$G/dyn/run_kf3.log`，输出留在 `$T/dev/kf3_889628a/`）：

| 项 | dyn7 | kf2 | kf3 第一轮 |
|---|---|---|---|
| 违规帧 / 零违规集 | 2162 / 7 | 2080 / 5 | 1896 / 6 |
| `rot_jump` / `rot_torque` | 541 / 541 | 189 / 259 | 179 / 246 |
| `rot_drift` / `rest_drift` / `lin_airborne` | 986 / 1332 / 432 | 1122 / 1237 / 542 | 937 / 1349 / 452 |

kf2 的退步收回了（ep01 `rot_drift` 106→25、ep03 50→0、ep06 悬空 91→0），但相对 dyn7 只有被拿着段的两项变好：静置段本来就和
dyn7 同法。旋转重置 200→173，剩下的是被拿着时的成段翻转。ep02 `rest_drift` 26→150：第 269–272 与 274–393 帧两个静置段隔 2 帧、
锁定位置差 7.5 cm，检查把它们算成一个支撑段并从段首量漂移（dyn7 锁定相同，只是段首帧没落在过渡帧上）。修正 `9c3bfb2`：相隔
≤ GAP（5）帧的静置段合并锁定。以原名重生成并跑全套自检（`$G/dyn/regen_kf3.sh`，日志 `regen_kf3.log` 末行 REGEN_KF3_DONE）。

**kf3 重生成结果**（`9c3bfb2`，10-16 09:44 完成，`$G/dyn/regen_kf3_b.log`；第一次重生成空等 1 小时：旧的 `logs/bkf3_w*.txt`
让并行脚本以为 30 集都做完了，`regen_kf3.sh` 已补上清理）：

| 项 | dyn7 | kf2 | kf3 第一轮 | kf3 |
|---|---|---|---|---|
| 违规帧 / 零违规集 | 2162 / 7 | 2080 / 5 | 1896 / 6 | **1675** / 6 |
| `rest_drift` / `rot_drift` | 1332 / 986 | 1237 / 1122 | 1349 / 937 | 1126 / 839 |
| `rot_jump` / `rot_torque` | 541 / 541 | 189 / 259 | 179 / 246 | 178 / 244 |
| `lin_airborne` / `lin_supported` / `lin_held` | 432 / 391 / 14 | 542 / 400 / 49 | 452 / 389 / 49 | 452 / 373 / 49 |
| 门槛（地面）/ 我们的支撑面 | 25/30 / 30/30 | 25/30 / 30/30 | 25/30 | 25/30 / 30/30 |
| 标了接触而手离物体 > 3 cm（占标注） | 0.49% | | | 0.45%（hm 0.44%） |

合并只改变了 ep02（219→102，`rest_drift` 150→26）和 ep27（110→6）。ep13 没变（297）：上午「ep13 是锁定被切碎」的判断不对。
它的漂移从第 461 帧量起，那是一次脚推的末尾：第 440–461 帧人体层的脚离箱子 1.3–3.8 cm（碰到了），重定向后的机器人脚
9–12 cm（没碰到），箱子在第 461–476 帧又滑了 15 cm 才停（人脚已离开 10–14 cm）。所以 ep13 是重定向的接触缺口加推后滑动，
与 ep29 不同（ep29 的人脚本身就没碰到）。相对 dyn7 的进步里，ep02/ep27 来自静置合并，dyn7 若加同样的合并也会得到（推断）。

**对照帧检查（10-16 09:55，`t3_pose_overlay.py`，图在 `$T/dev/checked_frames/`）**：10 个对照过视频的帧上各版本与 hm 的夹角，
再看叠加图判对错。10-16 起用 `tex=1`（网格自身贴图）判：按坐标上色看不出杯盖朝哪头，ep03 第 451 帧因此被 10-15 误标为
「hm 对」，实际 hm 上下颠倒（用户看贴图图指出：杯把应在左上、hm 在左下）。其余 9 帧在贴图图上复核，原标注成立。

| 帧 | 视频里 | dyn7 | kf2 / kf3 |
|---|---|---|---|
| ep03 117 / 131 / 345（hm 对） | 杯把在左、手握杯把 | 0 / 3 / 6°，对 | 63 / 95 / 83°，杯把转到背后或右侧，错 |
| ep03 451（hm 上下颠倒） | 杯子斜握、杯把在左上 | 9°，与 hm 同样颠倒，错 | 137°，看不到杯把，错 |
| ep01 223 / 238（hm 对） | | 3 / 5°，对 | 1 / 3°，对 |
| ep01 301（hm 对） | 吸尘器斜向地面 | 0°，对 | 135 / 105°，立起来了，错 |
| ep04 313 / 509 / 669（hm 头尾颠倒） | 粗端在上 | 127 / 156 / 147°，仍颠倒 | 170–178°，粗端在上，对 |

dyn7 对 6 帧，kf3 对 5 帧（451 都错）：卡尔曼把 ep04 改对了，却把 ep03 和 ep01 第 301 帧改错了。机制相同：被拿着时，它按时间先后选分支
（沿用之前的朝向、拒收与之不符的观测），而不是按画面选；之前的朝向碰巧对（ep04）就修对，碰巧错（ep03）就改坏。所以
`rot_jump` 变少不代表朝向变对，kf3 不能算更好。成段翻转该选哪一支，需要画面证据。

**用户逐条复核（10-16 10:30）**：16 处看图判断由用户在坐标色叠加图上逐条确认，结果是唯一的对照答案，记在
`stages/recovery/tier3/checked_frames.json`（只用于评估，修复仍只用自动方法）。与上表不同之处：ep01 第 238 帧四个版本的吸头方向
都差约 90°（原判「都对」）；只算朝向，10 个对照帧上 dyn7 对 5、kf3 对 4。新发现的是位置问题：ep01 第 301 帧四版都比实物大一圈，
ep04 第 509/669 帧四版都偏上（只有粗端对齐），ep13 第 600 帧 hm/dyn7 偏上而 kf3 基本准，ep28 第 620 帧刮头都有偏移、kf3 最小。
把高度后处理之前的 `best` 也渲染出来（`$T/dev/checked_frames/review/pre/`）：ep04 的偏上在 `best` 里已经存在，所以不是后处理造成的，
出在 CARI4D 或转换（用户第二轮确认：best、hm、kf3 都偏高，best/hm 上下颠倒，kf3 朝向对）。ep13 第 600 帧则相反：best 最准、kf3 略高、hm 更高，
即高度后处理把箱子抬高了。高度后处理为消除穿地（ep13 处理前 76 帧低于地面）把物体竖直抬升（各集抬升中位数 −3 到 +6 cm），
画面上吻合的姿态在 3D 里穿地，说明地面估计或物体深度两者之一有误；竖直抬升会破坏画面吻合，沿视线移动（已归档的 depth_post
系列的做法）才能保住画面（推断）。ep01 第 301 帧第二轮：kf3 吸头朝向对但握把近乎竖直（应斜握在手里），best/hm 吸头朝向错。
CARI4D 自己的轮廓检查里 ep01 的深度因子中位 1.18（渲染偏大，物体放得离相机太近），与第 301 帧一致。
CARI4D 的焦距 806–831，与转换用的 830 相近，焦距不是主因（推断）。

**高度后处理让画面吻合变差（10-16 10:50，`$T/dev/audit/align_perframe.json`，10-15 跑的 best/hm 逐帧轮廓 IoU，两版此后未变）**：
30 集 4553 个抽样帧里，hm 比 best 低 0.05 以上的 1674 帧（36.8%），高 0.05 以上的 122 帧；20 集的中位 IoU 降了 0.02 以上，没有一集
升了 0.02 以上，逐集变化的中位数 −0.042。降得最多：ep02 0.810→0.471、ep27 0.810→0.529、ep28 0.403→0.172、ep04 0.780→0.550、
ep09 0.814→0.607。即交付版 best_hm 为消除穿地做的竖直抬升，在三分之一的帧上把物体移离了画面位置。沿视线修正的深度后处理系列
（已归档 d…dr2s；10-13 的替换判据里 IoU 0.8073 对 best 0.8101、通过了 IoU 一项）能同时保住画面，待重新评估。四版（best/hm/dyn7/kf3）
同口径复跑在 `dev/audit/align_4v.json`。

**支撑面扩大试验（10-16 12:30–12:47，已撤回）**：dr2s 在 ep07 用我们支撑面判门槛不过（749.8 mm），原因不是 dr2s 挪了熨斗（同帧位置差
中位 2 mm、最大 7 cm），而是 rxzhou 的 `check_support_alignment.py` 取最低 5% 帧的平均中心：hm 被高度后处理钳在 0.760 m，取到的帧散在整集、
中心落在板上；dr2s 有些帧底面 0.748 m，集中在熨斗被推到 x = −0.926 的时候，超出 v2 支撑板（x −0.880 至 −0.574）。试过把支撑板扩到
「底面贴着台面、时间上连着静置段」的滑动范围（`42f4a42`），再改成只取凸包离最低点 3 cm 内的接触部分（`73148db`），产出
`runs/support/tier3_cari4d_f830_best_v3`，投影图 `$T/dev/support_v3_overlay/`。用户看图判 v3 整体不如 v2：熨斗伸出桌沿、碗（弧形底）
反而变小；且物体本来就会被推出桌沿（ep11 拿书前先把书推到一半悬空，手才伸得进去），用物体位置反推桌面必然推大。两次提交已
`git revert`（`396d952`、`91f3e91`），复跑与 v2 逐字节一致；支撑面仍用 v2，v3 目录留作记录。dr2s 在 ep07 桌沿那些帧陷入桌面 1.2 cm，
未处理。ep11 在 v3 下新增的「穿入」多是书伸出桌沿边缘下斜，不当问题。

**best_dr2s_dyn7（10-16 13:15，`$G/dyn/run_dr2sd7.sh`、门槛 `logs/oursup_bdr2sd7.txt`）**：dr2s（从 best 沿视线修深度）上跑 dyn7 的动力学后处理
（`t3_dynamics_post.py` 改为在没有 height_post 记录时读 depth_post 的锚点，`ebad90b`）。同口径五版：

| 版本 | 违规帧 / 零违规集 | rot_jump | rest_drift | 悬空 | IoU（29 集） | 门槛（我们的支撑面） | 手物 |
|---|---|---|---|---|---|---|---|
| hm | 6207 / 0 | 696 | 2853 | 496 | 0.738 | 30/30 | 0.44% |
| dyn7 | 2162 / 7 | 541 | 1332 | 432 | 0.741 | 30/30 | 0.49% |
| kf3 | 1675 / 6 | 178 | 1126 | 452 | 0.749 | 30/30 | 0.45% |
| dr2s | 5723 / 0 | 696 | 2625 | 386 | 0.807 | 29/30（ep07） | 0.46% |
| dr2s_dyn7 | 2189 / 7 | 545 | 1308 | 274 | 0.810 | 30/30（v3 支撑面；v2 时 29/30） | 0.45% |

支撑面 v3（`1723b15`）：v2 的静置范围不变，另加滑动时质心经过处、外扩 2 cm（质心在桌上才站得住，所以不出桌面）；先试过整个凸包投影和
「离最低点 3 cm 的接触点」两版，用户看图否决（熨斗出桌沿、碗变小），已撤回。v3 只让 ep07 由悬空 750 mm 变为落板（陷入 9.7 mm），其余 29 集
门槛结果逐条相同；12 集静置范围与 v2 逐集相同。`oursup.sh` 加 `SUP_SRC` 指定来源（默认 v2）。dr2s_dyn7 的朝向问题未修，等初值试点。

**best_dr2s_dyn7 自检（10-16 13:20–13:45，按 `~/v2d/tier3/selfcheck-2026-10-15.md` 的清单）**：
数据契约（新工具 `gate/t3_contract_check.py`，变异测试：不允许任何列改动时报错）通过，dr2s → dr2s_dyn7 只改物体位姿，best → dr2s 只改物体位姿与人体平移；
逐帧对齐 IoU < 0.5 的帧（4553 帧中）best 545、hm 810、dyn7 813、kf3 819、dr2s 560、dr2s_dyn7 528；IK 误差与 hm 相当（ep28 最大值 2.24 → 2.89）；
改动审计（`gate/t3_pose_audit.py`，`$T/dev/audit/audit_{dr2s,hm}_to_dr2sd7.json`）dyn7 一步锁定段外可见变化 > 5 cm 的帧 537（ep28 263、ep19 117，
ep19 第 826 帧 1.07 m），这些帧与 16 个对照帧都由用户看图：没有变差，纸箱、刮水器明显变好，ep02 第 395 帧篮子三版都倒置（重建的朝向）、
dr2s_dyn7 位置最贴。动力学：违规帧占比 27.0% → 9.5%，前 30 帧内就违规的集 30 → 3，首次违规帧中位 0 → 212。未做：合成轨迹空跑与幂等性、
每帧可信度（工具从未写），dr2s 本身无来源记录（10-13 生成）。

## 违规最多的三集（10-16 诊断，`gate/diag/unheld_runs.py`，在 bdyn7 上；三类漂移/悬空在各版本几乎不变）

kf3 第一轮违规的 79% 在 6 集：ep28 396、ep29 345、ep13 297、ep02 219、ep19 124、ep27 110。
- **ep13 纸箱**：上午判为锁定被切碎，kf3 重生成后证伪，实际原因见上（重定向的接触缺口加推后滑动）。
- **ep29 带轮行李箱（重建的接触缺口，原因未定位）**：任务是用左脚推。物体轮廓与视频吻合（IoU 中位 0.80），箱子真的在动。
  人体层（best_hm）脚掌/脚趾顶点到箱面距离在 5 次推的间隙段最近 6.4/19.0/6.6/7.9/9.8 cm，箱子在动的帧里人脚 ≤ 5 cm 的帧为 0；
  重定向后机器人再远 5–9 cm（`gate/diag/ep29_human_feet.py`，输出 `$G/diag/ep29_human_feet.npz`）。人脚从未投影回视频验证过，
  深度由地面间接定出，所以缺口出在物体、人脚、地面还是尺度上分不清。用户 10-16 定：不做接触修正（其前提是人脚和物体都准，
  现在保证不了），先记下。另有未解释处：箱子在 301/467 帧上速度 > 5 cm/s，而推只有 5 次。
- **ep28 刮水器（重建失败）**：视频里全程双手握着来回扫（第 620、720 帧），重建里手离物体 20–40 cm、物体离地最高 84 cm；
  `fp` 版、跟丢 0.68、轮廓 IoU 0.43。后处理修不了，ep28 在初值试点里。

用户 10-16 的原则：重建对了，检查怎么判不重要（检查是自查工具，不是评分）；不为迎合检查改数据。

## 接手怎么做

- （已做，见上）试点跑完后统计 6 集（在 v2d_cari4d 镜像里，CPU；`work_rot` 已删，命令只作记录）：
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

## 内参与发布地面的一致性（10-16 23:xx CST，`t3_intrinsics_floor.py`，结果 `$T/dev/intrinsics/{grid,scan_pp}.json`）

方法与重新表达照搬 rxzhou 的 `t3_floor_tilt_k.py`（p1-training），发布地面改从 Tier 3 input 经 `t3_inputs` 读；714 个主机位地面事件、13 集、
CARI4D 位姿取 `runs/convert`。对照（流程焦距步 830）复现 3.83°，「深度随 f、GB 主点、866.3」复现他的 GB1 行，「深度不变、GB、866.3」复现 GBZ。
- **cy 是主因**：主点居中（cy 576）时倾斜 3.4–3.9°、接触点高 +14 至 +16 cm；cy 换到 531 后倾斜约 1.1°、高度约 0。只扫 cy（cx 768、f 851.3、深度随 f）：
  俯仰为 0 在 cy≈524，高度为 0 在 cy≈530，斜率为 0 在 cy≈523——地面自己定出 cy 约 523–531，与方格拟合的 531 一致。
- **cx 地面定不住**：cx 680–810 倾斜 1.11–1.36°、高度 −0.3 至 +0.4 cm，768 附近略好；不支持也不否定 701.8。约 1° 横滚各组都在。
- **f 地面定不住（深度随 f 口径）**：821–882.5 之间高度只差约 1.3 cm（cy 531：+0.9 → −0.4），小于逐集中位的 p10–p90 宽度（约 3.5 cm）；
  这一口径下横向坐标不随 f 变、只拉深度，地面对 f 天然不敏感。深度不变口径对 f 敏感（821–830 高度约 0，866 为 +4.3 cm），但它的斜率与倾斜
  整体比深度随 f 口径差（2–3 cm/m 对 0.7–1.3），数据更像深度随 f。

## 世界系第 1 步：focal 步骤改成任意内参（10-16 深夜）

用户定（rxzhou 指示）：主机位内参用 GB f 866.3、cx 701.8、cy 531.1（p1-training `stages/recovery/kfix/kt_gb.json`，原始 1536×1152 画面，
畸变忽略；CARI4D 导出同为 1536×1152，不缩放）。第二、侧机位先不套，套之前要看地面倾斜与地平线是否对得上。
- `t3_convert_ep.py focal`：spec 新增 `intrinsics`（{组: {f, cx, cy} 或 null}），旧 `focal_px` 照用。点映射 M = (f_new/f_used)·K_new⁻¹·K_used
  （像素不变、深度随 f），主点不变时退化为原来的 diag(1, 1, k)。`focal_calib.json` 多记新旧主点。
- `probe_focal_intrinsics.py`：合成位姿上像素不变（4.6e-13 px）、深度比、物体朝相机的一面不变、主点不变时等于旧公式、spec 解析；注入
  「忽略主点」缺陷时探针 FAILED。真实数据：旧 `focal.json` 在 L40S 全部 54 个转换目录上复现现有 `object_cam_focal.npz`（≤ 1e-6 m；
  ep19 pivot 目录 5.6e-8 m，因 CARI4D 的 float32 K 有 fy/fx−1 = −7.4e-8，新映射保持像素、旧式忽略了它）。
- ep04 副本（`$T/dev/kgb/try/`，spec `$T/dev/kgb/intrinsics_gb.json`）完整跑 focal：像素变化 3.4e-13 px、深度比 1.051107、人体刚体误差
  0.0014 mm；物体相对 f830 结果移动中位 29.7 cm、最大 39.6 cm。
- 未做：第 2 步地面校正重拟（`t3_support.py` 写死 `floor_fit_f830.json`、`t3_versions.py` 前缀写死 `tier3_cari4d_f830_`，要参数化）；第 3 步
  新转换目录与整链重跑。另：10-16 post_review 的对照里人体 identity_coeffs 重跑差 0.0056（物体逐位一致），world 步人体重拟不完全可复现。

## 世界系第 2 步：GB 内参下的地面校正（10-16 23:30 CST）

`t3_focal_all.sh convert convert_kgb intrinsics_gb.json`（部署 `16c2b7f`）：30 集 focal 全过，主机位 24 集 (866.3, 701.8, 531.1)，第二、
侧机位保留 CARI4D 内参（spec 里 null，与 focal.json 相同）。`runs/convert_kgb/` 只含 focal 及其起点文件，`runs/convert*` 未动。
`t3_floor_fit.py ... floor_fit_kgb.json convert_kgb`：主机位组倾斜 1.222°、缩放 0.98400（d_ours 1.4102 / 发布 1.3877），与 rxzhou GB1 行一致；
第二、侧机位组与 f830 版相同（内参没变）。**留一法：校正前接触点高度逐集中位的绝对值中位 1.04 cm，留一校正后 1.53 cm（最大 2.32 cm）**——
f830 时校正把 15.6 cm 降到 1.4 cm，GB 下校正不再改善留一高度：13 集里 7 集变好（ep04/05/08/23/26/27/29）、5 集变差（ep15/17/18/22/24），
都在 ±3 cm 内。推断：0.984 的缩放主要来自把 1.2° 倾斜的平面外推到相机原点，未核实。主机位世界系要不要再做地面校正，待用户定。
- **用户定（10-16 23:45）：主机位保留地面校正（`floor_fit_kgb.json`，1.222° / 0.984），与 rxzhou 的 k-fix 对齐。**

## 第二、侧机位能否套 GB 内参（10-17 00:xx CST，`t3_register_check.py`，结果 `$T/dev/register_check/register_check.json`）

「落地点拟地面 vs 地平线」分不出内参（两者由同一批像素经同一线性映射得到，任何内参下都吻合），改用经主机位的测量：
- A 主机位（GB、发布地面、floor_fit_kgb）看第二机位：23 个去人背景里 18 个脚点距离 < 6.2 m（另 5 个 6.5–8.5 m，像是那几天二机位挪过位），
  三脚架中心中位 6.170 m、二机位机头离地中位 1.338 m、方位 89.18°。
- B 二机位自己落地点拟出的离地高度对内参不敏感：GB 1.4866 m、CARI4D 自身 1.4859 m（ep12/14 共 149 个事件）。
- 两条独立途径给二机位重建的尺度：(1) 互相看到的距离之比；(2) 高度——二机位看到的主机位机头 1.384 m（主机位真高 1.388）、主机位看到的
  二机位机头 1.338 m、二机位自测 1.4866 m，联立解出机头框中心比镜头低约 7.4 cm、尺度 1.053、二机位真实离地约 1.41 m。
  **GB：距离比 1.054 与高度尺度 1.053 一致；CARI4D 自身内参 0.998 对 1.054、自身 f 加 GB 主点 1.002 对 1.053，都不一致。** 偏航 GB 下 181.37°
  （原配准 181.35°）。ep28 排除（距离 4.97 m、方位 89.4°，与其余四集不同）。分辨力主要来自 f；主点只影响偏航（居中主点给 176.83°）。
- 更正：此前说二机位组地面校正的缩放 0.935「把二机位缩小 6.5%、是建模错误」不对——二机位真实高度约 1.41 m，与主机位相近，那套做法
  只差约 1.5%（按尺度 1.053 应为 0.949）。
- 侧机位 ep21：自己的落地点只有 38 个、几乎排成一条线（横向跨度 1.3 cm），拟不出地面（拟出离地 0.66 m、俯仰 +12°，不可信），这条路检验
  不了；主机位画面里也只看到二机位，没看到侧机位。侧机位要换办法（地平线/吊顶消失点定俯仰横滚，或借二机位链条）。

## 三台相机都用 GB：后台流程（10-17 00:16 CST 挂上，用户出门）

**用户定（10-17）**：二机位用 GB、尺度 0.949（= 1/1.053）；ep21 也用 GB，按 10-12 的 A、C 配对（left = A）重做配准；交付记录要写明
ep21 做过的测试——「证据不足，但做过检验，不是直接套的」。

**ep21 做过的检验（写进交付记录用）**：
1. 地面接触点拟地面：38 个事件几乎共线（横向跨度 1.3 cm），定不住法向（拟出离地 0.66 m、俯仰 +12°）——此路不通。
2. 吊顶地平线定法向 + 接触点定高度，量它看到的 A、C 三脚架中心距：GB 6.42 m、CARI4D 自身 804 6.37 m、自身 f + GB 主点 6.43 m
   （腿偏移 0.29 m），三者差 < 1%，分不出内参；对主机位视角 6.170 m 的比值 1.04–1.10（随腿偏移）。
3. 同一消失点方法（k1 = 0、主点居中）的焦距：ep21 835.5，二机位 842–852，主机位 ep00 846（该方法在主机位比 GB 866 低约 2%）——同型号的旁证。
4. GB 下 ep21 地平线横滚 0.02°、俯仰 −1.61°，接触点离地 1.404 m（p10–p90 1.400–1.406），自洽。
结论：落地/距离检验分不出 GB 与 ep21 自身内参，按同型号旁证采用 GB，属证据不足下的决定。

**产物与流程**（代码 `25affe5`，`t3_gb3_register.sh`，日志 `$T/logs/gb3_register.log`，末行 GB3_REGISTER_DONE 或 GB3_FAILED <步骤>）：
- 规格 `runs/floor/intrinsics_gb3.json`（三组 GB）；focal 输出 `runs/{convert,convert_v2,convert_fp,convert_pivot}_gb3/`（`logs/gb3_focal.out`）。
- 地面 `runs/floor/floor_fit_gb3.json`（二机位 scale=1:0.949 → shift_m；ep21 法向取 `runs/floor/ceiling_vp_other.json` 的吊顶地平线）。
- 配准 `runs/floor/camera_register_gb3.json`：二机位 t3_mutual_multi（conv=convert_gb3）；ep21 t3_corner_register（pair= 固定为
  `dev/kgb/ep21_original_pair.json` 的两个框：左裁图 [0,752,67,861]、右边缘 [1385,579,1535,821]；旧配置下复现 90.55° 逐位一致）。
- 四个 `_gb3` 来源全部 world；摘要 `dev/kgb/gb3_summary.txt`（各组落地事件在新世界系的离地高度 vs f830 版；新旧配准对比）。
- 代码改动：floor fit 的 `scale=`/`horizon=`、`shift_m`（world、mutual、corner 都沿发布法向平移）；corner 的图宽改取 CARI4D 居中 K
  （原写法 2·cx 在 GB 下会把右裁图错位 132 px）。旧配置回归：floor_fit_kgb 逐字段一致、二机位 181.35°/(−0.3737, 5.8261) 与 ep21
  90.55°/(3.0119, 2.895) 逐位复现。
- 已清理：`runs/convert{,_v2,_fp}_gb2`、53 个 gb2 日志（清单 `dev/kgb/gb2_logs_deleted.txt`）、`intrinsics_gb2.json`、`dev/kgb/try`、
  `dev/init_pilot/post`。保留：`dev/init_pilot/conv_{ctrl,init}`（checked_frames 的 init 判断出自它们）、`runs/convert_kgb`（floor_fit_kgb 的来源）。

**回来后**：先看 `gb3_register.log` 末行与 `gb3_summary.txt`（二机位、ep21 落地高度应在 ±3 cm 内；二机位偏航应近 181.4°）。之后是组装与后处理链：
按 best 选择表换成 `_gb3` 来源组装 → 支撑面（`t3_support.py` 写死 floor_fit_f830，要参数化）→ 物理 → dr2s → 物理 → dyn7 → 门槛 → 自检 → 交付；
`t3_versions.py` 前缀写死 `tier3_cari4d_f830_`，新版本名待定。

## 待办：CoCoNet 初值不能只靠相邻两个可靠帧（用户 10-17 要求解决；rxzhou 同样提醒）

现状 `t3_fp_init.py`：每段 ≤ 60 帧的不可靠段，在两端相邻可靠帧之间 slerp。问题：`fp_reliable` 只表示与上一确认姿态连续，不表示对；
两端都可能在错的分支上；> 60 帧的段跳过；FoundationPose 自信地错的帧（ep03 451）不在不可靠段里，插值碰不到。
事实（10-17 查）：stage-05 pkl 只存了选中候选（`fp_poses_cam`、`fp_selected_candidate_index`、`fp_candidate_count` 约 200），**没存候选本身**；
带 gt/oracle 字样的字段全空（`fp_oracle_rotation_error_deg` 803 帧全 NaN，metadata `gt_object_pose_available: False`、
`foundationpose_selection_uses_gt_pose: False`），选择没用真值。
候选方案（待用户定）：(1) FoundationPose 每帧存前 K 个候选（要改导出、重跑 05，GPU），全时间线 Viterbi 选择：代价 = 掩码 IoU/FP 分数 + 相邻帧
转角（对称等价按 t3_symmetry 取最小）；(2) 手持段用手腕转动传播朝向，锚定段内所有可靠帧（最小二乘），只用 CPU，松手/换手处失效；
(3) 二者结合：(2) 作为 (1) 的转移代价先验。建议 (1)+(2)。

### 静置段锚初值（CPU 简化版）干跑：否定（10-17，`t3_fp_init_rest.py`，未上 GPU）

做法：静置段（dr2s 的 anchors，物体静止；ep29 被踢滑动的帧不算静置）整段投票取朝向；运动段在 FoundationPose 位姿与其绕三根主轴的半圈翻转
4 个假设上做最小总转角的动态规划，两端钉在相邻静置段朝向（翻转代价可靠帧 10°、不可靠帧 2°）。ep04/03/13/28/29 干跑，对照帧（慢插值试点的
CoCoNet 输出用户判过朝向对）：ep04 313 新=FP（与试点差 120°，没修）；509/669 新把 FP 翻 180°，但与试点差 86–90°（翻错轴）；ep03 451 新=FP
（与试点差 39°，没修）；ep03 345（原本对）被改 51°。原因：(1) FP 的错大多不是整半圈（试点相对 FP 差 120/129/142/39°），4 个假设里没有对的；
(2) 静置段里 FP 自己也乱（ep03 各段 15° 内只占 33–65%），多数票不一定对。结论：两端静置锚 + 中间全局最优的框架可留，但候选必须是 FP 真实的
~200 个候选（改导出、重跑 05，GPU），静置段投票要加掩码/纹理证据。脚本留作记录，不部署到流程里。

**GB3 流程进度（10-17 00:40 CST）**：第一次跑到 world 全部失败（导出给 xargs 子 shell 的函数用了 bash 数组，数组不随函数导出，docker 命令变成以
`-v` 开头），`3751a7d` 修复后重跑，复用已产出的地面拟合与配准，前 3 集 world 已过（主机位 scale 0.984、shift 0）。已产出：二机位 GB 配准偏航
181.38°、t = (0.0884, 6.1785) m，双向脚点距离差 0.007 m（旧 0.143 m）；ep21 沿用 10-12 那对框，两点距 5.995 m 对 A–C 6.179 m（短 3%）。
等 `logs/gb3_register.log` 末行 GB3_REGISTER_DONE 与 `dev/kgb/gb3_summary.txt`。

**新内参版本整链（10-17 00:43 CST 挂上，`ca3ecf0`）**：用户定前缀 `tier3_cari4d_gb_`。`t3_gb_chain.sh` 等 `gb3_register.log` 出 GB3_REGISTER_DONE 后：
组装 `tier3_cari4d_gb_best`（best 的逐集选择，转换目录换成 `_gb3`，主/`_suspect` 划分同 best）→ 物理 → 支撑面 `runs/support/tier3_cari4d_gb_best`
（`T3_FLOOR_FIT=floor_fit_gb3.json T3_REGISTER=camera_register_gb3.json`）→ dr2s（`--move-human=3d`）→ 物理 → dyn7 → `gate/chain_check.sh`
（`SEL`/`SUP` 指向 gb，门槛集 `gbdyn7`）。**停在交付之前**（交付改 rxzhou 读的数据，等用户看过）。日志 `logs/gb_chain.log`，末行 GB_CHAIN_DONE 或
GB_CHAIN_FAILED <步骤>；门槛 `$G/logs/p2_gbdyn7.txt`、我们的支撑面 `$G/logs/oursup_gbdyn7.txt`、画面对齐 `$T/dev/depth_diag/align_gbdyn7.json`。
三个版本已登记为 candidate。注意：dr2s 用的是当前支撑面代码（v3 规则，含质心扫过），交付版 dr2s 当时用 v2；用户核对时一并看。
**第一次运行失败（10-17 01:13）**：world 54 集全部 ok，但摘要步骤的 docker 调用没带 `-i`，heredoc 没传进容器，`gb3_summary.txt` 为空，于是报 GB3_FAILED，整链随之停下（没组装）。`cd8ba69` 补上 `-i`，11:54 两个脚本重新挂上（地面拟合与配准沿用，world 重跑）；第一次的日志改名为 `logs/gb3_register.run1.log`、`logs/gb_chain.run1.log`。单独试跑过摘要：ep21 配准偏航从 90.55° 变为 85.01°，t 从 (3.01, 2.90) 变为 (3.58, 2.41)；二机位偏航 181.35°→181.38°，t 从 (−0.37, 5.83) 变为 (0.09, 6.18)。地面事件接触高度新旧相近，ep14 中位数从 −3.7 cm 变为 −2.3 cm，ep00 从 −2.1 cm 变为 −1.0 cm。
**交付规则（用户 10-17 中午授权「通过自检就交付」，条件在看结果前登记；随后用户改为 10-18 自己看结果再定，授权收回，以下六条作为看结果时的判据，agent 不自行交付）**：自检脚本 `$G/dyn/gb_selfcheck.sh`（日志 `$G/dyn/gb_selfcheck.log`，末行 SELFCHECK_DONE）在整链后跑动力学检查（支撑面用 `$G/support_usda_gbdyn7`）、手-物、逐帧对齐、契约、改动审计。六条全过才把交付版换成 `tier3_cari4d_gb_best_dr2s_dyn7`，否则保留 `best_dr2s_dyn7` 等用户：1 整链完成、30 集、代码 `cd8ba69` dirty=0，契约 gb_dr2s → gb_dr2s_dyn7 只改物体位姿；2 我们的支撑面门槛 30/30；3 逐帧 IoU < 0.5 的帧 ≤ 554（交付版 528 × 1.05）；4 动力学违规帧 ≤ 2408（2189 × 1.1）；5 标了接触而手离物体 > 3 cm 的帧占比 ≤ 交付版 + 0.2 个百分点；6 agent 看贴图渲染（审计改动最大的帧、ep21、ep12/14），明显变差或判不了就不交付。世界系整体变了，交付版 → 新版的改动审计只用来挑看图的帧，不作条件。
**10-17 13:1x 状态与接手**：整链到第 7 步（地面门槛 25/30，失败 ep3/6/7/20/25 与交付版逐条相同，重定向 0 失败），我们的支撑面复检在跑；之后 `gb_selfcheck.sh` 自动开跑。用户要的报告：按上面六条逐条对照交付版，写 `agent-doc/selfcheck-tier3-gb_best_dr2s_dyn7-2026-10-17.md`，交付报告草稿用 `t3_delivery_report.py` 写到 `$T/dev/audit/`（不进版本目录、不交付），事实过 jev。看图注意：`t3_pose_overlay.py` 对所有版本只用一个选择表的相似变换与内参，f830 与 GB 两个世界不能放进同一次调用；两版各用自己的选择表（`tier3_cari4d_f830_best.selection.json` / `tier3_cari4d_gb_best.selection.json`）、同一组 `frames=` 分别渲染再并排。
**自检结果（10-17 13:48 跑完）**：六条中前五条过，第 6 条看图未过（ep16 第 130 帧明显变差，dyn7 在 GB 世界把第一段静置锁定延到第 128 帧，交付版到第 105 帧）；未交付，交付版仍是 `best_dr2s_dyn7`。报告 [selfcheck-tier3-gb_best_dr2s_dyn7-2026-10-17.md](selfcheck-tier3-gb_best_dr2s_dyn7-2026-10-17.md)，交付报告草稿 `$T/dev/audit/DELIVERY_draft_gbdyn7.md`。

## 初值试点的位置问题：后处理与「旋转取新、中心取旧」都修不了（10-19，用户要求先验再做方案 (1)）

用户 10-19 选方案 (1)（FoundationPose 每帧存全部候选 + 全时间线选择），先验证试点里的位置偏差能否靠后处理或拼接修掉。判据跑之前登记在
`$T/dev/init_pilot/mix/PLAN.md`。三个版本只换物体，四集 ep04/03/13/28，走 **gb4 链**（focal `intrinsics_gb3.json` 带人体重拟合，world
`floor_fit_gb4` + `camera_register_gb4`，支撑面 `runs/support/tier3_cari4d_gb4_best`，dr2s `--move-human=3d`，dyn7）：ctrl = convert_fp 原样，
init = work_init 的 `refined.pth`，mix = init 的旋转 + ctrl 的网格包围盒中心（`mix_object.py`，断言旋转逐位等于 init、中心逐位等于 ctrl）。
阶段 A（组装后）与 Y（dr2s + dyn7 后）；「变化帧」= init 相对 ctrl 转角 > 24°；轮廓 IoU 每 2 帧一次（`mix_iou.py`，在 v2d_cari4d 容器里跑，
宿主 venv 缺 h5py/torch）。对照：ctrl 的物体列与 gb4_best/_dr2s/_dr2s_dyn7 逐列一致；人体列有差（姿态 ≤ 0.03 rad、平移 ≤ 4 mm，ep28 最大），
focal 步人体重拟合不逐位复现（推断），不影响物体轮廓的比较。结果 `$T/dev/init_pilot/mix/report/summary.txt`。

**位置偏差的形状**（init − ctrl 的物体中心，CARI4D 相机系，变化帧 p50/p90）：ep04 沿视线 3.4/11.1 cm、横向 3.2/7.1 cm（8/20 px）；ep03 0.6/1.5、
0.5/0.7 cm（1.4/2.0 px，变化帧只有 12）；ep13 1.4/5.3、2.4/6.6 cm（6/16 px）；ep28 14/42、14/29 cm（40/86 px，ep28 重建本身失败）。横向分量与沿视线
同量级，dr2s 只沿视线改，碰不到横向那一半。

**IoU（iou_vis，变化帧合并四集；差 = 版本 − 同阶段 ctrl，好/坏 = 差 > +0.05 / < −0.05）**：

| 版本 | n | 中位差 | 好 / 坏 | 登记的判据 |
|---|---|---|---|---|
| A_init | 139 | −0.012 | 28 / 53 | 不过 |
| Y_init | 141 | +0.000 | 37 / 43 | 不过（Q1：后处理修好 init？否） |
| A_mix | 140 | −0.004 | 32 / 47 | 不过 |
| Y_mix | 140 | −0.000 | 39 / 39 | 过；但 Q2 要求 A、Y 都过，记「否」 |

逐集：ep04 是损失的主体，A_init −0.013（8/21）、Y_init −0.001（9/21），**mix 反而更差**（A −0.031，4/19）；ep13 init 本来就更好（A +0.023，10/4）；
ep28 A_init 10/28，到 Y 打平（18/17）；ep03 变化帧可用的 iou_vis 只有 2 帧，说不了什么。整集中位 iou_vis 三版相差 ≤ 0.008（ep04 0.804/0.809/0.807）。

**结论**：(a) dr2s + dyn7 把合并后的中位差从 −0.012 拉到 0，坏帧从 53 降到 43，但仍多于好帧，ep04 基本没变；(b) 沿用旧中心修不了，ep04 上更差——
旧中心是为错误朝向摆的位置，不是独立于朝向的「对的位置」（推断）；(c) 损失只在变化帧上，整集 IoU 不受影响。方案 (1) 不另加位置补丁：判版本看 Y 阶段，
朝向仍以用户看贴图为准。盲区同 10-16：球棒头尾翻转的轮廓相近，IoU 主要量位置；ep03 手持帧掩码几乎全在人体内。
脚本（未入库，同试点其他脚本）：`$T/dev/init_pilot/mix/{PLAN.md,mix_object.py,mix_review.sh,iou_tail.sh,mix_iou.py,mix_summary.py}`。

## 方案 (1)：全时间线选择 FoundationPose 候选（10-19 开工，用户定；闸门判据在看结果前登记于此）

**为什么**：10-16 初值试点证明 CoCoNet 跟着初值走（ep04 第 313/509/669、ep03 第 451 帧换初值后朝向对了），但它的插值依据 `fp_reliable` 只表示
「与上一确认姿态连续」不表示「对」，两端都可能在错分支上，长段跳过，自信地错的帧碰不到。方案 (1) 不预设哪帧可信：每帧在自己的候选里选，
与相邻帧联合求最优（Viterbi），选出的序列作 CoCoNet 初值，后面照原链走。

**05 步 dump**（`a9b5854`）：`third_party/patches/cari4d-fp-candidate-dump.patch` 在已部署的补丁文件上再加一层，每次配准调用把完整排序候选池
（约 200 个位姿、FP 分数、短名单的全图掩码指标）写进 pkl 旁的 `<seq>.candidates.npz`，选择与 pkl 不变。A/B（ep03 第 440–460 帧）：原版两次逐位相同，
dump 版 pkl 与原版逐位相同；17 帧输出位姿在本帧候选里原样找到，另 4 帧是窗口切入造成的 FIRST_CONFIRMED_BACKFILL。`t3_fp_dump.sh` 只重跑 05、
对照 work_fp 逐位核对，输出 `runs/work_dump/<ep>/`；10-19 11:37 起两路（A：ep03/02/09/25/16/19，B：ep04/13/28/11/01/27/15/17），日志 `logs/fp_dump_{A,B}.log`。
让卡：集与集之间查 rxzhou 的链（10-10 约定）、`runs/work_dump/GPU_HOLD`、空闲显存；`touch runs/work_dump/STOP` 停在集间。

**选择器** `t3_fp_select.py`（参数 10-19 在任何试点结果前定死，不在对照帧上调）：状态 = 本帧各次调用的短名单候选（无短名单时每次调用取 FP 分数前 8，
IoU 项中性）；单帧代价 −(调用内 log-softmax 分数 + 5·IoU)；相邻代价 转角/(10°·间隔) + 平移/(5 cm·间隔)，转角按 `gate/t3_symmetry.py` 的对称组取最小
（与 `nearest_equivalent` 对拍最大差 2e-11°）。无调用的帧沿用上一选中位姿。在 A/B 的 21 帧上干跑：21 帧都相对原选择转约 176°（含原本上下颠倒的第 451 帧），
帧间跳变前后都是 0。

**试点与闸门**（`t3_sel_pilot.sh ep04 ep03` → `t3_sel_gate.py`，用户 10-19 同意判据）：work_fp 复制到 `runs/work_sel/`，写入选择，CARI4D 只重跑 06–08；
gb4 物体链（同上节位置验证）出 ctrl / sel 两版，每 2 帧 iou_vis。
- G1 朝向（答案取 `checked_frames.json`，只作评估）：sel 与 init 试点相差 < 30°：ep04 第 313/509/669、ep03 第 451 帧；与 ctrl 相差 < 30°：ep03 第 117/131/345 帧。
- G2 跳变：CoCoNet 输出里帧间转角 > 24° 的帧数，两集都是 sel < ctrl。
- G3 位置：Y 阶段，sel 相对 ctrl 转角 > 24° 的帧合并，iou_vis 中位差 ≥ −0.01。
全过则剩余 12 集自动走同一流程到自检，停在交付前（交付等用户看贴图）；不过就停，dump 保留。结果 `$T/dev/sel_pilot/gate.json`，日志 `logs/sel_pilot.log`
末行 SEL_GATE_PASS / SEL_GATE_FAIL / SEL_PILOT_FAILED。

### 无人值守运行状态（10-19 12:55 CST 写，用户下线；分支 `track2/tier3-recon`，部署 `d5ce9bc`）

用户 10-19 定：版本名 **gb5**；世界系**沿用 gb4**（`floor_fit_gb5.json` / `camera_register_gb5.json` 是 gb4 的逐字节副本，已 cmp）；ep19（pivot）不进本轮。
L40S 上在跑（都是 setsid 脱钩的确定性脚本，没有 agent）：

| 脚本 | 日志（`$T/logs/`） | 末行 |
|---|---|---|
| `t3_fp_dump.sh A`（ep03/02/09/25/16/19）、`B`（ep04/13/28/11/01/27/15/17） | `fp_dump_A.log`、`fp_dump_B.log`，每集 `fp_dump_<ep>.log` | `FP_DUMP_STREAM_DONE` / `FP_DUMP_FAILED` |
| `t3_sel_pilot.sh ep04 ep03` | `sel_pilot.log`，闸门 `$T/dev/sel_pilot/{gate.log,gate.json}` | `SEL_GATE_PASS` / `SEL_GATE_FAIL` / `SEL_PILOT_FAILED` |
| `t3_sel_full.sh gb5 <13 集 fp>` | `sel_full.log`，每集转换 `sel_convert_<ep>.log`，链 `gb_chain_gb5.log`，自检 `$G/dyn/gb5_selfcheck.log` | `SEL_FULL_DONE` / `SEL_FULL_SKIPPED`（闸门没过） / `SEL_FULL_FAILED` |
| `dev/fpdump/convert_test.sh`（转换步试跑，ep04 的 work_init，等 B 路 ep04 dump 完成后跑） | `$T/dev/sel_test/convert_test.log` | `CONVERT_TEST_DONE` |

已验证的衔接：A/B（见上）；试点第 4–5 步与闸门在 `work_init` 上从头跑通（`SEL_WORK=work_init SEL_FROM_STEP=4`，`logs/sel_test.log` 末行 SEL_GATE_PASS——
只证衔接，sel 即 init，G1 必为 0）；13 集与选择表一致、30 集的 gb4 转换目录都在。**没验证的**：全量的转换步（试跑在等卡）、`t3_gb_chain.sh gb5` 与自检
（与 gb4 同一份代码，只换名字；自检脚本由 gb4 的 sed 生成，替换结果人工核过）。
预计（两路并行实测只快 1.4 倍）：闸门 15:00–15:30，dump 全部 23:00–24:00，链 + 自检明早 5–6 点。**停在交付之前**：交付等用户看贴图后再定。

接手怎么查：`tail -n 3 $T/logs/{sel_pilot,sel_full,fp_dump_A,fp_dump_B}.log`；`ls -a $T/runs/work_dump`（`GPU_HOLD` 存在 = 有人在用整卡，
dump 停在集间等）。让卡：rxzhou 的链回来时所有 GPU 步在集与集之间停下等（10-10 约定）。停 dump：`touch $T/runs/work_dump/STOP`。
失败后恢复：dump 每集独立（`check.json` identical 即算完成，重跑会跳过）；`t3_sel_full.sh` 已选/已 refine 的集重启后跳过，转换会重做；
它要求 `runs/tier3_cari4d_gb5_best*` 不存在，链失败后重跑前要先挪走这些目录。
未办：交付前给 rxzhou 说明 gb5（白名单加 `tier3_cari4d_gb5_best_dr2s_dyn7` 与 `_suspect`，`gb5_best`/`gb5_best_dr2s` 是中间产物别用）；
gb4 交付报告里 `rest_drift` / `rot_drift` 比 gb3 涨了的原因未查。

**14:05 更新（部署 `623a398`）**：13:15/13:20 两路各跑完第一集后都报「stage-05 output differs」退出，试点随之失败、全量 SKIPPED。原因是 dump 脚本的核对
heredoc 进 docker 没加 `-i`，容器里的 python 读到空脚本、exit 0，`check.json` 为空（`14212ba` 修，并把「核对无结果」单列为失败）。手动重核：
ep03（781 帧、854 次调用、215208 个候选）、ep04（803 帧、1199 次调用、302148 个候选）与 work_fp **逐位相同**。选择器读 npz 时每次索引都整数组解压，
ep04 跑 11 分钟没完（`623a398` 改为一次读入，整集 13 s）。已重启四个脚本；转换步试跑 13:21–13:31 全部通过（`$T/dev/sel_test/convert_test.log`）。
试点选择结果：ep04 163 帧转 > 24°，FoundationPose 层帧间跳变 38 → 16；ep03 374 帧转 > 24°，跳变 3 → 7（闸门看 CoCoNet 输出，不在这一层判）。
**现在卡在 rxzhou**：他 13:23 起在 ml40 跑 t2xp（Tier 2 ep14 正式训练 13:43 开始，显存约 40 GB），按 10-10 约定我们所有 GPU 步在集间等他的链结束，
时长未知；dump、试点 06–08、全量都会顺延。

**10-19 23:50 闸门 FAIL**（`$T/dev/sel_pilot/gate.json`）：ep04 G1 过（4–11°），Y 好 34 / 坏 5；ep03 G1 不过（第 451 帧对 init 84°，第 117/131 帧对 ctrl 110°/80°），
Y 好 2 / 坏 46；G3 合并中位 −0.079。全量按设计 SEL_FULL_SKIPPED；dump 两路照跑（用户 10-19 定）。

**ep03 失败机制（10-20 00:20，只读诊断 `$T/dev/sel_diag/{sel_diag.py,ep03.json}`，未入库）**：重放 Viterbi 与 work_sel 逐位相同。
- 对的候选一直在：每帧都有离 ctrl < 30° 的状态；第 117/131/345 帧离答案 < 30° 的状态 2–4 个，第 451 帧 5 个。
- 单帧代价分不开：第 117、131 帧选中的是单帧代价第 0 名（离答案 68°、84°），对的是第 1 名，差 0.02、0.22；第 451 帧对的排第 79 名
  （IoU 0.81 对 0.90）。全集只有 44.6% 的帧单帧最优离 ctrl < 30°。
- 不是平滑项拖过去的：限制在 ctrl 附近的最优路径，单帧、转角、平移三项都比自由路径大（572/456/350 对 487/393/334）。对这两条路径，
  三项任何非负加权都选自由路径，所以调 W_IOU / ROT_DEG / TRANS_M 修不了。变化帧上自由路径赢的部分，分数项与 IoU 项各占一半（−43.7、−41.3）。
- 推断（未验证）：杯把小，手持时多被手挡，FP 分数和全图掩码 IoU 都对绕杯身轴的转动不敏感；ep04 球棒细长，错分支的轮廓差得多。

**杯把推断核对（10-20，`$T/dev/sel_diag/{sel_handle.py,handle/ep03_handle.{png,json}}`，未入库）**：在 05 步的输入上（导出目录的图像、掩码、
`output_aligned.glb`、`wild_export.json` 的 K）叠选中候选与最好的「对」候选；杯把按网格形状标（窄轴给杯身半径，杯把向宽轴一侧伸出）。
杯子整体只有约 1700 px。
- 第 117 帧**支持推断**：两个轮廓 1694 / 1695 px，IoU 0.84 / 0.83；XOR 321 px，其中 193 px 在杯把上、132 px 落在人体掩码里。
  选中候选的杯把 112 px 中 83 px 在人体掩码内（被手挡），对的候选杯把在左（与核对记录「handle on the left」一致）。
- 第 451 帧**是另一种机制**：对的候选（离 init 23°，单帧第 79 名）整体就配不准，轮廓 1507 px 对掩码 1667 px，IoU 0.80 对 0.89；
  XOR 466 px 只有 132 px 在杯把上。候选池里没有配得好的对朝向候选，不是杯把看不见的问题。

**答案帧修订（10-20，用户定）**：ep03 第 451 帧 init 朝向错、sel 对（`checked_frames.json` 的 `ep03_f451` 与 `sixth_pass_sel_pilot`；
对照图 `$T/dev/sel_diag/handle/ep03_f451_compare.png`）。这个杯子两端都有银色，不能凭银色认杯盖。最终输出对掩码（`sel_final_iou.py`）：
第 451 帧 sel IoU 0.854、质心偏 3.4 px，init 0.636 / 7.2 px，同链 ctrl 0.52；第 117 帧 sel 0.782（轮廓 1546 px 小于掩码 1731，杯把没画出），
ctrl 0.61。
- `t3_sel_gate.py` 的 `CHECKS` 仍把第 451 帧对 init 比，这一项已失效；闸门判据是看结果前登记的，没改。按新答案 ep03 的 G1 仍不过
  （第 117 帧 110°、第 131 帧 80°），结论 FAIL 不变。
- 未核：hm/dyn7 在第 451 帧记的「upside down」是以 init 为参照判的，可能也要重看；G3 判 sel 变差，与这两帧 sel 位置更准方向相反，原因没查。

**G3 归因（10-20，只读，脚本在 `$T/dev/sel_diag/sel_g3_stages.py`，`_all` 版把 `vis` 换成 `all`）**：
- ep03 报告 391 行里 284 行 `iou_vis` 为空（从第 92 帧起；空值条件是去掉人体后渲染或掩码 < `MIN_VISIBLE_PX`=400），G3 的 48 帧
  几乎全在第 0–90 帧（另 3 帧在 536–546）。手握段（含 424–470、第 451 帧）没进统计。
- sel 转动 > 24° 的帧按段看全轮廓 IoU（sel−ctrl，Y 阶段）：第 0–134 帧 −0.158（A 阶段 −0.052），其余段大多为正
  （424–470 +0.075、608–628 +0.057、268–282 +0.07）。全部 173 个转动帧的 Y 中位数 −0.005，A +0.006。
- 结论：G3 与 G1 的失败是同一段——开头第 0–134 帧 sel 朝向错（第 117/131 帧杯把被转到右侧或看不到，用户判过 ctrl 对）；
  这一段在 Y 阶段被放大（−0.05 → −0.16，Y_sel 在前几帧近乎常数，推断是 dyn7 的静止段沿用了这个错位姿，未核）。
  全轮廓口径的 −0.005 是看结果后的口径，不据此改判。
- 第 131 帧对照图 `$T/dev/sel_diag/handle/ep03_f131_compare.png`（`sel_compare_n.py`）：sel 两层都把杯把放在右侧，ctrl 在左；
  对掩码 IoU ctrl 0.845、sel 0.832，轮廓分不出朝向。

**以 ctrl 为锚的离线试验（10-20 用户定，看结果前登记）**：答案帧现为 ep03 117/131/345 ctrl 对、451 sel 对（`61abbd0`），ep04 313/509/669
init 对。思路：默认保留 FoundationPose 自己的选择，只有整段时间线明显偏好别的朝向才改。
- 规则：一元项减 `BETA`×[该状态与本帧 ctrl 位姿夹角 < 24°]，其余与 `t3_fp_select.py` 相同；`BETA=0` 即 10-19 选择器（断言复现 sel 试点）。
- 网格 `BETA` ∈ {0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5}；在 FP 层（第 05 阶段位姿）判答案帧，与参照夹角 < 30° 算对。
- 取值：7 帧全对的 `BETA` 若成连续区间，取区间两端的几何中点；没有全对的就判此规则不成立，不再加参数救。
- 局限：G1 判的是 CoCoNet 之后的朝向，FP 层对不等于 06 之后对，过了还要在 GPU 上重跑 06–08。阈值在这 7 帧上选出，
  留出验证用 ep13/ep02（dump 完成后按选定 `BETA` 跑，与 ctrl 不同的段渲染给用户判）。
- 脚本 `$T/dev/sel_diag/sel_margin.py`，CPU，只读。
- **结果（10-20 ~02:30，`$T/dev/sel_diag/margin/`）**：`BETA=0` 逐位复现 sel 试点（两集最大差 0）。答案帧全对的区间：ep03 为 0.2–1.5
  （0.1 及以下 117/131 错；2 及以上 451 被拉回 ctrl），ep04 为 0–0.5（0.75 起 313 被拉回 ctrl，103°）。交集 0.2–0.5，按登记取
  `BETA=0.316`：ep03 4/4（117 14.0°、131 14.7°、345 12.5°、451 0.0°，与 ctrl 差 > 24° 的帧 97，sel 试点 374）；ep04 3/3（2.6°、19.5°、
  24.1°，146 帧，sel 试点 163）。区间只差 2.5 倍，阈值余量小；509/669 在 FP 层离 30° 不远（sel 试点在 06 之后是 11.1°/4.0°）。
  FP 层跳变 ep03 为 7（ctrl 3），G2 判的是 06 之后，不可直接比。
- **ep13 留出（10-20 ~03:00，用户判，FP 层）**：`BETA=0.316` 在 ep13 与 ctrl 不同的帧 383（`BETA=0` 为 390），两段在开头 0–232、结尾
  774–921。8 帧里锚定版对、ctrl 错 5 帧（40/120/800/860/915，静止段）；两者都错 2 帧（196/766，遮挡严重）；ctrl 较近 1 帧（226，位姿稍偏）。
  记入 `checked_frames.json`（`ep13_f*`，版本名 `ctrl`/`anchor`）。锚定在 ep13 上几乎不拦截时间线选择的改动，ctrl 在这集的静止段本身是错的。

**锚定版 GPU 重跑（10-20 用户定：闸门选 b，ep13 一起跑，插队）**：
- `t3_fp_select.py` 默认 `BETA=0.316`、`ANCHOR_DEG=24`（锚是被改写前 pkl 里 FoundationPose 自己的位姿）；在 ep03/ep13 的副本上与离线
  `sel_margin.py` 逐位一致（最大差 0.0）。
- `t3_sel_pilot.sh` 的工作目录随 `SEL_WORK` 走（之前第 1–3 步写死 `work_sel`），CARI4D 日志 `logs/cari4d_<ep>_anchor.log`。
- `t3_sel_gate.py`：G1 按 10-20 答案（ep03 451 对 `pilot`=runs/work_sel，ep13 40/120/800/860/915 对本次运行的第 05 阶段位姿、226 对 ctrl）；
  G3 判定不变，另报全轮廓 IoU（`G3_all_info`，不入判定）。在旧 sel 试点上复跑复现原数（G3 −0.0786、117 109.7°、131 79.8°），
  全轮廓参考 +0.0075（n=230）。第 05 阶段与 CoCoNet 输出同一坐标系：ep03 夹角中位数约 10°（p90 25.6°），ep13 1.7°。
- 运行：`SEL_WORK=work_anchor SEL_REVIEW=$T/dev/anchor_pilot t3_sel_pilot.sh ep03_contigo_coffee_mug ep04_baseball_bat ep13_snack_box`，
  日志 `$T/logs/anchor_pilot.log`。插队靠 `GPU_HOLD`：两路 dump 做完手上这一集就停，06–08 跑完释放，不杀正在跑的集；仍等 rxzhou 的链空闲。
- **停掉（10-20 02:55，用户定）**：`BETA=0.316` 的上下界由用户核对过的答案帧定出（下界 ep03 117/131，上界 ep04 313），等于用测试视频上的
  人工判断调参，违反 10-15「修复只能来自自动方法」与 `checked_frames.json` 的 evaluation only。锚定版重跑在 06–08 之前终止（进程组 kill，
  `GPU_HOLD` 已删，B 路 02:56 接着跑 ep11）；`runs/work_anchor` 只有第 05 步改写，不作任何依据。`t3_fp_select.py` 里的 0.316 待换成
  不依赖答案帧的取值（方案 a：由候选池的打分噪声定，规则先登记再算），答案帧只做评估。

**`BETA` 的新取法（10-20 用户同意，登记于计算之前；不读答案帧）**：
- 量：打分噪声。同一帧内两个状态的二元代价 `angle/ROT_DEG + |dt|/TRANS_M`（角度按对称取最小，与选择器相同）< 0.1（约 1° / 0.5 cm），
  视为同一假设；收集所有这种状态对的一元项差 `|Δu|`（一元项即 `states_of` 给的、不含锚定项）。
- 统计量：全部状态对合并后的中位数，即 `BETA`。理由：锚定奖励每帧都加、在一段里累积，对应典型噪声而不是尾部。
- 集：登记时已 dump 完的 5 集 ep02、ep03、ep04、ep13、ep28；之后 dump 的集不加入。
- 用法：算出多少用多少。答案帧只做评估：离线在 FP 层报 ep03/ep04 的 7 帧与 ep13 的 8 帧，之后上 GPU 跑闸门；落在 0.2–0.5 外、闸门不过就照实
  记失败，不改规则。已知局限：规则是在知道 0.2–0.5 这个区间之后提出的。
- **按登记规则的结果（10-20 03:2x，`$T/dev/sel_diag/{beta_noise.py,beta/beta_noise.json}`）**：近邻状态对 99061 个，`|Δu|` 中位 **0.0024**
  （p75 0.065、p90 0.133）；逐集中位 ep02/03/13/28 为 0.0，ep04 0.0417。诊断（`beta_dup.py`）：ep02/03/13/28 的近邻对几乎全是逐位相同的位姿
  （9163/4544/15257/4187 对），来自同一帧的不同调用、不同 source id，一元项也相同；ep04 65889 对里 15242 对逐位相同。即这条规则量到的主要是
  同一候选在不同调用里重复出现，不是两个独立估计的打分差。按登记，`BETA=0.0024`；离线网格上 0.05 时 ep03 117/131 已错，推断 0.0024 同样错（未跑）。
  是否把「逐位相同的状态对」排除后重算属于看到结果后的改动，待用户定；排除后的值没有算。
- **修正（10-20，用户定，登记于重算之前；看过 0.0024 之后的事后修正）**：同一规则，只把 4×4 位姿逐元素差 < 1e-9 的状态对排除（同一候选的重复，
  不是两个估计）。其余（NEAR 0.1、中位数、5 集、算出多少用多少、答案帧只评估）不变。
- **修正后的结果（`beta/beta_noise_dedup.json`）**：非重复近邻对 50668 个，**`BETA=0.0633`**（p25 0.029、p75 0.116）；几乎全部来自 ep04（50647 对，
  球棒有 24 个对称旋转）；ep02/03 各 1 对、ep13 19 对、ep28 0 对，其余集的候选之间没有 1°/0.5 cm 以内的不同候选。离线 FP 层
  （`beta/ep0{3,4}_*_b0633.json`）：ep04 3/3（2.6°/19.5°/24.1°），ep03 2/4（117 68.3°、131 84.1° 错；345 12.5°、451 0.0° 对）。
  **按登记记为失败**：不依赖答案帧的锚定取值救不了 ep03 开头静止段，不再改规则。`t3_fp_select.py` 现在的默认值仍是 0.316（来自答案帧），待用户定怎么处理。

**`BETA` 的 A/B（10-20 用户定，登记于运行之前）**：比较取值本身没问题，问题只在裁判；裁判用自动指标（同 10-13 按跟丢比例逐集选版本），
答案帧只在最后验收。
- 取值 {0, 0.1, 0.2, 0.3, 0.5}；集 ep03、ep04、ep13。每个取值走完整条链：选择 → 06–08 → 转换 → dr2s → dyn7 → `t3_sel_iou.py`（每 2 帧）。
  `BETA=0` 的 ep03/ep04 复用 `runs/work_sel`（10-19 试点，离线已证逐位相同），ep13 新跑。
- 裁判：每集 Y 阶段 sel 的全轮廓 IoU（`Y_sel.all`）在全部抽样帧上的均值，三集等权平均，最大者胜；与最大者差 < 0.005 的取值里取
  三集 sel 跳变帧（闸门 `jumps_ctrl_sel`）合计最少者，再平局取较小 `BETA`。用均值不用中位数：未改动帧的差接近 0，中位数分不出取值。
- 用户说先看趋势；胜出值定下后再看 7 个答案帧与 ep13 的 8 帧（只评估，不回头改值）。自动裁判不一定选中 0.3，选哪个报哪个。
- 运行：`t3_beta_ab.sh`，`runs/work_b{000,010,020,030,050}`，评审目录 `$T/dev/beta_ab/<tag>`，日志 `$T/logs/beta_ab.log`。
  GPU 约 13 次 06–08（每次约 22 分钟），一次性 `GPU_HOLD`，dump 跑完手上这一集后让路。
- **省时（10-20 03:24 重启，用户同意，`e3fdeae`）**：08 只渲染核对视频、下游不读，A/B 里跳过（`T3_SKIP_RENDER=1`，补丁
  `third_party/patches/cari4d-skip-render.patch` 叠在每帧配准补丁之上，md5 钉住，`pipeline_report.json` 记 `render: skipped`）；第 05 步位姿与较小
  `BETA` 逐位相同时复用其 06–07（`REUSED_FROM`；假设同输入同输出，未核）。去重后：ep04 0.3 = 0.2，ep13 0.1 = 0.2 = 0.3，ep03 五个取值互不相同；
  GPU 实跑 10 次（ep03 4、ep04 3、ep13 3），每次约 11 分钟（ep04 的 06+07）。仍等两路 dump 做完当前集（B 路 ep11 约 04:40）。
- **运行状态（10-20 08:45 CST）**：GPU 10 次于 06:16 跑完、`GPU_HOLD` 已释放；CPU 链每个取值约 53 分钟，b000 07:09、b010 08:02 已出
  （闸门均 FAIL：ep03 G1、ep13 G1/G2、G3；闸门只评估，不是裁判），预计约 10:40 全部完成。结果看 `$T/logs/beta_ab.log` 末行
  （`BETA_AB_DONE` / `BETA_AB_FAILED`）与 `$T/dev/beta_ab/summary.txt`（`WINNER` 行）。两路 dump 已续跑：A 在 ep16（剩 ep19），B 在 ep27（剩 ep15）。
- **`ANCHOR_DEG = 24°` 的来历**：沿用 `gate/t3_dynamics_check.py` 的 `OMEGA_MAX = 4π rad/s` ÷ 30 fps（闸门 G2/G3 同一门槛），没有单独检验它作为
  「同一朝向分支」半径是否合适（候选与原选夹角分布未统计）。用户 10-20 判断不是关键、暂不查；结果对它敏感时再回来。

## 外观指标探针（10-20，用户定；判据登记于运行之前）

起因：yudong 提出光看 IoU 可能不合适。已核（`$T/dev/sel_diag/iou_discrim.py`，b000/b010/b020）：答案帧上 ctrl、sel 恰一个对时，Y 阶段
全轮廓 IoU 偏向对的一方 8/19（b000），与乱猜分不开；ep13 盒子 6 帧错 4 帧，ep04 相邻两帧符号相反。A/B 的登记裁判因此主要量位置，量不了朝向。

探针 `$T/dev/sel_diag/appearance_probe.py`（CPU，`--cpus 2`、`nice 19`，不挤 A/B 链）：网格贴图按面着色（同 `t3_pose_overlay.py tex=1`），
不透明渲染进视频帧，在「渲染轮廓内、人体掩码外」的像素上算三种外观分，外加 IoU 作对照：
- `ssim`：灰度 SSIM（高斯窗 σ=1.5，7×7），取上述像素的均值，越高越好；
- `edge`：渲染内部边缘（轮廓内腐蚀 3 px 后的 Canny 50/150）到视频 Canny 边缘的平均距离（截断 20 px），越低越好；
- `color`：渲染色与视频色逐通道标准化后的相关系数均值，越高越好；
- 可比像素 < 400 记为判不了（算作判错）。参数固定为以上值，不按结果调。

两项测试，帧为答案帧中有已知正确版本的 13 帧（ep03 117/131/345/451，ep04 313/509/669，ep13 40/120/226/800/860/915；196/766 两版都错，除外）：
- A（成对）：各 `BETA` 的 Y_ctrl 与 Y_sel 恰一个对的帧，sel 位姿相同（< 1°）的去重；指标偏向对的一方记判对。
- B（排序）：每帧以正确版本的 Y 位姿为准，绕质心沿网格三根主轴各转 90°/180°/270° 得 9 个错误候选（与正确位姿在对称意义下 < 30° 的剔除）；
  正确位姿严格得分最优记判对。
- **判据**：A 判对率 ≥ 80% 且 B 判对率 ≥ 80% 的指标记「可用」。过线的全部报给用户，不自动挑最好的；都不过线就记失败，不再加变体。
  可用只表示可以拿去登记为新裁判，换不换裁判由用户定。IoU 同场计算，预期在 A 上接近 50%（若也 ≥ 80%，说明测试本身有问题）。

**结果（10-20 09:45，b000/b010/b020；记为失败）**：三种外观分都不过线，IoU 对照也不过（A 8/18，B 6/13，符合预期）。

| 指标 | A（18 对） | B（13 帧） |
|---|---|---|
| iou_all / iou_vis | 8 / 8 | 6 / 5 |
| ssim | 10 | 1 |
| edge | 7 | 1 |
| color | 9 | 4 |

- ep03 杯子判不了：手持帧人体掩码外的可比像素只有 24–172（门槛 400），A 3 对、B 4 帧全部记错，任何基于画面的指标在这集都拿不到信号。
- ep04 球棒有信号：`color` 在 A 上 7/7（正确版本相关 0.48–0.70，错误版本 −0.39 到 −0.56），B 2/3；`ssim` A 7/7、B 0/3。球棒两头颜色差别大。
- ep13 盒子没有信号：正确位姿的 `color` 也在 −0.09 到 0.31 之间，A 2/6、B 2/6（贴图与视频颜色对不上或渲染对位差，未查）。
- b030/b050 出来后 A 会多几对，但 B 只依赖正确版本，与取值无关，最高 4/13，结论不变。
- 探针 IoU 与链上报告同向、数值差 < 0.015（ep13 第 40 帧 0.937/0.905 对 0.944/0.916），渲染与相机链路一致。
- 按登记不再加变体。输出 `$T/dev/sel_diag/appearance_probe_b000-b020.json`。

## 跨帧约束探针（10-20，用户定；判据登记于运行之前）

外观指标失败后改试跨帧的物理约束（`$T/dev/sel_diag/crossframe_probe.py`，CPU，`--cpus 2`、`nice 19`）。分段取自各版本 D 阶段的
dr2s `anchors`（物体落在支撑面/地面上的段，下称「放着」），其余为「搬运段」。两条约束：
- **C1 放着要放得稳**：放着的帧上，重力方向（`t3_inputs.ground_plane` 的法向）在物体体坐标里的方向，与网格凸包的稳定姿态
  （`trimesh.poses.compute_stable_poses`，质心同闸门，概率 ≥ 0.01）的朝下方向的最小夹角（`tilt`），越小越好。
  只能排除「放不稳」的朝向：杯子倒扣、盒子换一面朝下这类本身也稳的错，C1 按设计分不出。
- **C2 搬运时随手转**：搬运段内物体相对持物手刚性。手的转动 = 掌心顶点（SOMA 蒙皮权重在 `<side>Hand` 上 ≥ 0.8，人体取各版本 D 阶段
  的 npz）相对段端点帧的 Kabsch 旋转；持物手取段内掌心离物体中心平均更近的一侧。预测朝向 = 手的转动 × 该版本在离此帧更近的一端
  （搬起前或放下后）放着时的朝向（端点外 5 帧的弦均值）；偏差 = 实际与预测的对称意义夹角，越小越好。段两端都没有放着的帧则判不了。
- 帧：答案帧中有已知正确版本的 13 帧，放着的归 C1（ep03 117/131/345，ep13 40/120/860/915），搬运的归 C2（ep03 451，ep04 313/509/669，
  ep13 226/800）。成对测试同外观探针的 A（各 `BETA` 的 Y_ctrl 与 Y_sel 恰一个对，sel 位姿 < 1° 去重；判不了记错）。
  C1 另报旋转候选排序（同外观探针 B），按设计会在稳定的错误朝向上打平，只作参考、不作判据。
- **判据**：C1、C2 各自在自己的成对样本上判对率 ≥ 80% 且样本 ≥ 5 对，记「可用」；否则记失败。参数（概率阈值 0.01、端点 5 帧、
  掌心权重 0.8）固定，不按结果调。可用只表示可以登记为裁判的组成部分，换不换由用户定。

**结果（10-20 10:05，b000–b030；两条都记为失败）**：C1 5/7、C2 8/11，都低于 80%。输出 `$T/dev/sel_diag/crossframe_probe.json`。
- C1 没有分辨力：杯子凸包有 5 个稳定朝下方向，sel 在第 117/131 帧的错误朝向（相对 ctrl 110°/80°）倾角 5.4°/2.8°，与正确的 4.4°/4.1°
  同为「放得稳」；盒子 6 面都稳，各版本倾角都在 1.6–5.8°。判对的 5 对是 0.2–2° 的噪声差。旋转候选排序 1/7：错误候选大多同样稳。
- C2 在「放着时朝向对、搬运中翻错」的情况上分得很开：ep04 7/7（对的版本偏差 12–60°，错的 100–168°），ep03 451 对（44° 对 160°）。
  错的 3 对都在 ep13：ctrl 在搬起前的放着段本身就错（答案帧 40/120 判 ctrl 错），C2 以版本自己放着时的朝向为起点，只能查出搬运段与
  放着段不一致，查不出两段一起错；第 800 帧两版各与自己（都可能错）的放下段一致（10.1° 对 11.0°）。
- 合起来：跨帧约束能判「一致性」，判不了「放着时是哪一面朝下」。缺的是每个放着段的绝对朝向，C1（重力稳定）对杯子倒扣/侧放、盒子换面
  这类本身也稳的错误无效，与 10-17 静置段投票失败的原因相同。按登记不调参数、不加变体。

## 做法 1（C2 进选择器的相邻帧代价）：手位姿来源（10-20 查，`$T/dev/sel_diag/kp6.py`）

- 来源：CARI4D 第 03 步 `mhr_init/<seq>.pkl` 的 `mhr_keypoints`（803×70×3，SAM-3D-Body 的 MHR70 关键点，名表
  `/workspace/v2d_sam3d_body/lib/sam_3d_body/metadata/mhr70.py`）。与第 05 步 `fp_poses_cam` 同一相机系（`camera_id` 0）、米制
  （`depth_source` metric_depth，`mean_depth_align_scale` 1.0），在选择之前就有，不依赖物体链。
- 掌心刚体点：手腕 + 食/中/无名/小指 third-joint（掌指关节）；右手 41/28/32/36/40，左手 62/49/53/57/61（腕索引与 CARI4D
  `lib_mhr/contact.py` 的 `MHR_WRIST_KEYPOINTS` 一致）。
- 质量（搬运段）：手腕到 FP 物体中心中位距离 ep04 0.20 m、ep03 0.16 m、ep13 0.40–0.44 m；ep13 p90 达 3.6 m（两手都是，约一成帧，原因未查）。
  掌心逐帧转角中位 3–5°、p90 4.5–11°、p99 6–26°，即逐帧有约 5° 的噪声，与选择器的 `ROT_DEG` 10° 同量级。

### 做法 1 的设计与离线试验登记（10-20，用户确认设计；判据登记于运行之前）

- 选择器相邻帧的转角项改为 `min(物体绝对转角, 物体相对持物手的转角) / (ROT_DEG·gap)`；相对转角 = 对称意义下 `∠(H·R_a, R_b)`，
  `H` = 两帧掌心 5 点（上节）的 Kabsch 旋转。只在两帧该手都「拿着」时启用：掌心任一点到物体表面（FoundationPose 原选位姿，
  官方网格均匀采样 2000 点）< `HOLD_M` 0.10 m（沿用物理检查）；两手都拿着时取较小者；关键点非有限则不启用。不加新参数、不平滑手。
  `t3_fp_select.py --carry` 开启（默认关，定下来之前不改默认）；`--poses-out=<npz>` 在 `--dry` 时存选中的相机系位姿。
- 离线（CPU，`--cpus 2`、`nice 19`）：ep03/ep04/ep13 × BETA {0, 0.1, 0.2, 0.3, 0.5} 各跑一次 `--carry --dry`；对照组是 A/B 已写好的
  `runs/work_b*/<ep>` 第 05 步 pkl（同 BETA 不带 carry），不重跑。在 FP 层评估 13 个答案帧，正确参考与 30° 容差同闸门：ep03 117/131/345
  与 ep13 40/120/800/860/915 取 `work_fp` 第 05 步位姿，ep03 451 取 `work_sel`（10-19 试点）第 05 步位姿，ep04 313/509/669 取 `work_init`
  第 05 步位姿，ep13 226 取 `work_fp` 的 CoCoNet 输出（用户判 FoundationPose 原选在此帧错、ctrl 的 CoCoNet 输出更接近）。
  另计三集 FP 层逐帧跳变（对称意义 > 24°）之和。
- **判据**：每个 BETA 上 carry 的答案帧判对数 ≥ 对照组，且跳变之和 ≤ 对照组；并至少一个 BETA 上判对数或跳变严格更好。满足则上 GPU
  重跑 06–07 再走链（另行登记），不满足记失败。
