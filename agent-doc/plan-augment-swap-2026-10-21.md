# 计划：换资产重跑，接上现在的后处理与闸门（augment-swap，10/21）

2026-10-21 11:30 EDT 写定，分支 `track2/augment-swap`（从 `track2/tier3-recon` 的 `42f01f0` 开出）。判据在结果出来之前登记在这里。
状态：待用户审阅，未执行。

## 0. 为什么现在做

主任务仍是打榜，Tier 3 重建 10/21 起由 rxzhou 负责，我们腾出手来做泛化。换资产 10/09 搁置，原因是 Tier 3 的公开榜只对 30 条官方
测试集计分，它本质上是对测试集过拟合，换资产对榜上的分数没有帮助。这一点今天仍然成立，所以本计划的目标不是榜上的分数。

它针对的是公开榜之外的两处，两处的原文 10/21 都重新核对过（官方页与 10/10 快照 sha256 相同；Kaggle §3 由用户从线上贴来，与快照逐字相同）：

- **赛后评测**：Kaggle §3.b「After the Competition closes, the Competition Sponsor evaluates selected solutions against data that is not
  part of the Competition Data」；官方页「we evaluate the top solutions on the broader dataset to determine how well they generalize」。
  更大的数据集里有没有新物体，原文没写。
- **Industry Innovation Award**：不看名次，要有效提交、承诺开源与技术报告。评审标准里的 Economic Viability（降低大规模数据生成
  的成本）与 Data Flywheel（不靠额外人工、随时间改进系统）对应的正是「一段视频换出多个资产变体」。

所以成功标准是：**一段 Tier 3 视频，自动换出多个资产变体，每个变体都过现在的后处理与闸门，全程不靠人工判定，一条命令可复现**
（Kaggle §3.c 要求奖项过 §2.9 的核验，其中有一条命令复现）。

## 1. 事实（都有记录）

1. 代码在 `stages/augment/`（10/08 23:20 – 10/09 17:20 EDT，止于 `b714a54`）：`swap_pilot.py`（摆放候选、量接触与穿入）→
   `hull_check.py`（CoACD 凸包穿入）→ `palm_resolve.py`（每个抓握段在物体系里平移手）→ `arm_refit.py`（重拟合肩到手的 SOMA 旋转）→
   `swap_viz.py`（并排参考视频）。候选由 `fetch_objaverse.py` 取，只留 CC0 与 CC BY（Kaggle 2.7.a）。
2. 10/09 的结果（ep00 倒地高脚凳扶正，候选 Barstool Round `b221…`，按高度缩放）：指尖误差 5.5/3.2 cm → 中位 0.01 cm、最大 0.15 cm，
   肩臂旋转最多改 12°；左手接触保持 0.34 → 0.996，右掌穿入 10.7% → 3.9%；网格细分到 1 cm 边后，按官方重定向的 2 cm 规则接触帧
   304/450（官方网格 283/460）。有抓握位置的 3 个候选里 2 个过 `palm_resolve` 的门槛。产物在 L40S `$T/aug/`（`pilot_v2`–`v5`、
   `palm_v1`/`v2`、`arm_v1/ep00_b221_height`），本机副本 `~/v2d/tier3/viz/`。
3. 当时没做的：用新网格跑官方重定向 `soma_to_g1`；换资产之后的后处理与闸门一步都没跑；`palm_resolve` 只解平移、不解手的旋转。
4. 当时的输入是 convert 目录里的 `soma_params.npz`，位于 focal、world、assemble、dr2s、dyn7 之前。gb5 里 ep00 取 `base`，convert 目录是
   `$T/runs/convert_gb5/ep00_tall_bar_stool/`（有 `soma_params{,_focal,_world}.npz`、`object_{cam,cam_focal,world}.npz`、`focal_calib.json`、
   `world_calib.json`）。
5. 后处理各步读网格的方式：`t3_physics_check.py`、`t3_support.py`、`t3_post_verify.py` 与 gate 里的检查读 `$T3_ROOT/input/<meta.mesh>`；
   gate 的根由 `gate/mkroot.py` 把 `mesh` 链到 `$T/input/mesh`；`t3_lean_support.py`、`t3_dynamics_check.py`、`t3_hand_object_check.py`
   读 gate 产物旁边的 `object/textured_mesh.obj`。换网格要在这几处一起换，漏一处的表现是那一步照旧拿官方网格判、不报错。
6. 物体直立轴现在由 `stages/augment/official_up.json` 给（凳子 `-z`），条目写着「checked by eye」。依据本来就是 Tier 3 自己的重建：
   ep21 拉凳子全程、ep00 结尾时世界的上方在物体系里都落在 `-z`。

## 2. 做什么

**S0 盘点（只读，CPU）。** 逐步确认 focal、world、assemble、dr2s、dyn7 哪几步会改人体手部的位置，哪几步读网格、从哪里读（把第 1 节
第 5 条补全到每个调用点）；确认 `convert_gb5/ep00` 与 10/09 的候选文件都还在。结果写进本文件执行记录。

**S1 直立轴改成自动判定。** 新工具 `stages/augment/auto_up.py`，两路证据：
- 重建：取这一集没人拿着的静止段（与闸门的 `held` 同一口径），把地面法向（`runs/floor/floor_fit_gb5.json` 里这一集所在组的地面平面）换到物体系，取各帧的主方向；
- 网格：`trimesh.poses.compute_stable_poses` 在凸包上给出的稳定姿态，取与上一路一致的那一个。
两路一致才给结果；某一集从头到尾没出现可用的静止段时，回退到稳定姿态里概率最高的那个，并在报告里标出。Objaverse 候选同样跑一遍，
不再默认 glTF 的 `+Y`。`official_up.json` 退出链路，只留作测试里的对照（自动结果与它不一致时测试红，再查原因）。

