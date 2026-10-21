# 计划：接管 Tier 3 重建，第 1 级——在自己的目录里复现 gb5 的 CPU 后处理段（t3takeover，10/21，第 2 版）

2026-10-21 02:0x MDT 写定，分支 track2/p1-training；取代 `agent-doc/plan-t3takeover-2026-10-21.md` 第 1 版（那份的复核要求重写，见它的“复核”一节）。
rxzhou 10/21 00:3x：“现在重建我们全权接管”。判据在结果出来之前登记在这里。不读 Tier 1；网格与地面平面的 `plane` 同她的管线与 t3g4。

## 0. 事实（都有记录）

1. **她的目录对我们可写**（同属 mfshared 组）；她的部分脚本写死了指向她目录的路径、没有覆盖办法：`t3_gb_chain.sh` 80–81 行、`t3_sel_full.sh` 25–29 行、`gate/chain_check.sh` 7 行、
   `deploy_l40s.sh` 9–10 行。`git status` 曾重写她仓库里的一个 `.git/index`（`agent-doc/plan-t3takeover-2026-10-21.md` 执行记录）。
2. **各步的命令、环境、线程**（10/21 只读核对，代码 `origin/track2/tier3-recon` 42f01f0；这些步骤的脚本在 e5ab7e5、af4cf06、42f01f0 三个版本里 sha256 相同）：
   - decode、focal、world：`v2d_cari4d` 镜像（ca1774d94cd9），`docker run --rm --user <uid>:<gid> --network none`，decode 固定 8 线程，focal/world 用 OMP 4（ep20、ep14）或 6（ep27）；
   - assemble、物理提取：她的宿主机 venv（Python 3.10.12、pyarrow 25.0.1、numpy 2.2.6、scipy 1.15.3、trimesh 5.1.0）；物理检查：镜像、`--cpus 8`；
   - support、dr2s、dyn7、align：gate venv（Python 3.11.17、numpy 2.3.5、scipy 1.15.3、trimesh 4.5.1、pyarrow 25.0.1、torch 2.7.0+cpu），support 用 OMP 4；
   - 支撑面 usda：gate venv + gate 仓库（rxzhou 的 f0ac98f 与 video_to_data v0.4.0），工作目录是 gate 目录。
3. **随机性**：support 的 RANSAC 用 rng(0)，dyn7 的 trimesh 采样种子 0、1，dr2s 没有随机数；物理检查有正对照（gb4 与 gb5 的 out npz 对 ep14、ep20 逐字节相同）。
   lean（`gate/t3_lean_support.py`）的 trimesh 采样没有种子，但这三集的 usda 没被 lean 改过。
4. **参照**：ep20、ep14 在 gb5 与 gb4 的转换文件是同一批 inode，gb5_best parquet 逐字节相同，_dr2s、_dyn7 只差页脚里的版本名；ep27 整条重算（BETA 0.5 的 05 选择、06–07、decode 到 world）。
   版本名写进了产物（物理 npz 与支撑面 json 的 tier 字段、parquet 的 from、world_calib 里的地面文件名），要逐字节一致就沿用她的版本名。
5. **地面与配准文件**：world 用的是 `runs/floor/floor_fit_gb5.json`（sha 2b58531f…）与 `camera_register_gb5.json`（sha 27766318…）；`runs/floor/*_gb3.json` 是更早的另一套，不能用。
   dr2s 不设 `T3_REGISTER` 时读 `runs/floor/camera_register.json`（只用一组的平面，与 gb5 那份相同）。support、dr2s、usda、lean 不设 `T3_FLOOR_FIT`、`T3_REGISTER` 时默认读 f830 那套。

## 1. 第 1 级做什么（只用 CPU）

范围：从她的 world 产物往后——assemble → 物理检查 → support → dr2s → 物理检查 → dyn7 → 支撑面 usda——三集：ep20（base，一个支撑面）、ep27（FoundationPose 集，gb5 重算，有桌面）、
ep14（二机位，base；它没有支撑面，usda 是空的，所以二机位的支撑面路径由 ep25 在第 2 级补）。decode、focal、world 与 CARI4D 留到第 2 级。

