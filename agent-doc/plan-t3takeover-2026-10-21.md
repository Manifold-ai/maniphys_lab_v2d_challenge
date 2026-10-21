# 计划：接管 Tier 3 重建——先在自己的目录里复现 gb5（t3takeover，10/21 凌晨，第 1 版）

2026-10-20 23:5x MDT 写定第 1 版，分支 track2/p1-training。rxzhou 10/21 00:3x：“现在重建我们全权接管”。判据在结果出来之前登记在这里。
只读另一位成员的目录，不写、不删、不停她的进程；改动只在我们自己的目录与分支里。不读 Tier 1；Tier 2 只用网格与地面平面的 `plane`（同她的管线与 t3g4）。

## 0. 事实（都有记录）

1. 代码在我们 GitHub 仓库的 `track2/tier3-recon` 分支（本地已 fetch，469 个提交，最新 42f01f0 = ml40 上部署的版本，`DEPLOYED … dirty=0`）；脚本在 `stages/recovery/tier3/`（124 个文件）。
   ml40 上 `tier3/code` 是 `deploy_l40s.sh` 的 rsync 副本（`MANIFEST.sha256` 165 个文件），另有 `tier3/patched/`（CARI4D 与 FoundationPose 导出的补丁版，脚本按 md5 核）。
2. 流程（她的 `agent-doc/overview-tier3-pipeline-2026-10-20.md`）：掩码（DINO + SAM2）→ CARI4D 01–08（GPU，单集 26 分钟到 2 小时，约 44 GB 显存，只能在 L40S 上跑）
   → 逐集选版本 → 转换（decode、soma、focal、world、assemble）→ 物理检查与支撑面 → dr2s → dyn7 → 检查与交付；转换以后都在 CPU 上。
3. 环境：ml40 上的 docker 镜像 `v2d_grounding_dino`、`v2d_sam2`、`v2d_cari4d`、`v2d_sam3d`（宿主机共用，用镜像不写她的目录）；她的宿主机 venv（Python 3.10）与 gate venv（uv Python 3.11）。
   权重 cari4d 6.5 GB、gdino 662 MB、sam2 1.7 GB；SOMA 资源 268 MB；工具包 `video_to_data` 146 MB；输入 999 MB（30 段视频、29 个网格、只留 `plane` 的地面文件、meta）。
   ml40 的 `/lab_data` 空闲 994 GB。
4. 现状：交付版 gb5（29 集 + ep28 在 suspect）；已知问题 ep28 重建失败、ep29 脚与行李箱有缺口、ep11 右手、ep16 第 105–125 帧手离瓶约 10 cm、遮挡帧朝向错；
   自检还缺“合成轨迹空跑与幂等性”“每帧可信度”两项工具。合规：gb5 的 BETA 由自动规则选（`agent-doc/plan-t3g5-2026-10-21.md` 执行记录，规则 4.b）。
5. 世界系与地面拟合用 30 集一起拟（`runs/floor/floor_fit_gb5.json`、`camera_register_gb5.json`），单集复现时沿用这些文件，不重拟。

## 1. 做什么

1. **代码**：Mac 上 `git worktree add ../V2D-t3recon 42f01f0`（分离头指针，只读用）；我们要改的东西开新分支 `track2/t3recon-rx`（从 42f01f0），不往她的分支推。
2. **复制到我们的目录**（ml40，只读她的源，CPU）：`/lab_data/rxzhou/v2d/t3recon/` 下放 code（按她的 `MANIFEST.sha256` 逐文件核）、patched、weights（cari4d、gdino、sam2）、
   soma_assets、video_to_data、input、`runs/floor` 与 `runs/camera_groups` 的 gb5 文件、`tier3_cari4d_gb5_best.selection.json`、gb5 交付目录本身（作对照）。
   每个目录复制后逐文件比 sha256，记 `results/t3recon/copy_manifest_ml40.txt`。不复制工作目录（236 GB）与归档。
3. **复现（只用 CPU，GPU 留给训练）**：选 2 集——非 FoundationPose 集 ep5、FoundationPose 集 ep27——把她这两集 CARI4D 08 之后的产物（`work/<ep>` 里转换要读的部分）复制过来，
   在 `v2d_cari4d` 容器里用我们的副本跑转换 → 组装 → 支撑面 → dr2s → dyn7（参数照 gb5 的来历记录），得到两份 parquet 与支撑面。
4. **GPU 复现**（ml40 空出来以后，约 10/21 21:00 之后，另写短计划）：ep5 从掩码起整条跑一次，比与 gb5 的差。

## 2. 判据（登记）

- K0：复制的每个文件 sha256 与源相同；code 与她的 `MANIFEST.sha256` 一致。
- K1（CPU 复现成立）：两集 parquet 的每一列与 gb5 交付的同集相比，数值列最大绝对差 ≤ 1e-6（米、弧度），整数列相等；支撑面 usda 逐字节相同或几何差 ≤ 1e-7 m。
  成立就记“我们能从 CARI4D 08 之后接着做”，此后对后处理的改动从我们的副本出。
- K2（不成立）：逐列报差异、找原因（版本、参数、随机性），在找到之前不在我们的副本上改后处理。
- 不提交；对真值的效果只能从榜上看。人工看图只作监看。

## 3. 风险

- 她的后处理里可能读了容器内固定路径（`/x/...`）或宿主机 venv：照她的部署脚本挂载；不行就记下差异再定。
- 随机性：dyn7、dr2s 若有随机数，K1 的 1e-6 可能过严；先查脚本里有没有随机数，有就按她的种子。
- ml40 的 CPU 与训练链共用：复现限 `--cpus 4`。

## 执行记录

（空）