**S2 换资产接到 world 之后。** 换资产在 world 的产物上做（`soma_params_world.npz` + `object_world.npz`），之后接 assemble → 物理检查与
支撑面 → dr2s → dyn7 → `chain_check`。放在 world 之后，是因为 focal 步带人体重拟合，放在前面会把手的修改重新拟掉（S0 核实；若 S0 发现
focal 不动手部，再按最少改动的位置定）。每个变体建一个自己的根 `$T/aug/variants/<集>_<候选uid前8位>/`：`input/` 除了 `mesh/<obj>/` 换成
候选网格（文件名沿用官方的，脚本不用改）其余链接到 `$T/input`，gate 根用同一个 `input`；第 1 节第 5 条的 `textured_mesh.obj` 在 gate 的
`runs/motion_src/tier<T>/<序列>/object/` 下，由 motion_src 生成步（`challenge_to_soma.py`）写出，S0 核实它从变体根取网格。所有 `T3_*` 路径指向变体根；`runs/floor/*_gb5.json` 只读链接。

**S3 对照：拿官方网格当候选。** 同一套变体根机制、候选就是官方网格本身，从 world 产物跑到 dyn7 与 `chain_check`，结果必须与 gb5 交付的
ep00 逐字节相同（rxzhou 10/21 的复现已证明 assemble 之后各步在相同输入下逐字节确定）。不相同就停，先找出变体根漏换或多换了什么。

**S4 ep00 跑两个过了 `palm_resolve` 的候选。** 每个变体：`swap_pilot` → `hull_check` → `palm_resolve` → `arm_refit` → S2 的后处理链 →
官方重定向 `soma_to_g1`（新网格）→ `swap_viz`（画最终产物，不画中间产物）→ `t3_delivery_report.py` 出一份变体自己的报告。

**S5 推广。** ep00 两个变体都过 R1–R3 之后，再上 10/09 试点过的 ep05（箱子）与 ep20（电饭煲），另写执行记录；不过就停在 ep00，先归因。

不做：手的旋转求解（`palm_resolve` 现在只解平移，S4 结果说明需要时另立计划）；训练 policy（见第 5 节）。

## 3. 判据（登记）

- R0（对照）：S3 逐字节相同。
- R1（换资产本身）：沿用 10/09 登记的门槛，不改数——`swap_pilot` 与 `hull_check` 的接触保持与穿入、`palm_resolve` 的 KEEP_SHARE /
  PEN_SHARE / MAX_OFFSET_M、`arm_refit` 的断言（未动关节逐位不变）。
- R2（后处理与闸门）：`chain_check` 与 gb5 交付同一套检查、同一组阈值；每项报告变体对 S3 对照的差值。阈值一个都不为变体放宽。
- R3（端到端）：在最终 parquet 上重算接触，左右手在原接触帧上的保持比例都不低于 R1 的 KEEP_SHARE——后处理不能把换资产对上的手又拉开。
- R4（自动化）：从 convert 产物到报告由一条命令跑完，链路里没有任何人工判定的输入；`auto_up.py` 在凳子上给出 `-z`。
- 人看并排视频只作监看，不作通过或选择的依据（同 rxzhou 10/20 的合规口径）。

## 4. 合规与边界

- 输入只用 Tier 3 的东西：我们的 CARI4D 重建、Tier 3 输入目录、官方网格（用户 10/12 定可用），外加 CC0 / CC BY 的公开资产（2.7.a，
  署名记在 manifest）。不读 Tier 1、Tier 2 的轨迹，不读官方支撑面。
- 产物只写 `$T/aug/`；不写 `$T/runs/`、不登记进 `versions.json`（变体不是 Tier 3 交付版本），另记 `$T/aug/variants.json`。
  rxzhou 白名单里的 16 个目录不碰。
- 全在 CPU 上：docker 步 `--cpus 4`、宿主机步 `nice -n 10`，不占 L40S 的 GPU。rxzhou 只读挂载我们的目录做复现，`$T/aug/` 里新增目录
  不影响他。
- 代码按惯例用 `deploy_l40s.sh` 部署。重建输入固定在 gb5；rxzhou 以后出新的重建版本，换资产链按同一条命令在新版本上重跑。

## 5. 之后：policy 层面的泛化（不在本计划内）

数据侧过了，才谈 policy 侧：rxzhou 现在每集训一个 policy，拿变体数据训，对公开榜不加分。要回答「换资产能不能让 policy 对没见过的
物体更稳」，需要一个小实验（例如 ep00 用若干变体训、在留出的一个变体上评），要用到他的训练链与 GPU 时段。这件事先和 rxzhou 商量，
另写计划。

## 待用户定

1. S2 的位置（world 之后）以 S0 的结果为准，S0 若发现别的步也会改手，再拿方案来问。
2. 自动直立轴两路不一致时，是停下报告还是回退到稳定姿态——计划写的是回退并标出，可以改成停。
3. S5 要不要等 ep00 的并排视频你看过再推广（视频只作监看，但推广与否由你定）。

## 执行记录

（空）