1. **防护包装** `stages/recovery/t3r_run.sh`（新写，测试 `test_t3r_run.py`）：
   - 导出 T3_ROOT、T3_PY、T3_GPY、T3_SOMA_ASSETS、T3_GATE、T3_FLOOR_FIT、T3_REGISTER，全部指向 `/lab_data/rxzhou/v2d/t3recon/`；
   - 命令行与环境变量里出现 `/lab_data/<她的目录>` 就拒绝（退出码 2）；`PYTHONDONTWRITEBYTECODE=1`、`GIT_OPTIONAL_LOCKS=0`；docker 只挂我们的目录（她的目录一律不挂）；
   - 每跑一步前后各记一次 `find /lab_data/<她的 v2d> -user rxzhou`，结果只能是已知的那一个 `.git/index`，多一个就停（退出码 3）。
2. **代码**：`track2/t3recon-rx` 从 42f01f0 开出；`git archive` 到 `/lab_data/rxzhou/v2d/t3recon/code`，写我们自己的 DEPLOYED 与 MANIFEST（dr2s、dyn7 的来历核对要它们）；
   gate 仓库从我们自己仓库 `git archive f0ac98f`，加 video_to_data v0.4.0（我们已有）。
3. **环境**：gate venv 与她的宿主机 venv 不复制（venv 里有指向她目录的绝对路径）。在 `v2d_cari4d` 镜像之外各建一个我们自己的 uv 环境，钉第 0 节第 2 条的版本
   （宿主机那套 Py 3.10 + pyarrow 25.0.1、numpy 2.2.6、scipy 1.15.3、trimesh 5.1.0；gate 那套 Py 3.11 + numpy 2.3.5、scipy 1.15.3、trimesh 4.5.1、pyarrow 25.0.1、torch 2.7.0+cpu），
   再 `pip freeze` 与她的两份 venv 逐包比（读她的 site-packages 目录名，只读）。版本不一致就记下、不进 K1 的判。
4. **数据**（只读复制，`cp`、不用硬链接，逐文件比 sha256，记 `results/t3recon/copy_manifest_ml40.txt`）：SOMA 资源；`input/meta/` 4 个文件；三集的网格与地面文件；
   `runs/floor/{floor_fit_gb5,camera_register_gb5,camera_register,intrinsics_gb3}.json`；`runs/tier3_cari4d_gb5_best.selection.json`；`dev/walls/moge_{ep14,ep20,ep27}*.npz`；
   三集的 world 产物（`convert_gb5/ep14…`、`convert_gb5/ep20…`、`convert_fp_gb5/ep27…`）；参照（三版 parquet 与元数据、physics 的 npz 与 out、support json、depth_post / dynamics_post /
   provenance、三份 usda 与 support_usda.json、align json）；负对照（ep27 的 gb4 parquet 三版）。参照放 `ref/`，我们的产物放 `out/`。
5. **跑**：按第 0 节第 2 条的命令逐步调用（不跑她的链脚本），版本名沿用她的（`tier3_cari4d_gb5_best…`），工作根是我们的 `t3recon/`；`--cpus 4`、`nice -n 10`（ml40 在训练）。

## 2. 判据（登记）

- K0（防护与复制）：包装测试全过；复制的每个文件 sha256 与源相同；每一步前后 `find … -user rxzhou` 只有那一个已知文件。不过就停。
- K1（复现成立）：逐段比、第一处不同就停并报：assemble 后的 parquet；物理检查的 npz 与 out；support json（沿用她的版本名后应逐字节相同）；
  dr2s 的 parquet 与 depth_post.json（四元数按转角比，q ≡ −q，≤ 1e-6 rad；位置 ≤ 1e-6 m）；dyn7 同；usda 逐字节。
  正对照：同一步在我们这边跑两遍结果相同。负对照：ep27 的 gb4 parquet 与 gb5 参照必须不同（证明比较能看出差别）。
  三集都过记“第 1 级接管成立：从 world 往后能在我们的目录里重出 gb5”。
- K2（不成立）：报第一处不同在哪一步、哪一列、差多少，先查版本与环境；查清前不在我们的副本上改后处理。
- 不提交；人工看图只作监看。

## 3. 风险与安排

- 环境重建要从 PyPI 装包：ml40 经 `V2D_PROXY`（stdin 注入）才能连外网；装不上就退回只读调用她的解释器（不复制、不写），记为偏差。
- gate 仓库 3.7 GB、video_to_data 要 LFS；我们 ml40 上已有 video_to_data v0.4.0 的副本（训练用），先核它是不是同一版。
- CPU 与训练链共用：每步限 4 核。预计复制 30 分钟、环境 1 小时、三集复现 1 小时。

## 执行记录

（空）
